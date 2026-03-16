# Exercise 1: MCP Server for Project Management

## Overview

An MCP (Model Context Protocol) server that exposes project management tools over **stdio** transport. Built with the official [Python MCP SDK](https://github.com/modelcontextprotocol/python-sdk) (`FastMCP`) and backed by **PostgreSQL** via **SQLAlchemy**.

## Architecture

```
MCP Client (stdio) ←→ FastMCP Server → SQLAlchemy ORM → PostgreSQL
```

## Tools Exposed

| Tool | Description |
|------|-------------|
| `search_tasks` | Search tasks with filters (project, status, priority, assignee, keyword) |
| `get_task_details` | Get full task info including comments |
| `create_task` | Create a new task in a project |
| `update_task` | Update one or more task fields |
| `assign_task` | Assign/reassign a task to a user |
| `add_comment` | Add a comment to a task |
| `get_project_summary` | Get project stats (counts by status/priority, overdue tasks) |
| `list_users` | List all users with optional role filter |

## Setup & Run

### Prerequisites
- Docker & Docker Compose
- Python 3.11+

### 1. Start PostgreSQL
```bash
# From the project root
docker compose up -d
```

### 2. Install dependencies
```bash
pip install -e .
# or
pip install sqlalchemy psycopg2-binary mcp python-dotenv pydantic
```

### 3. Seed the database
```bash
python shared/seed_data.py
```

### 4. Run the MCP Server
```bash
python exercise-1/src/server.py
```
The server runs on **stdio** — it reads JSON-RPC messages from stdin and writes responses to stdout.

## Verification

### Using MCP Inspector
```bash
npx @modelcontextprotocol/inspector python exercise-1/src/server.py
```
This opens a web UI where you can browse tools and invoke them interactively.

### Programmatic test
```bash
# List tools
echo '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | python exercise-1/src/server.py
```

## Design Decisions

- **SQLAlchemy ORM**: Most popular Python ORM — mature, well-documented, supports complex queries
- **PostgreSQL**: Production-grade RDBMS with proper constraints and ACID compliance
- **FastMCP**: Official Python SDK convenience wrapper — handles JSON-RPC protocol, tool registration, and schema generation automatically
- **Structured error responses**: All errors return JSON `{"error": "..."}` rather than raising exceptions, so LLM agents get useful feedback
