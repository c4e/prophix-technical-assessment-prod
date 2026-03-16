# Architecture: Multi-Agent Communication Design

## Pattern: Agents as Tools

The system uses the **Strands Agents "Agents as Tools"** pattern, where specialized agents are wrapped as `@tool`-decorated functions callable by an orchestrator agent. This is the simplest multi-agent pattern in Strands and maps cleanly to the assessment's Triage → Analysis → Action flow.

### Why "Agents as Tools"?

| Pattern | Fit | Reasoning |
|---------|-----|-----------|
| **Agents as Tools** | ✅ Best | Clear hierarchy, orchestrator delegates to specialists. Simple to implement, debug, and explain. |
| Graph | ❌ | Overkill for this use case — we don't need branching conditional logic at every node. |
| Swarm | ❌ | Agents don't need autonomous handoff — the orchestrator controls flow. |
| Workflow | ❌ | Tasks aren't independent/parallelizable — analysis must complete before actions. |

## Component Design

### 1. Triage Agent (LLM-only)

A standalone `Agent` with no tools that classifies the user's intent:
- **Input:** Raw user request
- **Output:** Structured classification (QUERY / ANALYSIS / ACTION / MIXED)
- **Implementation:** Constrained prompt that returns `INTENT: <type>\nREASONING: <explanation>`

This runs **before** the orchestrator agent loop, so the orchestrator receives routing hints.

### 2. Orchestrator Agent

A Strands `Agent` with `analysis_agent` and `action_agent` as tools:
- Receives the user request + triage classification
- Decides which tool agent(s) to invoke based on the intent
- For MIXED intents, calls analysis first, then passes findings to the action agent
- Synthesizes a cohesive final response

### 3. Analysis Agent (Read Tools)

Wrapped as a `@tool` function. Internally creates a Strands `Agent` with read-only MCP tools.
- Tools: `search_tasks`, `get_task_details`, `get_project_summary`, `list_users`
- System prompt focuses on data retrieval, aggregation, and reporting

### 4. Action Agent (Write Tools)

Wrapped as a `@tool` function. Internally creates a Strands `Agent` with write MCP tools.
- Tools: `create_task`, `update_task`, `assign_task`, `add_comment` (+ `list_users`, `search_tasks` for ID lookups)
- System prompt focuses on executing changes and reporting results

## Message Protocol

### AgentMessage Envelope

```python
@dataclass
class AgentMessage:
    sender: str          # "triage", "analysis", "action", "orchestrator"
    recipient: str       # Target agent
    intent: str          # Classification from triage
    content: str         # Message body (structured text or JSON)
    metadata: dict       # Additional context (timestamps, IDs, etc.)
    timestamp: float     # Unix timestamp
    confidence: float    # 0.0 - 1.0, how confident the sender is
```

### SharedContext Store

A `SharedContext` dataclass is populated during request processing and passed to
tool agents via `ToolContext.invocation_state` (the Strands SDK's built-in
mechanism for sharing per-invocation state with tools):

```python
# Orchestrator passes context when invoking:
self.orchestrator_agent(prompt, shared_context=ctx)

# Tool agents receive it automatically:
@tool(context=True)
def analysis_agent(query: str, tool_context: ToolContext) -> str:
    ctx = tool_context.invocation_state.get("shared_context")
```

SharedContext fields:
- `original_request`: The user's raw input
- `intent`: Classified intent from triage
- `triage_reasoning`: Why this classification was chosen
- `analysis_result`: Output from the analysis agent
- `action_result`: Output from the action agent
- `messages`: List of all AgentMessages exchanged
- `tool_calls`: Log of all MCP tool invocations
- `errors`: Any errors encountered

### Trace Output

Each request produces a structured trace showing:
1. Original request and classified intent
2. Triage reasoning
3. Messages exchanged between agents
4. All tool calls with parameters
5. Final results from each agent
6. Any errors

## Error Handling

### Interrupt-Based Guards (Native Strands Hooks)

The orchestrator uses the **Strands interrupt system** (`BeforeToolCallEvent` hooks) for conflict detection and timeout enforcement — no custom error handlers needed.

#### ConflictGuardHook

Intercepts `action_agent` tool calls before execution. If the instruction contains dangerous keywords (`delete`, `remove all`, `bulk`, `reassign all`, `drop`), it raises a Strands interrupt:

```python
class ConflictGuardHook(HookProvider):
    def _guard(self, event: BeforeToolCallEvent) -> None:
        if event.tool_use["name"] != "action_agent":
            return
        instruction = event.tool_use["input"].get("instruction", "").lower()
        triggered = [kw for kw in CONFLICT_KEYWORDS if kw in instruction]
        if triggered:
            approval = event.interrupt("exercise3-conflict-guard", reason={...})
            if approval.lower() not in ("y", "yes", "approve"):
                event.cancel_tool = f"Action cancelled by user: {approval}"
```

#### TimeoutGuardHook

Tracks elapsed time across all tool calls in a request. If the threshold (default 120s, configurable via `ORCHESTRATOR_TIMEOUT` env var) is exceeded, interrupts to ask whether to continue:

```python
class TimeoutGuardHook(HookProvider):
    def _check(self, event: BeforeToolCallEvent) -> None:
        elapsed = time.time() - self._start_time
        if elapsed > self.max_seconds:
            approval = event.interrupt("exercise3-timeout", reason={...})
            if approval.lower() not in ("y", "yes", "continue"):
                event.cancel_tool = f"Operation timed out after {elapsed:.0f}s"
```

#### Interrupt Loop

When an interrupt fires, the agent pauses and returns `stop_reason == "interrupt"`. The orchestrator handles the loop:

- **Interactive CLI mode**: Prompts the user for approval
- **Batch mode** (`--save-examples`): Auto-approves with `auto_approve=True`

All interrupts are logged to `SharedContext.escalations` and appear in the trace output.

### Standard Error Handling

| Error Type | Handling |
|-----------|----------|
| Agent failure | Orchestrator catches exceptions, reports to user |
| Tool call failure | Individual agents receive error JSON, reason about alternatives |
| Circular routing | Not possible — triage runs once, then orchestrator delegates linearly |
| Bedrock API timeout | Strands SDK handles; logged and surfaced via `ctx.errors` |

## Data Flow Example

**Request:** "Find overloaded team members and rebalance tasks"

```
1. Triage Agent → MIXED (analysis then action needed)
2. Orchestrator → analysis_agent("Find task distribution across all users")
   → MCP: list_users()
   → MCP: search_tasks(assignee_id=1)
   → MCP: search_tasks(assignee_id=2)
   → ... (for each user)
   → Returns: "Bob has 6 tasks, Carol has 8 tasks, David has 2 tasks..."
3. Orchestrator → action_agent("Reassign tasks from Carol to David: task IDs 14, 15")
   → MCP: assign_task(task_id=14, assignee_id=4)
   → MCP: assign_task(task_id=15, assignee_id=4)
   → Returns: "Reassigned 2 tasks from Carol to David"
4. Orchestrator → combines results into final answer
```
