"""Orchestrator – multi-agent system deployed on AgentCore.

Uses the Strands "Agents as Tools" pattern:
  1. Triage Agent   – classifies intent (QUERY / ANALYSIS / ACTION / MIXED)
  2. Analysis Agent – read-only MCP tools on the PM server
  3. Action Agent   – write MCP tools on the PM server

The orchestrator agent receives the user prompt + triage classification and
delegates to the appropriate specialist(s).
"""

import logging

from bedrock_agentcore.runtime import BedrockAgentCoreApp
from strands import Agent

from agents import run_triage, analysis_agent, action_agent, Intent
from model.load import load_model

app = BedrockAgentCoreApp()
log = app.logger
logger = logging.getLogger("orchestrator")

# ---------------------------------------------------------------------------
# Orchestrator system prompt
# ---------------------------------------------------------------------------

ORCHESTRATOR_PROMPT = """You are an Orchestrator for a multi-agent project management system.

You coordinate specialized agents to handle user requests:
- **analysis_agent**: For reading data, computing metrics, generating reports, searching tasks
- **action_agent**: For creating tasks, updating tasks, reassigning tasks, adding comments

Routing rules:
- QUERY or ANALYSIS intents → use analysis_agent
- ACTION intents → use action_agent
- MIXED intents → use analysis_agent first, then action_agent with the analysis results

Always provide a cohesive final answer summarizing what was done.
If an agent reports an error, explain it and suggest alternatives.
"""

# ---------------------------------------------------------------------------
# Routing helpers
# ---------------------------------------------------------------------------

INTENT_HINTS = {
    Intent.QUERY: "This is a data QUERY. Use the analysis_agent to retrieve the information.",
    Intent.ANALYSIS: "This requires ANALYSIS. Use the analysis_agent to compute metrics and generate a report.",
    Intent.ACTION: "This requires ACTION. Use the action_agent to make changes.",
    Intent.MIXED: (
        "This is a MIXED request. "
        "First use analysis_agent to gather data, "
        "then use action_agent with the findings to make changes."
    ),
}


def _build_routing_prompt(request: str, intent: Intent, reasoning: str) -> str:
    hint = INTENT_HINTS.get(intent, INTENT_HINTS[Intent.QUERY])
    return (
        f"User request: {request}\n\n"
        f"Triage classification: {intent.value}\n"
        f"Triage reasoning: {reasoning}\n\n"
        f"Instructions: {hint}"
    )


# ---------------------------------------------------------------------------
# AgentCore entrypoint
# ---------------------------------------------------------------------------

@app.entrypoint
async def invoke(payload, context):
    session_id = getattr(context, "session_id", "default")
    prompt = payload.get("prompt", "")
    logger.info(f"[ORCHESTRATOR] session={session_id} prompt={prompt[:100]}")

    # Step 1: Triage
    intent, reasoning = run_triage(prompt)
    logger.info(f"[ORCHESTRATOR] Triage → {intent.value}: {reasoning[:120]}")

    # Step 2: Route via orchestrator agent
    orchestrator_agent = Agent(
        model=load_model(),
        system_prompt=ORCHESTRATOR_PROMPT,
        tools=[analysis_agent, action_agent],
    )

    routing_prompt = _build_routing_prompt(prompt, intent, reasoning)

    try:
        stream = orchestrator_agent.stream_async(routing_prompt)

        async for event in stream:
            if "data" in event and isinstance(event["data"], str):
                yield event["data"]
    except Exception as e:
        logger.error(f"[ORCHESTRATOR] Error: {e}", exc_info=True)
        yield f"Error processing request: {e}"


if __name__ == "__main__":
    app.run()