"""Seed the database with realistic sample data for the project management system."""

import sys
import os
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv

load_dotenv()

from shared.db import init_db, get_session
from shared.models import (
    Comment,
    Project,
    ProjectStatus,
    Task,
    TaskPriority,
    TaskStatus,
    User,
    UserRole,
)


def seed():
    """Populate the database with realistic sample data."""
    init_db()
    session = get_session()

    # Clear existing data
    session.query(Comment).delete()
    session.query(Task).delete()
    session.query(User).delete()
    session.query(Project).delete()
    session.commit()

    # ---- Projects (4) ----
    projects = [
        Project(
            name="Project Alpha",
            description="Core platform API redesign and migration to microservices architecture.",
            status=ProjectStatus.active,
            created_at=datetime(2025, 1, 10, tzinfo=timezone.utc),
        ),
        Project(
            name="Project Beta",
            description="Customer-facing mobile application with real-time collaboration features.",
            status=ProjectStatus.active,
            created_at=datetime(2025, 2, 1, tzinfo=timezone.utc),
        ),
        Project(
            name="Project Gamma",
            description="Internal analytics dashboard for business intelligence and reporting.",
            status=ProjectStatus.active,
            created_at=datetime(2025, 3, 5, tzinfo=timezone.utc),
        ),
        Project(
            name="Legacy Migration",
            description="Migration of legacy monolith to cloud-native infrastructure. Completed Q4 2024.",
            status=ProjectStatus.archived,
            created_at=datetime(2024, 6, 1, tzinfo=timezone.utc),
        ),
    ]
    session.add_all(projects)
    session.flush()

    # ---- Users (12) ----
    users = [
        User(name="Alice Johnson", email="alice@company.com", role=UserRole.manager),
        User(name="Bob Smith", email="bob@company.com", role=UserRole.developer),
        User(name="Carol Williams", email="carol@company.com", role=UserRole.developer),
        User(name="David Brown", email="david@company.com", role=UserRole.developer),
        User(name="Eve Davis", email="eve@company.com", role=UserRole.designer),
        User(name="Frank Miller", email="frank@company.com", role=UserRole.qa),
        User(name="Grace Lee", email="grace@company.com", role=UserRole.developer),
        User(name="Henry Wilson", email="henry@company.com", role=UserRole.qa),
        User(name="Ivy Chen", email="ivy@company.com", role=UserRole.designer),
        User(name="Jack Taylor", email="jack@company.com", role=UserRole.manager),
        User(name="Karen White", email="karen@company.com", role=UserRole.developer),
        User(name="Leo Martinez", email="leo@company.com", role=UserRole.developer),
    ]
    session.add_all(users)
    session.flush()

    now = datetime.now(timezone.utc)

    # ---- Tasks (35) ----
    tasks = [
        # --- Project Alpha (12 tasks) ---
        Task(
            project_id=projects[0].id, title="Design new REST API schema",
            description="Create OpenAPI spec for the v2 REST API including all endpoints and data models.",
            status=TaskStatus.done, priority=TaskPriority.high,
            assignee_id=users[1].id, due_date=now - timedelta(days=10),
            created_at=now - timedelta(days=30),
        ),
        Task(
            project_id=projects[0].id, title="Implement authentication service",
            description="Build JWT-based auth service with refresh tokens and OAuth2 support.",
            status=TaskStatus.in_progress, priority=TaskPriority.critical,
            assignee_id=users[2].id, due_date=now + timedelta(days=5),
            created_at=now - timedelta(days=20),
        ),
        Task(
            project_id=projects[0].id, title="Set up CI/CD pipeline",
            description="Configure GitHub Actions for automated testing, linting, and deployment.",
            status=TaskStatus.done, priority=TaskPriority.high,
            assignee_id=users[3].id, due_date=now - timedelta(days=5),
            created_at=now - timedelta(days=25),
        ),
        Task(
            project_id=projects[0].id, title="Database migration scripts",
            description="Write Alembic migration scripts for the new schema changes.",
            status=TaskStatus.blocked, priority=TaskPriority.high,
            assignee_id=users[6].id, due_date=now - timedelta(days=2),
            created_at=now - timedelta(days=15),
        ),
        Task(
            project_id=projects[0].id, title="Load testing",
            description="Run load tests with k6 to validate API performance under 10k concurrent users.",
            status=TaskStatus.todo, priority=TaskPriority.medium,
            assignee_id=users[5].id, due_date=now + timedelta(days=15),
            created_at=now - timedelta(days=10),
        ),
        Task(
            project_id=projects[0].id, title="Write API documentation",
            description="Generate and review auto-generated API docs. Add usage examples.",
            status=TaskStatus.todo, priority=TaskPriority.low,
            assignee_id=users[1].id, due_date=now + timedelta(days=20),
            created_at=now - timedelta(days=8),
        ),
        Task(
            project_id=projects[0].id, title="Implement rate limiting",
            description="Add rate limiting middleware to protect API endpoints from abuse.",
            status=TaskStatus.in_progress, priority=TaskPriority.high,
            assignee_id=users[10].id, due_date=now + timedelta(days=3),
            created_at=now - timedelta(days=12),
        ),
        Task(
            project_id=projects[0].id, title="Security audit",
            description="Conduct security review of all new endpoints. Check for OWASP Top 10 vulnerabilities.",
            status=TaskStatus.blocked, priority=TaskPriority.critical,
            assignee_id=users[7].id, due_date=now - timedelta(days=1),
            created_at=now - timedelta(days=14),
        ),
        Task(
            project_id=projects[0].id, title="Implement caching layer",
            description="Add Redis caching for frequently accessed endpoints to reduce DB load.",
            status=TaskStatus.todo, priority=TaskPriority.medium,
            assignee_id=users[11].id, due_date=now + timedelta(days=10),
            created_at=now - timedelta(days=7),
        ),
        Task(
            project_id=projects[0].id, title="API versioning strategy",
            description="Define and implement API versioning approach (URL path vs header).",
            status=TaskStatus.done, priority=TaskPriority.medium,
            assignee_id=users[2].id, due_date=now - timedelta(days=15),
            created_at=now - timedelta(days=28),
        ),
        Task(
            project_id=projects[0].id, title="Error handling standardization",
            description="Implement consistent error response format across all API endpoints.",
            status=TaskStatus.in_progress, priority=TaskPriority.medium,
            assignee_id=users[3].id, due_date=now + timedelta(days=7),
            created_at=now - timedelta(days=9),
        ),
        Task(
            project_id=projects[0].id, title="Monitoring and alerting setup",
            description="Configure CloudWatch alarms and Datadog dashboards for the new services.",
            status=TaskStatus.todo, priority=TaskPriority.high,
            assignee_id=users[6].id, due_date=now + timedelta(days=12),
            created_at=now - timedelta(days=5),
        ),
        # --- Project Beta (12 tasks) ---
        Task(
            project_id=projects[1].id, title="Design mobile UI wireframes",
            description="Create wireframes for all main screens including home, chat, and settings.",
            status=TaskStatus.done, priority=TaskPriority.high,
            assignee_id=users[4].id, due_date=now - timedelta(days=20),
            created_at=now - timedelta(days=35),
        ),
        Task(
            project_id=projects[1].id, title="Implement real-time chat",
            description="Build WebSocket-based real-time chat with message persistence and read receipts.",
            status=TaskStatus.in_progress, priority=TaskPriority.critical,
            assignee_id=users[2].id, due_date=now + timedelta(days=8),
            created_at=now - timedelta(days=18),
        ),
        Task(
            project_id=projects[1].id, title="Push notification service",
            description="Integrate Firebase Cloud Messaging for iOS and Android push notifications.",
            status=TaskStatus.blocked, priority=TaskPriority.high,
            assignee_id=users[3].id, due_date=now + timedelta(days=2),
            created_at=now - timedelta(days=16),
        ),
        Task(
            project_id=projects[1].id, title="User profile management",
            description="Build profile editing screen with avatar upload and preference settings.",
            status=TaskStatus.in_progress, priority=TaskPriority.medium,
            assignee_id=users[8].id, due_date=now + timedelta(days=6),
            created_at=now - timedelta(days=14),
        ),
        Task(
            project_id=projects[1].id, title="Offline mode support",
            description="Implement local storage sync for offline access to messages and data.",
            status=TaskStatus.todo, priority=TaskPriority.medium,
            assignee_id=users[6].id, due_date=now + timedelta(days=25),
            created_at=now - timedelta(days=10),
        ),
        Task(
            project_id=projects[1].id, title="App store submission prep",
            description="Prepare screenshots, descriptions, and metadata for iOS App Store and Google Play.",
            status=TaskStatus.todo, priority=TaskPriority.low,
            assignee_id=users[4].id, due_date=now + timedelta(days=30),
            created_at=now - timedelta(days=5),
        ),
        Task(
            project_id=projects[1].id, title="Beta testing coordination",
            description="Organize TestFlight and Play Console beta testing groups. Collect feedback.",
            status=TaskStatus.todo, priority=TaskPriority.medium,
            assignee_id=users[5].id, due_date=now + timedelta(days=18),
            created_at=now - timedelta(days=8),
        ),
        Task(
            project_id=projects[1].id, title="Accessibility compliance",
            description="Ensure WCAG 2.1 AA compliance for all screens. Fix color contrast and screen reader issues.",
            status=TaskStatus.blocked, priority=TaskPriority.high,
            assignee_id=users[8].id, due_date=now - timedelta(days=3),
            created_at=now - timedelta(days=12),
        ),
        Task(
            project_id=projects[1].id, title="Performance optimization",
            description="Optimize app startup time and reduce memory usage. Target < 2s cold start.",
            status=TaskStatus.todo, priority=TaskPriority.high,
            assignee_id=users[11].id, due_date=now + timedelta(days=14),
            created_at=now - timedelta(days=6),
        ),
        Task(
            project_id=projects[1].id, title="Integration tests for chat",
            description="Write integration tests covering message send/receive, media sharing, and group chat.",
            status=TaskStatus.in_progress, priority=TaskPriority.medium,
            assignee_id=users[7].id, due_date=now + timedelta(days=10),
            created_at=now - timedelta(days=9),
        ),
        Task(
            project_id=projects[1].id, title="Implement file sharing",
            description="Add ability to share documents, images, and files within chat conversations.",
            status=TaskStatus.todo, priority=TaskPriority.medium,
            assignee_id=users[10].id, due_date=now + timedelta(days=20),
            created_at=now - timedelta(days=4),
        ),
        # --- Project Gamma (11 tasks) ---
        Task(
            project_id=projects[2].id, title="Design dashboard layout",
            description="Create responsive dashboard layout with widget-based components and dark mode.",
            status=TaskStatus.done, priority=TaskPriority.high,
            assignee_id=users[4].id, due_date=now - timedelta(days=8),
            created_at=now - timedelta(days=22),
        ),
        Task(
            project_id=projects[2].id, title="Data pipeline integration",
            description="Connect to Snowflake data warehouse and set up ETL pipelines for metrics.",
            status=TaskStatus.in_progress, priority=TaskPriority.critical,
            assignee_id=users[11].id, due_date=now + timedelta(days=4),
            created_at=now - timedelta(days=15),
        ),
        Task(
            project_id=projects[2].id, title="Build chart components",
            description="Implement reusable chart components (bar, line, pie, heatmap) using D3.js.",
            status=TaskStatus.in_progress, priority=TaskPriority.high,
            assignee_id=users[1].id, due_date=now + timedelta(days=7),
            created_at=now - timedelta(days=12),
        ),
        Task(
            project_id=projects[2].id, title="Export to PDF/CSV",
            description="Add ability to export dashboard reports to PDF and CSV formats.",
            status=TaskStatus.todo, priority=TaskPriority.medium,
            assignee_id=users[10].id, due_date=now + timedelta(days=15),
            created_at=now - timedelta(days=8),
        ),
        Task(
            project_id=projects[2].id, title="Role-based access control",
            description="Implement RBAC so different user roles see different dashboards and data.",
            status=TaskStatus.blocked, priority=TaskPriority.high,
            assignee_id=users[2].id, due_date=now + timedelta(days=1),
            created_at=now - timedelta(days=11),
        ),
        Task(
            project_id=projects[2].id, title="Real-time data refresh",
            description="Implement WebSocket-based real-time updates for dashboard metrics.",
            status=TaskStatus.todo, priority=TaskPriority.medium,
            assignee_id=users[3].id, due_date=now + timedelta(days=20),
            created_at=now - timedelta(days=6),
        ),
        Task(
            project_id=projects[2].id, title="Scheduled report emails",
            description="Build a scheduler for sending weekly/monthly report emails to stakeholders.",
            status=TaskStatus.todo, priority=TaskPriority.low,
            assignee_id=users[6].id, due_date=now + timedelta(days=25),
            created_at=now - timedelta(days=4),
        ),
        Task(
            project_id=projects[2].id, title="Dashboard QA testing",
            description="Complete end-to-end testing of all dashboard features and data accuracy.",
            status=TaskStatus.todo, priority=TaskPriority.high,
            assignee_id=users[5].id, due_date=now + timedelta(days=12),
            created_at=now - timedelta(days=3),
        ),
        Task(
            project_id=projects[2].id, title="User onboarding walkthrough",
            description="Create interactive onboarding tour for new dashboard users.",
            status=TaskStatus.todo, priority=TaskPriority.low,
            assignee_id=users[8].id, due_date=now + timedelta(days=28),
            created_at=now - timedelta(days=2),
        ),
        Task(
            project_id=projects[2].id, title="Alert configuration UI",
            description="Build UI for users to configure custom metric alerts and thresholds.",
            status=TaskStatus.in_progress, priority=TaskPriority.medium,
            assignee_id=users[10].id, due_date=now + timedelta(days=9),
            created_at=now - timedelta(days=7),
        ),
    ]
    session.add_all(tasks)
    session.flush()

    # ---- Comments (25) ----
    comments = [
        # Task 0 - Design new REST API schema
        Comment(task_id=tasks[0].id, user_id=users[0].id, content="Great work on the API schema. The resource structure is clean and follows REST best practices.", created_at=now - timedelta(days=12)),
        Comment(task_id=tasks[0].id, user_id=users[1].id, content="Thanks! I've added pagination support to all list endpoints as discussed.", created_at=now - timedelta(days=11)),

        # Task 1 - Implement authentication service
        Comment(task_id=tasks[1].id, user_id=users[2].id, content="OAuth2 flow is working. Still need to implement refresh token rotation.", created_at=now - timedelta(days=5)),
        Comment(task_id=tasks[1].id, user_id=users[0].id, content="Make sure we support both authorization code and client credentials grant types.", created_at=now - timedelta(days=4)),

        # Task 3 - Database migration scripts (blocked)
        Comment(task_id=tasks[3].id, user_id=users[6].id, content="Blocked by the auth service - need the final user schema before writing migrations.", created_at=now - timedelta(days=3)),
        Comment(task_id=tasks[3].id, user_id=users[0].id, content="Let's sync with Carol to get an ETA on the user schema finalization.", created_at=now - timedelta(days=2)),

        # Task 7 - Security audit (blocked)
        Comment(task_id=tasks[7].id, user_id=users[7].id, content="Cannot proceed with security audit until the auth service and rate limiting are complete.", created_at=now - timedelta(days=3)),
        Comment(task_id=tasks[7].id, user_id=users[5].id, content="I can help with the OWASP testing once the endpoints are stable.", created_at=now - timedelta(days=2)),

        # Task 10 - Error handling standardization
        Comment(task_id=tasks[10].id, user_id=users[3].id, content="Proposing we use RFC 7807 Problem Details format for all error responses.", created_at=now - timedelta(days=4)),
        Comment(task_id=tasks[10].id, user_id=users[2].id, content="Agreed. That's the industry standard. I'll align the auth service errors too.", created_at=now - timedelta(days=3)),

        # Task 13 - Implement real-time chat
        Comment(task_id=tasks[13].id, user_id=users[2].id, content="WebSocket connection pooling is implemented. Working on message ordering guarantees.", created_at=now - timedelta(days=6)),
        Comment(task_id=tasks[13].id, user_id=users[9].id, content="Can we get a demo of the current state in Friday's standup?", created_at=now - timedelta(days=5)),
        Comment(task_id=tasks[13].id, user_id=users[2].id, content="Sure! I'll prepare a demo showing the real-time message sync.", created_at=now - timedelta(days=4)),

        # Task 14 - Push notification service (blocked)
        Comment(task_id=tasks[14].id, user_id=users[3].id, content="Blocked: waiting for Firebase project setup and API keys from DevOps.", created_at=now - timedelta(days=7)),
        Comment(task_id=tasks[14].id, user_id=users[0].id, content="I've escalated the Firebase setup request. Should be resolved by end of week.", created_at=now - timedelta(days=5)),

        # Task 19 - Accessibility compliance (blocked)
        Comment(task_id=tasks[19].id, user_id=users[8].id, content="Color contrast issues found on 5 screens. Also need to add ARIA labels to dynamic content.", created_at=now - timedelta(days=4)),
        Comment(task_id=tasks[19].id, user_id=users[4].id, content="I'll update the design tokens. The dark mode palette needs higher contrast ratios.", created_at=now - timedelta(days=3)),

        # Task 24 - Data pipeline integration
        Comment(task_id=tasks[24].id, user_id=users[11].id, content="Snowflake connection is established. Working on the ETL scheduling with Airflow.", created_at=now - timedelta(days=5)),
        Comment(task_id=tasks[24].id, user_id=users[9].id, content="Priority metrics: revenue, MAU, churn rate, and feature adoption. Please start with these.", created_at=now - timedelta(days=4)),

        # Task 27 - Role-based access control (blocked)
        Comment(task_id=tasks[27].id, user_id=users[2].id, content="Blocked: need the final RBAC spec from the product team before implementation.", created_at=now - timedelta(days=3)),
        Comment(task_id=tasks[27].id, user_id=users[9].id, content="The spec should be finalized this week. I'll share it as soon as it's approved.", created_at=now - timedelta(days=2)),

        # Task 25 - Build chart components
        Comment(task_id=tasks[25].id, user_id=users[1].id, content="Bar and line charts are done. Starting on heatmap visualization next.", created_at=now - timedelta(days=3)),

        # Task 6 - Implement rate limiting
        Comment(task_id=tasks[6].id, user_id=users[10].id, content="Using token bucket algorithm. Default: 100 req/min per user, 1000 req/min per API key.", created_at=now - timedelta(days=4)),
        Comment(task_id=tasks[6].id, user_id=users[0].id, content="Good defaults. Make sure we can override per-endpoint via config.", created_at=now - timedelta(days=3)),

        # Task 15 - User profile management
        Comment(task_id=tasks[15].id, user_id=users[8].id, content="Profile page design is complete. Implementing the avatar crop/upload component now.", created_at=now - timedelta(days=3)),
        Comment(task_id=tasks[15].id, user_id=users[4].id, content="Looking great! Let's make sure we support WebP format for smaller file sizes.", created_at=now - timedelta(days=2)),
    ]
    session.add_all(comments)
    session.commit()

    print(f"✅ Seeded: {len(projects)} projects, {len(users)} users, {len(tasks)} tasks, {len(comments)} comments")
    session.close()


if __name__ == "__main__":
    seed()
