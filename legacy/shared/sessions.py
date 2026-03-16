"""Shared session management helpers.

Provides a centralised way to create Strands FileSessionManager instances
and manage session lifecycle (create, delete) so that every exercise uses
the same conventions.

Usage:
    from shared.sessions import create_session_manager, new_session_id, delete_session

    sm = create_session_manager(session_id, storage_dir)
    agent = Agent(..., session_manager=sm)
"""

import os
import shutil
import uuid

from strands.session.file_session_manager import FileSessionManager


def new_session_id() -> str:
    """Generate a new unique session id."""
    return str(uuid.uuid4())


def create_session_manager(
    session_id: str | None = None,
    storage_dir: str | None = None,
) -> tuple[str, FileSessionManager]:
    """Create a FileSessionManager for the given session.

    Args:
        session_id:  Existing id to resume, or ``None`` to start a new session.
        storage_dir: Directory where session files are stored.
                     Defaults to ``<project_root>/sessions``.

    Returns:
        A ``(session_id, FileSessionManager)`` tuple.
    """
    if not session_id:
        session_id = new_session_id()

    if not storage_dir:
        # Default: <project_root>/sessions
        storage_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "sessions",
        )

    os.makedirs(storage_dir, exist_ok=True)

    session_manager = FileSessionManager(
        session_id=session_id,
        storage_dir=storage_dir,
    )

    return session_id, session_manager


def delete_session(session_id: str, storage_dir: str | None = None) -> bool:
    """Delete a persisted session from disk.

    Returns ``True`` if a session directory was found and removed.
    """
    if not storage_dir:
        storage_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "sessions",
        )

    session_dir = os.path.join(storage_dir, f"session_{session_id}")
    if os.path.isdir(session_dir):
        shutil.rmtree(session_dir, ignore_errors=True)
        return True
    return False
