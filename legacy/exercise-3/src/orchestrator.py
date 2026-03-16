"""Orchestrator: coordinates specialized agents to handle complex user requests.

Routes requests through Triage → Analysis/Action based on classified intent.
Uses the Strands "Agents as Tools" pattern for delegation.
"""

import logging
import os
import sys
import time
from typing import Any

from strands import Agent
from strands.hooks import BeforeToolCallEvent, HookProvider, HookRegistry
from shared.config import make_model
from shared.sessions import create_session_manager, delete_session
from shared.observability import setup_telemetry, trace_attributes

# Add exercise-3/src to path for sibling imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from protocol import Intent, SharedContext
from agents import run_triage, analysis_agent, action_agent

logger = logging.getLogger("exercise3.orchestrator")

SESSIONS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "sessions")

# ---------------------------------------------------------------------------
# Logging & Telemetry
# ---------------------------------------------------------------------------

LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
setup_telemetry("exercise-3", log_dir=LOG_DIR, app_log_name="orchestrator")

# ---------------------------------------------------------------------------
# Interrupt Hooks — native Strands BeforeToolCallEvent guards
# ---------------------------------------------------------------------------

CONFLICT_KEYWORDS = ["delete", "remove all", "bulk", "reassign all", "drop"]
TIMEOUT_SECONDS = float(os.environ.get("ORCHESTRATOR_TIMEOUT", "120"))


class ConflictGuardHook(HookProvider):
    """Interrupt the orchestrator before potentially destructive action_agent calls.

    Uses the native Strands interrupt system (BeforeToolCallEvent) to pause
    execution and request human approval when dangerous keywords are detected
    in the action_agent instruction.
    """

    def __init__(self, app_name: str = "exercise3") -> None:
        self.app_name = app_name

    def register_hooks(self, registry: HookRegistry, **kwargs: Any) -> None:
        registry.add_callback(BeforeToolCallEvent, self._guard)

    def _guard(self, event: BeforeToolCallEvent) -> None:
        if event.tool_use["name"] != "action_agent":
            return

        instruction = event.tool_use["input"].get("instruction", "").lower()
        triggered = [kw for kw in CONFLICT_KEYWORDS if kw in instruction]
        if not triggered:
            return

        logger.warning(f"[CONFLICT GUARD] Dangerous keywords {triggered} in action_agent call")
        approval = event.interrupt(
            f"{self.app_name}-conflict-guard",
            reason={
                "tool": "action_agent",
                "instruction_preview": event.tool_use["input"].get("instruction", "")[:300],
                "triggered_keywords": triggered,
            },
        )
        if approval.lower() not in ("y", "yes", "approve"):
            event.cancel_tool = f"Action cancelled by user: {approval}"


class TimeoutGuardHook(HookProvider):
    """Interrupt if total orchestration time exceeds the configured threshold.

    Checks elapsed time before every tool call. If the threshold is exceeded,
    the interrupt gives the caller a chance to continue or abort.
    """

    def __init__(self, app_name: str = "exercise3", max_seconds: float = TIMEOUT_SECONDS) -> None:
        self.app_name = app_name
        self.max_seconds = max_seconds
        self._start_time: float | None = None

    def register_hooks(self, registry: HookRegistry, **kwargs: Any) -> None:
        registry.add_callback(BeforeToolCallEvent, self._check)

    def _check(self, event: BeforeToolCallEvent) -> None:
        if self._start_time is None:
            self._start_time = time.time()

        elapsed = time.time() - self._start_time
        if elapsed <= self.max_seconds:
            return

        logger.warning(f"[TIMEOUT GUARD] Elapsed {elapsed:.0f}s > {self.max_seconds}s")
        approval = event.interrupt(
            f"{self.app_name}-timeout",
            reason={
                "elapsed_seconds": round(elapsed, 1),
                "max_seconds": self.max_seconds,
            },
        )
        if approval.lower() not in ("y", "yes", "continue"):
            event.cancel_tool = f"Operation timed out after {elapsed:.0f}s"
        else:
            # Reset timer so user gets another full window
            self._start_time = time.time()

    def reset(self) -> None:
        """Reset the timer for a new request."""
        self._start_time = None


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

ORCHESTRATOR_PROMPT = """You are an Orchestrator for a multi-agent project management system.

You coordinate specialized agents to handle user requests:
- **analysis_agent**: For reading data, computing metrics, generating reports, searching tasks
- **action_agent**: For creating tasks, updating tasks, reassigning tasks, adding comments

Workflow:
1. You receive the user's request along with a triage classification
2. Based on the intent, delegate to the appropriate specialist agent(s)
3. For MIXED intents: first call analysis_agent to gather data, then pass those findings to action_agent
4. Combine results into a clear, comprehensive response

Guidelines:
- For QUERY/ANALYSIS intents: use analysis_agent
- For ACTION intents: use action_agent 
- For MIXED intents: use analysis_agent first, then action_agent with the analysis results
- Always provide a cohesive final answer that summarizes what was done
- If an agent reports an error, explain it to the user and suggest alternatives
"""


