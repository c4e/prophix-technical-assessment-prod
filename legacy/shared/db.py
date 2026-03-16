"""SQLAlchemy database connection and session management."""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://pm_user:pm_password@localhost:5434/project_management",
)

engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(bind=engine)


class Base(DeclarativeBase):
    pass


def get_session():
    """Get a new database session."""
    return SessionLocal()


def init_db():
    """Create all tables."""
    from shared.models import Project, Task, User, Comment

    Base.metadata.create_all(bind=engine)
