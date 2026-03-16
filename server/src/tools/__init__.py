"""Database connection and session management."""

import os
import threading

from dotenv import load_dotenv
load_dotenv(override=True)

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://pm_user:pm_password@localhost:5434/project_management",
  )

engine = create_engine(
    DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    connect_args={"connect_timeout": 5},
)
SessionLocal = sessionmaker(bind=engine)


class Base(DeclarativeBase):
    pass


_db_ready = False
_db_lock = threading.Lock()


def _ensure_tables():
    """Create tables once, on first use."""
    global _db_ready
    if _db_ready:
        return
    with _db_lock:
        if _db_ready:
            return
        from .models import Project, Task, User, Comment  # noqa: F401
        Base.metadata.create_all(bind=engine)
        _db_ready = True


def get_session():
    """Return a new database session (creates tables on first call)."""
    _ensure_tables()
    return SessionLocal()


def init_db():
    """Explicit table creation — optional, used for local dev."""
    _ensure_tables()