class Orchestrator:
    """Multi-agent orchestrator using Strands' Agents-as-Tools pattern."""

    def __init__(self, session_id: str | None = None, auto_approve: bool = False):
        self.session_id, self._session_manager = create_session_manager(
            session_id, SESSIONS_DIR
        )
        self.auto_approve = auto_approve
        self._timeout_hook = TimeoutGuardHook()
        logger.info(f"Orchestrator session: {self.session_id}")

        self.orchestrator_agent = Agent(
            model=make_model(),
            system_prompt=ORCHESTRATOR_PROMPT,
            tools=[analysis_agent, action_agent],
            session_manager=self._session_manager,
            hooks=[ConflictGuardHook(), self._timeout_hook],
        )

    def process(self, user_request: str) -> tuple[str, SharedContext]:
        """Process a user request through the multi-agent pipeline.

        Returns:
            Tuple of (final_response, shared_context_with_trace)
        """
        ctx = SharedContext(original_request=user_request)
        start_time = time.time()

        # Step 1: Triage
        logger.info(f"[ORCHESTRATOR] Processing: {user_request[:100]}")
        intent = run_triage(user_request, ctx)
        logger.info(f"[ORCHESTRATOR] Triage result: {intent.value} - {ctx.triage_reasoning}")

        # Step 2: Route to specialist agent(s) via the orchestrator agent
        routing_prompt = self._build_routing_prompt(user_request, intent, ctx)
        self._timeout_hook.reset()

        try:
            # Pass SharedContext via invocation_state so @tool(context=True)
            # functions can access it through ToolContext.invocation_state
            response = self.orchestrator_agent(routing_prompt, shared_context=ctx)

            # Handle interrupts (conflict guard / timeout guard)
            response = self._handle_interrupts(response, ctx)

            final_answer = str(response)
        except Exception as e:
            logger.error(f"[ORCHESTRATOR] Error: {e}", exc_info=True)
            ctx.errors.append(f"Orchestrator error: {e}")
            final_answer = f"I encountered an error processing your request: {e}"

        # Store results
        if intent in (Intent.QUERY, Intent.ANALYSIS):
            ctx.analysis_result = final_answer
        elif intent == Intent.ACTION:
            ctx.action_result = final_answer
        else:
            ctx.analysis_result = final_answer
            ctx.action_result = final_answer

        elapsed = time.time() - start_time
        logger.info(f"[ORCHESTRATOR] Completed in {elapsed:.1f}s")

        return final_answer, ctx

    def _handle_interrupts(self, response, ctx: SharedContext):
        """Handle Strands interrupt loop for conflict/timeout guards.

        When a hook raises an interrupt, the agent stops and returns the
        interrupt(s). We collect responses (interactive or auto-approve) and
        re-invoke the agent until it completes normally.
        """
        while response.stop_reason == "interrupt":
            interrupt_responses = []
            for interrupt in response.interrupts:
                logger.info(f"[INTERRUPT] {interrupt.name}: {interrupt.reason}")

                if self.auto_approve:
                    user_input = "y"
                    logger.info(f"[INTERRUPT] Auto-approved: {interrupt.name}")
                else:
                    # Interactive mode: prompt the user
                    print(f"\n⚠️  Interrupt: {interrupt.name}")
                    print(f"   Reason: {interrupt.reason}")
                    user_input = input("   Approve? (y/n): ").strip() or "n"

                resolution = "approved" if user_input.lower() in ("y", "yes") else f"denied: {user_input}"
                ctx.escalations.append({
                    "type": "conflict" if "conflict" in interrupt.name else "timeout",
                    "name": interrupt.name,
                    "reason": interrupt.reason,
                    "resolution": resolution,
                })

                interrupt_responses.append({
                    "interruptResponse": {
                        "interruptId": interrupt.id,
                        "response": user_input,
                    }
                })

            response = self.orchestrator_agent(interrupt_responses)

        return response

    def _build_routing_prompt(self, request: str, intent: Intent, ctx: SharedContext) -> str:
        """Build the prompt for the orchestrator agent with routing hints."""
        intent_hints = {
            Intent.QUERY: "This is a data QUERY. Use the analysis_agent to retrieve the information.",
            Intent.ANALYSIS: "This requires ANALYSIS. Use the analysis_agent to compute metrics and generate a report.",
            Intent.ACTION: "This requires ACTION. Use the action_agent to make changes to the system.",
            Intent.MIXED: (
                "This is a MIXED request requiring both analysis and action. "
                "First use the analysis_agent to gather and analyze data, "
                "then use the action_agent with the analysis results to make the necessary changes."
            ),
        }

        return (
            f"User request: {request}\n\n"
            f"Triage classification: {intent.value}\n"
            f"Triage reasoning: {ctx.triage_reasoning}\n\n"
            f"Instructions: {intent_hints.get(intent, intent_hints[Intent.QUERY])}"
        )

    def reset(self):
        """Reset conversation history by creating a new session."""
        delete_session(self.session_id, SESSIONS_DIR)

        self.session_id, self._session_manager = create_session_manager(
            None, SESSIONS_DIR
        )
        logger.info(f"Orchestrator reset → new session: {self.session_id}")

        self._timeout_hook = TimeoutGuardHook()
        self.orchestrator_agent = Agent(
            model=make_model(),
            system_prompt=ORCHESTRATOR_PROMPT,
            tools=[analysis_agent, action_agent],
            session_manager=self._session_manager,
            hooks=[ConflictGuardHook(), self._timeout_hook],
            trace_attributes=trace_attributes(
                session_id=self.session_id, agent_name="orchestrator"
            ),
        )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def run_interactive():
    """Run the multi-agent system in interactive CLI mode."""
    from rich.console import Console
    from shared.cli import interactive_cli

    _console = Console()

    # Mutable container so callbacks can share state
    state = {"orch": Orchestrator(), "last_ctx": None}

    def _create():
        return state, state["orch"].session_id

    def _process(st, msg):
        answer, ctx = st["orch"].process(msg)
        st["last_ctx"] = ctx
        return answer

    def _reset(st):
        st["orch"].reset()
        st["last_ctx"] = None
        return st, st["orch"].session_id

    def _trace(st):
        ctx = st.get("last_ctx")
        if ctx:
            _console.print(f"[dim]{ctx.get_trace()}[/dim]")
        else:
            _console.print("[dim]No trace available yet.[/dim]")

    def _after(st, _answer):
        ctx = st.get("last_ctx")
        if ctx:
            return (
                f"Intent: {ctx.intent.value if ctx.intent else 'unknown'} | "
                f"Messages: {len(ctx.messages)} | "
                f"Errors: {len(ctx.errors)}"
            )
        return None

    interactive_cli(
        title="🤖 Multi-Agent Project Management System",
        subtitles=[
            "Orchestrator → Triage → Analysis/Action Agents",
            "Powered by AWS Strands SDK + Amazon Bedrock + MCP",
        ],
        create=_create,
        process=_process,
        reset=_reset,
        commands={"trace": _trace},
        after_response=_after,
    )


