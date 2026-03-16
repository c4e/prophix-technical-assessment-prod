"""Strands @tool wrappers for PM MCP server tools.

Each function calls the deployed MCP server via boto3 invoke_agent_runtime.
Split into read-only and write groups for the Analysis/Action agents.
"""

from strands import tool
from mcp_client.client import call_tool


# ---------------------------------------------------------------------------
# Read-only tools (Analysis Agent)
# ---------------------------------------------------------------------------

@tool
def search_tasks(
    project_id: int | None = None,
    project_name: str | None = None,
    status: str | None = None,
    priority: str | None = None,
    assignee_id: int | None = None,
    keyword: str | None = None,
) -> str:
    """Search tasks with optional filters.

    Args:
        project_id: Filter by project ID.
        project_name: Filter by project name.
        status: Filter by status (todo, in_progress, done, blocked).
        priority: Filter by priority (low, medium, high, critical).
        assignee_id: Filter by assignee user ID.
        keyword: Search keyword in task title or description.
    """
    args = {}
    if project_id is not None:
        args["project_id"] = project_id
    if project_name is not None:
        args["project_name"] = project_name
    if status is not None:
        args["status"] = status
    if priority is not None:
        args["priority"] = priority
    if assignee_id is not None:
        args["assignee_id"] = assignee_id
    if keyword is not None:
        args["keyword"] = keyword
    return call_tool("search_tasks", args)


@tool
def get_task_details(task_id: int) -> str:
    """Get full details of a task including its comments.

    Args:
        task_id: The ID of the task to retrieve.
    """
    return call_tool("get_task_details", {"task_id": task_id})


@tool
def get_project_summary(
    project_id: int | None = None,
    project_name: str | None = None,
) -> str:
    """Get a summary of a project including task statistics.

    Args:
        project_id: The project ID.
        project_name: The project name (alternative to project_id).
    """
    args = {}
    if project_id is not None:
        args["project_id"] = project_id
    if project_name is not None:
        args["project_name"] = project_name
    return call_tool("get_project_summary", args)


@tool
def list_users(role: str | None = None) -> str:
    """List all users, optionally filtered by role.

    Args:
        role: Optional role filter (developer, designer, manager, qa).
    """
    args = {}
    if role is not None:
        args["role"] = role
    return call_tool("list_users", args)


# ---------------------------------------------------------------------------
# Write tools (Action Agent)
# ---------------------------------------------------------------------------

@tool
def create_task(
    title: str,
    priority: str,
    description: str = "",
    project_id: int | None = None,
    project_name: str | None = None,
    assignee_id: int | None = None,
    due_date: str | None = None,
) -> str:
    """Create a new task in a project.

    Args:
        title: Task title.
        priority: Task priority (low, medium, high, critical).
        description: Task description.
        project_id: The project ID.
        project_name: The project name (alternative to project_id).
        assignee_id: User ID to assign the task to.
        due_date: Due date in ISO format (YYYY-MM-DD).
    """
    args = {"title": title, "priority": priority}
    if description:
        args["description"] = description
    if project_id is not None:
        args["project_id"] = project_id
    if project_name is not None:
        args["project_name"] = project_name
    if assignee_id is not None:
        args["assignee_id"] = assignee_id
    if due_date is not None:
        args["due_date"] = due_date
    return call_tool("create_task", args)


@tool
def update_task(
    task_id: int,
    title: str | None = None,
    description: str | None = None,
    status: str | None = None,
    priority: str | None = None,
    assignee_id: int | None = None,
    due_date: str | None = None,
) -> str:
    """Update one or more fields of an existing task.

    Args:
        task_id: The ID of the task.
        title: New title.
        description: New description.
        status: New status (todo, in_progress, done, blocked).
        priority: New priority (low, medium, high, critical).
        assignee_id: New assignee user ID.
        due_date: New due date (YYYY-MM-DD).
    """
    args = {"task_id": task_id}
    if title is not None:
        args["title"] = title
    if description is not None:
        args["description"] = description
    if status is not None:
        args["status"] = status
    if priority is not None:
        args["priority"] = priority
    if assignee_id is not None:
        args["assignee_id"] = assignee_id
    if due_date is not None:
        args["due_date"] = due_date
    return call_tool("update_task", args)


@tool
def assign_task(task_id: int, assignee_id: int) -> str:
    """Assign or reassign a task to a user.

    Args:
        task_id: The ID of the task.
        assignee_id: The user ID to assign to.
    """
    return call_tool("assign_task", {"task_id": task_id, "assignee_id": assignee_id})


@tool
def add_comment(task_id: int, user_id: int, content: str) -> str:
    """Add a comment to a task.

    Args:
        task_id: The task to comment on.
        user_id: The user posting the comment.
        content: The comment text.
    """
    return call_tool("add_comment", {"task_id": task_id, "user_id": user_id, "content": content})


# ---------------------------------------------------------------------------
# Tool groups for agents
# ---------------------------------------------------------------------------

READ_TOOLS = [search_tasks, get_task_details, get_project_summary, list_users]
WRITE_TOOLS = [create_task, update_task, assign_task, add_comment, list_users, search_tasks]
