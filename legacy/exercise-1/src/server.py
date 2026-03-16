"""MCP Server for the Project Management system.

Exposes tools for CRUD operations on projects, tasks, users, and comments
via the Model Context Protocol (MCP) using the FastMCP Python SDK.
Transport: stdio (default).
"""

import json
import sys
import os
from datetime import datetime, timezone

from dotenv import load_dotenv

load_dotenv()

from mcp.server import FastMCP
from sqlalchemy import or_

from shared.db import get_session, init_db
from shared.models import (
    Comment,
    Project,
    Task,
    TaskPriority,
    TaskStatus,
    User,
    UserRole,
)

# ---------------------------------------------------------------------------
# Server
# ---------------------------------------------------------------------------

mcp = FastMCP(
    "Project Management MCP Server",
    instructions=(
        "MCP server exposing project management tools."
        "Use these tools to search, create, update, and query tasks, projects, users, and comments."
    ),
)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _json(obj) -> str:
    """Serialize a dict/list to a compact JSON string."""
    return json.dumps(obj, default=str, indent=2)


def _error(msg: str) -> str:
    return _json({"error": msg})


def _resolve_project(session, project_id: int | None, project_name: str | None):
    """Resolve a project from either an ID or a name. Returns (project, error_str)."""
    if project_id is not None:
        proj = session.get(Project, project_id)
        if not proj:
            return None, f"Project with id {project_id} not found."
        return proj, None
    if project_name is not None:
        proj = session.query(Project).filter(Project.name.ilike(project_name)).first()
        if not proj:
            # Try partial match
            proj = session.query(Project).filter(Project.name.ilike(f"%{project_name}%")).first()
        if not proj:
            return None, f"Project '{project_name}' not found."
        return proj, None
    return None, "Either project_id or project_name must be provided."


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@mcp.tool(description="Search tasks with optional filters. Returns a list of matching tasks.")
def search_tasks(
    project_id: int | None = None,
    project_name: str | None = None,
    status: str | None = None,
    priority: str | None = None,
    assignee_id: int | None = None,
    keyword: str | None = None,
) -> str:
    """Search tasks with filters.

    Args:
        project_id: Filter by project ID.
        project_name: Filter by project name (alternative to project_id).
        status: Filter by status (todo, in_progress, done, blocked).
        priority: Filter by priority (low, medium, high, critical).
        assignee_id: Filter by assignee user ID.
        keyword: Search keyword in task title or description.
    """
    session = get_session()
    try:
        q = session.query(Task)
        if project_id is not None or project_name is not None:
            proj, err = _resolve_project(session, project_id, project_name)
            if err:
                return _error(err)
            q = q.filter(Task.project_id == proj.id)
        if status is not None:
            try:
                TaskStatus(status)
            except ValueError:
                return _error(f"Invalid status '{status}'. Must be one of: todo, in_progress, done, blocked.")
            q = q.filter(Task.status == status)
        if priority is not None:
            try:
                TaskPriority(priority)
            except ValueError:
                return _error(f"Invalid priority '{priority}'. Must be one of: low, medium, high, critical.")
            q = q.filter(Task.priority == priority)
        if assignee_id is not None:
            user = session.get(User, assignee_id)
            if not user:
                return _error(f"User with id {assignee_id} not found.")
            q = q.filter(Task.assignee_id == assignee_id)
        if keyword:
            pattern = f"%{keyword}%"
            q = q.filter(or_(Task.title.ilike(pattern), Task.description.ilike(pattern)))
        tasks = q.order_by(Task.created_at.desc()).all()
        return _json({"count": len(tasks), "tasks": [t.to_dict() for t in tasks]})
    finally:
        session.close()


@mcp.tool(description="Get full details of a task including its comments.")
def get_task_details(task_id: int) -> str:
    """Get full task info including comments.

    Args:
        task_id: The ID of the task to retrieve.
    """
    session = get_session()
    try:
        task = session.get(Task, task_id)
        if not task:
            return _error(f"Task with id {task_id} not found.")
        data = task.to_dict()
        data["project_name"] = task.project.name if task.project else None
        data["comments"] = [c.to_dict() for c in task.comments]
        return _json(data)
    finally:
        session.close()


@mcp.tool(description="Create a new task in a project. Use project_name or project_id to specify the project.")
def create_task(
    title: str,
    description: str,
    priority: str,
    project_id: int | None = None,
    project_name: str | None = None,
    assignee_id: int | None = None,
    due_date: str | None = None,
) -> str:
    """Create a new task.

    Args:
        title: Task title.
        description: Task description.
        priority: Task priority (low, medium, high, critical).
        project_id: The project ID to create the task in.
        project_name: The project name (alternative to project_id).
        assignee_id: Optional user ID to assign the task to.
        due_date: Optional due date in ISO format (YYYY-MM-DD).
    """
    session = get_session()
    try:
        project, err = _resolve_project(session, project_id, project_name)
        if err:
            return _error(err)
        try:
            TaskPriority(priority)
        except ValueError:
            return _error(f"Invalid priority '{priority}'. Must be one of: low, medium, high, critical.")
        if assignee_id is not None:
            user = session.get(User, assignee_id)
            if not user:
                return _error(f"User with id {assignee_id} not found.")
        parsed_due = None
        if due_date:
            try:
                parsed_due = datetime.fromisoformat(due_date).replace(tzinfo=timezone.utc)
            except ValueError:
                return _error(f"Invalid due_date format '{due_date}'. Use ISO format (YYYY-MM-DD).")
        task = Task(
            project_id=project.id,
            title=title,
            description=description,
            priority=TaskPriority(priority),
            status=TaskStatus.todo,
            assignee_id=assignee_id,
            due_date=parsed_due,
        )
        session.add(task)
        session.commit()
        session.refresh(task)
        return _json({"message": "Task created successfully.", "task": task.to_dict()})
    finally:
        session.close()


