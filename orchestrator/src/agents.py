"""Specialized agents for the multi-agent orchestrator.

Simplified "Agents as Tools" pattern from legacy exercise-3:
- Triage Agent  : LLM-only, classifies intent (QUERY / ANALYSIS / ACTION / MIXED)
- Analysis Agent: read-only MCP tools (search_tasks, get_task_details, get_project_summary, list_users)
- Action Agent  : write MCP tools (create_task, update_task, assign_task, add_comment + lookups)

Each specialist agent is wrapped as a @tool so the orchestrator can invoke
them as regular Strands tool calls.

MCP tools are called via boto3 invoke_agent_runtime (same pattern as proxy.py).
"""

import logging
from enum import Enum

from strands import Agent, tool
from model.load import load_model
from mcp_client.tools import READ_TOOLS, WRITE_TOOLS

logger = logging.getLogger("orchestrator.agents")


# ---------------------------------------------------------------------------
# Intent enum
# ---------------------------------------------------------------------------

class Intent(str, Enum):
    QUERY = "query"
    ANALYSIS = "analysis"
    ACTION = "action"
    MIXED = "mixed"


# ---------------------------------------------------------------------------
# Triage Agent (LLM-only)
# ---------------------------------------------------------------------------

TRIAGE_PROMPT = """You are a Triage Agent. Classify the user's request into exactly ONE intent.

Intents:
- QUERY     – read-only data retrieval ("list tasks", "show blocked tasks")
- ANALYSIS  – aggregation / reporting ("compare workloads", "project health report")
- ACTION    – write operations ("create task", "reassign task", "update status")
- MIXED     – requires analysis THEN action ("find overloaded members and rebalance")

Respond with ONLY the intent word (QUERY, ANALYSIS, ACTION, or MIXED) on the first line,
followed by a one-sentence reasoning on the second line.
"""


def run_triage(user_request: str) -> tuple[Intent, str]:
    """Classify the user request. Returns (intent, reasoning)."""
    logger.info(f"[TRIAGE] Classifying: {user_request[:100]}")
    agent = Agent(
        model=load_model(temperature=0.0),
        system_prompt=TRIAGE_PROMPT,
        tools=[],
    )

    try:
        result = agent(user_request)
        text = str(result).strip()
        lines = text.split("\n", 1)
        intent_str = lines[0].strip().upper()
        reasoning = lines[1].strip() if len(lines) > 1 else ""

        intent_map = {
            "QUERY": Intent.QUERY,
            "ANALYSIS": Intent.ANALYSIS,
            "ACTION": Intent.ACTION,
            "MIXED": Intent.MIXED,
        }
        intent = intent_map.get(intent_str, Intent.QUERY)
        logger.info(f"[TRIAGE] Intent={intent.value}, Reasoning={reasoning[:120]}")
        return intent, reasoning
    except Exception as e:
        logger.error(f"[TRIAGE] Error: {e}")
        return Intent.QUERY, f"Triage failed, defaulting to QUERY: {e}"


# ---------------------------------------------------------------------------
# Analysis Agent (read-only MCP tools)
# ---------------------------------------------------------------------------

ANALYSIS_PROMPT = """You are an Analysis Agent for a project management system.

Your role:
- Search and retrieve tasks, projects, and user information
- Compute metrics (task counts, workload distribution, completion rates)
- Generate structured reports and summaries
- Identify patterns (overdue tasks, blocked items, overloaded team members)

Guidelines:
- Be thorough: gather all data before forming conclusions
- Present findings with numbers and specific data points
- When analyzing workload, count tasks by status for each user
"""


@tool
def analysis_agent(query: str) -> str:
    """Analyze project data, compute metrics, generate reports, and retrieve information.

    Use for: searching tasks, getting statistics, comparing workloads,
    project health reports, and any read-only data operations.

    Args:
        query: The analysis question or data retrieval request.
    """
    logger.info(f"[ANALYSIS] Processing: {query[:100]}")
    agent = Agent(
        model=load_model(),
        system_prompt=ANALYSIS_PROMPT,
        tools=READ_TOOLS,
    )

    try:
        response = agent(query)
        return str(response)
    except Exception as e:
        logger.error(f"[ANALYSIS] Error: {e}")
        return f"Analysis error: {e}"


# ---------------------------------------------------------------------------
# Action Agent (write MCP tools)
# ---------------------------------------------------------------------------

ACTION_PROMPT = """You are an Action Agent for a project management system.

Your role:
- Create new tasks
- Update task fields (status, priority, description, due date)
- Assign or reassign tasks to users
- Add comments to tasks

Guidelines:
- Verify user/task IDs before making changes (use list_users, search_tasks for lookups)
- Report what was changed after each operation
- Process bulk operations one at a time and report results
"""


@tool
def action_agent(instruction: str) -> str:
    """Execute write operations on the project management system.

    Use for: creating tasks, updating tasks, reassigning tasks, adding comments,
    and any operations that modify data.

    Args:
        instruction: The action to perform, including any context from prior analysis.
    """
    logger.info(f"[ACTION] Processing: {instruction[:100]}")
    agent = Agent(
        model=load_model(),
        system_prompt=ACTION_PROMPT,
        tools=WRITE_TOOLS,
    )

    try:
        response = agent(instruction)
        return str(response)
    except Exception as e:
        logger.error(f"[ACTION] Error: {e}")
        return f"Action error: {e}"
