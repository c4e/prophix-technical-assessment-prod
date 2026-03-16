# Exercise 3: Multi-Agent Orchestration

## Overview

A multi-agent system using the **Strands Agents "Agents as Tools"** pattern where specialized agents collaborate through an orchestrator to handle complex workflows.

## Architecture

```
User Request
     ↓
┌─────────────────────────────────────┐
│          ORCHESTRATOR               │
│  (Strands Agent with tool agents)   │
│                                     │
│  1. Triage Agent (LLM-only)        │
│     → classifies intent             │
│                                     │
│  2. Routes to specialist:           │
│     ┌──────────┐  ┌──────────┐     │
│     │ Analysis │  │  Action  │     │
│     │  Agent   │  │  Agent   │     │
│     │(read MCP)│  │(write MCP│     │
│     └────┬─────┘  └────┬────┘     │
│          │              │          │
│          └──────┬───────┘          │
│                 ↓                   │
│          MCP Server (Ex.1)          │
│                 ↓                   │
│           PostgreSQL                │
└─────────────────────────────────────┘
```

### Agent Roles

| Agent | Role | Tools |
|-------|------|-------|
| **Triage** | Classifies intent: QUERY, ANALYSIS, ACTION, MIXED | None (LLM-only) |
| **Analysis** | Reads data, computes metrics, generates reports | `search_tasks`, `get_task_details`, `get_project_summary`, `list_users` |
| **Action** | Executes write operations | `create_task`, `update_task`, `assign_task`, `add_comment`, `list_users`, `search_tasks` |

### Routing Logic

| Intent | Route |
|--------|-------|
| QUERY | → Analysis Agent |
| ANALYSIS | → Analysis Agent |
| ACTION | → Action Agent |
| MIXED | → Analysis Agent → Action Agent (sequential) |

## Inter-Agent Communication

See [ARCHITECTURE.md](ARCHITECTURE.md) for the full protocol design.

Messages use a structured `AgentMessage` envelope:
```python
{
    "sender": "triage",
    "recipient": "orchestrator",
    "intent": "analysis",
    "content": "User is asking for workload comparison across team members",
    "confidence": 0.9,
    "timestamp": 1710000000.0,
    "metadata": {}
}
```

## Setup & Run

### Prerequisites
- Exercise 1 setup complete (PostgreSQL running, database seeded)
- AWS credentials configured

### Run Interactive Mode
```bash
python exercise-3/src/orchestrator.py
```

### Run Single Prompt
```bash
python exercise-3/src/orchestrator.py "Analyze the workload distribution and rebalance tasks"
```

### View Trace
In interactive mode, type `trace` after a request to see the full agent trace.

## Test Scenarios

| # | Scenario | Agents |
|---|----------|--------|
| 1 | "Analyze workload distribution and rebalance by reassigning tasks from overloaded members" | Triage → Analysis → Action |
| 2 | "Find all blocked tasks, identify blockers from comments, create tasks to address each" | Triage → Analysis → Action |
| 3 | "Generate a project health report for all active projects" | Triage → Analysis |
| 4 | "Review tasks across projects, then create sprint planning tasks assigned by workload and role" | Triage → Analysis → Action |

> **Note on scenario 4:** The exercises.md spec suggests creating a new *project*, but the MCP server (Exercise 1) does not expose a `create_project` tool — only `create_task`. We adapted the scenario to review existing tasks and create new tasks within existing projects, which exercises the same Triage → Analysis → Action pipeline.

## Logs

Trace logs saved to `exercise-3/logs/orchestrator.log`.
