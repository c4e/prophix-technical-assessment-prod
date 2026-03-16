# Project Management MCP Server

## Overview

A production MCP (Model Context Protocol) server deployed on **AWS Bedrock AgentCore**. Exposes project management tools over **Streamable HTTP** transport. Built with [FastMCP](https://github.com/modelcontextprotocol/python-sdk) and backed by **PostgreSQL** via **SQLAlchemy**.

## Architecture

```
MCP Client (Streamable HTTP)
        ↓
  AgentCore Runtime (0.0.0.0:8000/mcp)
        ↓
  FastMCP Server (stateless_http)
        ↓
  SQLAlchemy ORM → PostgreSQL
```

### Project Structure

```
server/
├── .bedrock_agentcore.yaml   # AgentCore deployment config
├── .env                      # Environment variables (local)
├── pyproject.toml             # Python dependencies
├── requirements.txt
└── src/
    ├── __init__.py
    ├── server.py              # AgentCore entrypoint
    ├── proxy.py               # SigV4 proxy for remote MCP Inspector testing
    ├── mcp_server.py          # FastMCP server with 8 tools
    └── tools/
        ├── __init__.py        # DB engine, session management
        └── models.py          # SQLAlchemy ORM models
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

## Setup

### Prerequisites

- Python 3.11+
- PostgreSQL (local via Docker or remote)
- AWS CLI configured with `bbl-training-prod` profile
- [AgentCore CLI](https://docs.aws.amazon.com/bedrock/latest/userguide/agentcore.html) (`pip install bedrock-agentcore-starter-toolkit`)

### 1. Install dependencies

```bash
cd server
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

### 2. Configure database

Copy `.env.example` or create a `.env` file in the `server/` root:

```env
DATABASE_URL=postgresql://pm_user:pm_password@localhost:5434/project_management
```

### 3. Start PostgreSQL (local dev)

```bash
# From the project root
docker compose up -d
```

### 4. Seed the database

```bash
python shared/seed_data.py
```

## Running Locally

```bash
cd server
source .venv/bin/activate
.venv/bin/python -m src.server
```

The server starts on `http://localhost:8000/mcp` (Streamable HTTP).

## Deploying to AgentCore

### First-time setup

```bash
cd server
agentcore configure -e src/server.py -p MCP -n server
```

### Deploy

```bash
AWS_PROFILE=bbl-training-prod agentcore deploy
```

### Check status

```bash
AWS_PROFILE=bbl-training-prod agentcore status
```

### Invoke (via AgentCore)

```bash
AWS_PROFILE=bbl-training-prod agentcore invoke '{"prompt": "List all users with developer role"}'
```

## Testing

### MCP Inspector (local)

```bash
npx @modelcontextprotocol/inspector
```

In the web UI:
- Transport: **Streamable HTTP**
- URL: `http://localhost:8000/mcp`
- No auth needed

### MCP Inspector (deployed via SigV4 proxy)

```bash
cd server
AWS_PROFILE=bbl-training-prod .venv/bin/python -m src.proxy
```

Then in MCP Inspector:
- Transport: **Streamable HTTP**
- URL: `http://localhost:9000/mcp`
- No auth needed (proxy handles SigV4 signing)

### Direct tool calls (curl)

```bash
# Initialize session
curl -s http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}},"id":1}'

# Call a tool
curl -s http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"list_users","arguments":{}},"id":2}'
```

### CloudWatch Logs (deployed)

```bash
aws logs tail /aws/bedrock-agentcore/runtimes/server-7iBhkG30on-DEFAULT \
  --log-stream-name-prefix "2026/03/16/[runtime-logs" --follow --region us-west-2
```

## Design Decisions

- **FastMCP**: Official Python MCP SDK — handles JSON-RPC protocol, tool registration, and schema generation
- **Streamable HTTP**: AgentCore Runtime expects MCP servers on `0.0.0.0:8000/mcp` with Streamable HTTP transport
- **SQLAlchemy ORM**: Mature Python ORM with support for complex queries and PostgreSQL
- **Lazy DB initialization**: Engine connects on first tool call (not at startup) to meet AgentCore's 30-second init window
- **python-dotenv**: Loads `.env` file automatically — standard Python project pattern
- **SigV4 Proxy**: Local HTTP proxy that signs requests for testing deployed servers with MCP Inspector
- **Structured errors**: All tool errors return JSON `{"error": "..."}` so LLM agents get useful feedback