def run_single(prompt: str) -> tuple[str, str]:
    """Run a single prompt, return (response, trace)."""
    orch = Orchestrator()
    answer, ctx = orch.process(prompt)
    return answer, ctx.get_trace()


# ---------------------------------------------------------------------------
# Scenario runner — saves transcripts to examples/
# ---------------------------------------------------------------------------

SCENARIOS = [
    ("scenario_1_workload_rebalance", "Analyze the workload distribution across the team and rebalance by reassigning tasks from overloaded members to those with capacity"),
    ("scenario_2_blocked_tasks_action", "Find all blocked tasks, identify what's blocking them based on comments, and create new tasks to address each blocker"),
    ("scenario_3_project_health_report", "Generate a project health report for all active projects including task completion rates, overdue counts, and blocked items"),
    ("scenario_4_sprint_planning", "Review all in-progress and to-do tasks across projects, then create 3 new high-priority tasks for the upcoming sprint: an API integration test task, a deployment checklist task, and a performance benchmarking task, assigning each to the most appropriate team member based on their current workload and role"),
]


def run_save_examples():
    """Run all 4 required scenarios and save transcripts to examples/."""
    from datetime import datetime, timezone

    examples_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "examples")
    os.makedirs(examples_dir, exist_ok=True)

    print(f"Running {len(SCENARIOS)} scenarios and saving to {examples_dir}/\n")

    for filename, prompt in SCENARIOS:
        print(f"▶ {filename}")
        print(f"  Prompt: {prompt[:80]}...")

        orch = Orchestrator(auto_approve=True)
        try:
            answer, ctx = orch.process(prompt)
            trace = ctx.get_trace()
        except Exception as e:
            answer = f"Error: {e}"
            trace = ""

        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        transcript = (
            f"# {filename}\n"
            f"Generated: {ts}\n\n"
            f"## Prompt\n{prompt}\n\n"
            f"## Response\n{answer}\n\n"
            f"## Agent Trace\n```\n{trace}\n```\n"
        )

        filepath = os.path.join(examples_dir, f"{filename}.md")
        with open(filepath, "w") as f:
            f.write(transcript)
        print(f"  ✓ Saved to examples/{filename}.md\n")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--save-examples":
        run_save_examples()
    elif len(sys.argv) > 1:
        prompt = " ".join(sys.argv[1:])
        answer, trace = run_single(prompt)
        print(answer)
        print("\n" + trace)
    else:
        run_interactive()
