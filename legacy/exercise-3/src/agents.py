"""Specialized agents for the multi-agent system.

Uses the Strands "Agents as Tools" pattern:
- Triage Agent: classifies intent (LLM-only, no tools)
- Analysis Agent: read-only data operations via MCP
- Action Agent: write operations via MCP
"""

import logging
import os
import sys
from enum import Enum as PyEnum

from pydantic import BaseModel, Field

from strands import Agent, tool, ToolContext

# Add exercise-3/src to path for sibling imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from protocol import AgentMessage, Intent, SharedContext

from shared.config import make_model, make_mcp_client
from shared.observability import trace_attributes

logger = logging.getLogger("exercise3.agents")


# ---------------------------------------------------------------------------
# Triage Agent (LLM-only, no tools)
# ---------------------------------------------------------------------------

TRIAGE_PROMPT = """You are a Triage Agent. Your ONLY job is to classify the user's request.

Classify each request into one of these intents:
- QUERY: Read-only data retrieval (e.g., "list tasks", "show me blocked tasks", "who is assigned to...")
- ANALYSIS: Aggregation, comparison, reporting (e.g., "compare workloads", "generate project health report", "analyze distribution")
- ACTION: Write operations (e.g., "create task", "reassign task", "add comment", "update status")
- MIXED: Requires analysis THEN action (e.g., "find overloaded members and rebalance", "find blocked tasks and create tasks to fix them")

Provide the intent and a one-sentence reasoning.
"""


# ── Structured output model for triage ────────────────────────────────────

class TriageIntent(str, PyEnum):
    """Allowed intent values returned by the Triage Agent."""
    QUERY = "query"
    ANALYSIS = "analysis"
    ACTION = "action"
    MIXED = "mixed"


class TriageResult(BaseModel):
    """Structured triage classification."""
    intent: TriageIntent = Field(description="The classified intent of the user request")
    reasoning: str = Field(description="One-sentence explanation of why this intent was chosen")


def run_triage(user_request: str, ctx: SharedContext) -> Intent:
    """Classify the user request using the Triage Agent with structured output."""
    logger.info(f"[TRIAGE] Classifying: {user_request[:100]}")
    triage_agent = Agent(
        model=make_model(temperature=0.0),
        system_prompt=TRIAGE_PROMPT,
        tools=[],
        trace_attributes=trace_attributes(agent_name="triage"),
    )

    try:
        result = triage_agent(
            user_request,
            structured_output_model=TriageResult,
        )
        triage: TriageResult = result.structured_output
        logger.info(f"[TRIAGE] Intent: {triage.intent.value}, Reasoning: {triage.reasoning}")

        intent = Intent(triage.intent.value)
        ctx.intent = intent
        ctx.triage_reasoning = triage.reasoning

        ctx.add_message(AgentMessage(
            sender="triage",
            recipient="orchestrator",
            intent=intent.value,
            content=ctx.triage_reasoning,
            confidence=1.0,
        ))

        return intent
    except Exception as e:
        logger.error(f"[TRIAGE] Error: {e}", exc_info=True)
        ctx.errors.append(f"Triage error: {e}")
        ctx.intent = Intent.QUERY
        return Intent.QUERY


# ---------------------------------------------------------------------------
# Analysis Agent (read-only tools)
# ---------------------------------------------------------------------------

ANALYSIS_PROMPT = """You are an Analysis Agent specialized in reading and aggregating project management data.

Your role:
- Search and retrieve tasks, projects, and user information
- Compute metrics and statistics (task counts, workload distribution, completion rates)
- Generate structured reports and summaries
- Identify patterns (overdue tasks, blocked items, overloaded team members)

You have access to read-only MCP tools: search_tasks, get_task_details, get_project_summary, list_users.

Guidelines:
- Be thorough: gather all necessary data before forming conclusions
- Present findings in a clear, structured format
- Include numbers and specific data points
- When analyzing workload, count tasks by status for each user
"""


@tool(context=True)
def analysis_agent(query: str, tool_context: ToolContext) -> str:
    """Analyze project data, compute metrics, generate reports, and retrieve information.

    Use this agent for: searching tasks, getting statistics, comparing workloads,
    generating project health reports, and any read-only data operations.

    Args:
        query: The analysis question or data retrieval request.
    """
    logger.info(f"[ANALYSIS] Processing: {query[:100]}")
    read_tools = make_mcp_client(
        tool_filters={"allowed": ["search_tasks", "get_task_details", "get_project_summary", "list_users"]}
    )

    agent = Agent(
        model=make_model(),
        system_prompt=ANALYSIS_PROMPT,
        tools=[read_tools],
        trace_attributes=trace_attributes(agent_name="analysis"),
    )

    try:
        response = agent(query)
        result = str(response)
        logger.info(f"[ANALYSIS] Result: {result[:200]}...")
        _extract_tool_calls(agent, "analysis", tool_context)
        return result
    except Exception as e:
        logger.error(f"[ANALYSIS] Error: {e}")
        return f"Analysis error: {e}"


# ---------------------------------------------------------------------------
# Action Agent (write tools)
# ---------------------------------------------------------------------------

ACTION_PROMPT = """You are an Action Agent specialized in executing write operations on the project management system.

Your role:
- Create new tasks
- Update task fields (status, priority, description, due date)
- Assign or reassign tasks to users
- Add comments to tasks

You have access to write MCP tools: create_task, update_task, assign_task, add_comment.
You also have access to list_users and search_tasks to look up IDs when needed.

Guidelines:
- Always verify user/task IDs before making changes
- Report what was changed after each operation
- If bulk operations are requested, process them one at a time and report results
- On error, explain what went wrong and do NOT retry with the same invalid parameters
"""


@tool(context=True)
def action_agent(instruction: str, tool_context: ToolContext) -> str:
    """Execute write operations on the project management system.

    Use this agent for: creating tasks, updating tasks, reassigning tasks,
    adding comments, and any operations that modify data.

    Args:
        instruction: The action to perform, including any context from prior analysis.
    """
    logger.info(f"[ACTION] Processing: {instruction[:100]}")
    write_tools = make_mcp_client(
        tool_filters={"allowed": [
            "create_task", "update_task", "assign_task", "add_comment",
            "list_users", "search_tasks",
        ]}
    )

    agent = Agent(
        model=make_model(),
        system_prompt=ACTION_PROMPT,
        tools=[write_tools],
        trace_attributes=trace_attributes(agent_name="action"),
    )

    try:
        response = agent(instruction)
        result = str(response)
        logger.info(f"[ACTION] Result: {result[:200]}...")
        _extract_tool_calls(agent, "action", tool_context)
        return result
    except Exception as e:
        logger.error(f"[ACTION] Error: {e}")
        return f"Action error: {e}"


# ---------------------------------------------------------------------------
# Tool-call extraction helper
# ---------------------------------------------------------------------------

def _extract_tool_calls(agent: Agent, agent_name: str, tool_context: ToolContext):
    """Extract MCP tool calls from an inner agent's message history into SharedContext.

    Uses ToolContext.invocation_state to access the SharedContext passed by the
    orchestrator — no module-level globals needed.
    """
    ctx: SharedContext | None = tool_context.invocation_state.get("shared_context")
    if ctx is None:
        return
    for msg in agent.messages:
        if msg.get("role") != "assistant":
            continue
        for block in msg.get("content", []):
            if "toolUse" in block:
                tu = block["toolUse"]
                ctx.log_tool_call(
                    agent=agent_name,
                    tool=tu.get("name", "unknown"),
                    params=tu.get("input", {}),
                    result="",  # result is in the toolResult block, not needed for trace
                )