@mcp.tool(description="Update one or more fields of an existing task.")
def update_task(
    task_id: int,
    title: str | None = None,
    description: str | None = None,
    status: str | None = None,
    priority: str | None = None,
    assignee_id: int | None = None,
    due_date: str | None = None,
) -> str:
    """Update task fields.

    Args:
        task_id: The ID of the task to update.
        title: New title (optional).
        description: New description (optional).
        status: New status (optional): todo, in_progress, done, blocked.
        priority: New priority (optional): low, medium, high, critical.
        assignee_id: New assignee user ID (optional).
        due_date: New due date in ISO format (optional).
    """
    session = get_session()
    try:
        task = session.get(Task, task_id)
        if not task:
            return _error(f"Task with id {task_id} not found.")
        if title is not None:
            task.title = title
        if description is not None:
            task.description = description
        if status is not None:
            try:
                task.status = TaskStatus(status)
            except ValueError:
                return _error(f"Invalid status '{status}'. Must be one of: todo, in_progress, done, blocked.")
        if priority is not None:
            try:
                task.priority = TaskPriority(priority)
            except ValueError:
                return _error(f"Invalid priority '{priority}'. Must be one of: low, medium, high, critical.")
        if assignee_id is not None:
            user = session.get(User, assignee_id)
            if not user:
                return _error(f"User with id {assignee_id} not found.")
            task.assignee_id = assignee_id
        if due_date is not None:
            try:
                task.due_date = datetime.fromisoformat(due_date).replace(tzinfo=timezone.utc)
            except ValueError:
                return _error(f"Invalid due_date format '{due_date}'. Use ISO format (YYYY-MM-DD).")
        task.updated_at = datetime.now(timezone.utc)
        session.commit()
        session.refresh(task)
        return _json({"message": "Task updated successfully.", "task": task.to_dict()})
    finally:
        session.close()


@mcp.tool(description="Assign or reassign a task to a user.")
def assign_task(task_id: int, assignee_id: int) -> str:
    """Assign/reassign a task to a user.

    Args:
        task_id: The ID of the task to assign.
        assignee_id: The user ID to assign the task to.
    """
    session = get_session()
    try:
        task = session.get(Task, task_id)
        user = session.get(User, assignee_id)
        errors = []
        if not task:
            errors.append(f"Task with id {task_id} not found.")
        if not user:
            errors.append(f"User with id {assignee_id} not found.")
        if errors:
            return _error(" ".join(errors))
        old_assignee = task.assignee.name if task.assignee else "unassigned"
        task.assignee_id = assignee_id
        task.updated_at = datetime.now(timezone.utc)
        session.commit()
        session.refresh(task)
        return _json({
            "message": f"Task '{task.title}' reassigned from {old_assignee} to {user.name}.",
            "task": task.to_dict(),
        })
    finally:
        session.close()


@mcp.tool(description="Add a comment to a task.")
def add_comment(task_id: int, user_id: int, content: str) -> str:
    """Add a comment to a task.

    Args:
        task_id: The task to comment on.
        user_id: The user posting the comment.
        content: The comment text.
    """
    session = get_session()
    try:
        task = session.get(Task, task_id)
        if not task:
            return _error(f"Task with id {task_id} not found.")
        user = session.get(User, user_id)
        if not user:
            return _error(f"User with id {user_id} not found.")
        if not content or not content.strip():
            return _error("Comment content cannot be empty.")
        comment = Comment(task_id=task_id, user_id=user_id, content=content.strip())
        session.add(comment)
        session.commit()
        session.refresh(comment)
        return _json({"message": "Comment added successfully.", "comment": comment.to_dict()})
    finally:
        session.close()


@mcp.tool(description="Get a summary of a project including task statistics. Use project_name or project_id.")
def get_project_summary(project_id: int | None = None, project_name: str | None = None) -> str:
    """Get project stats: task counts by status and priority, overdue tasks, etc.

    Args:
        project_id: The project ID to summarize.
        project_name: The project name (alternative to project_id).
    """
    session = get_session()
    try:
        project, err = _resolve_project(session, project_id, project_name)
        if err:
            return _error(err)
        tasks = session.query(Task).filter(Task.project_id == project.id).all()
        now = datetime.now(timezone.utc)
        by_status = {}
        by_priority = {}
        overdue = []
        for t in tasks:
            by_status[t.status.value] = by_status.get(t.status.value, 0) + 1
            by_priority[t.priority.value] = by_priority.get(t.priority.value, 0) + 1
            if t.due_date and t.due_date.replace(tzinfo=timezone.utc) < now and t.status.value not in ("done",):
                overdue.append(t.to_dict())
        summary = {
            "project": project.to_dict(),
            "total_tasks": len(tasks),
            "tasks_by_status": by_status,
            "tasks_by_priority": by_priority,
            "overdue_tasks": {"count": len(overdue), "tasks": overdue},
        }
        return _json(summary)
    finally:
        session.close()


@mcp.tool(description="List all users, optionally filtered by role.")
def list_users(role: str | None = None) -> str:
    """List all users with optional role filter.

    Args:
        role: Optional role filter (developer, designer, manager, qa).
    """
    session = get_session()
    try:
        q = session.query(User)
        if role is not None:
            try:
                UserRole(role)
            except ValueError:
                return _error(f"Invalid role '{role}'. Must be one of: developer, designer, manager, qa.")
            q = q.filter(User.role == role)
        users = q.order_by(User.name).all()
        return _json({"count": len(users), "users": [u.to_dict() for u in users]})
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Ensure tables exist
    init_db()
    # Run MCP server over stdio
    mcp.run(transport="stdio")
