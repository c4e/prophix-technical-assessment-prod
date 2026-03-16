"""Inter-agent message protocol and shared context store."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Intent(str, Enum):
    """Request intent as classified by the Triage Agent."""
    QUERY = "query"         # Read-only data retrieval / questions
    ACTION = "action"       # Write operations (create, update, assign)
    ANALYSIS = "analysis"   # Aggregate/compute/report
    MIXED = "mixed"         # Requires both analysis then action


@dataclass
class AgentMessage:
    """Envelope for inter-agent communication."""
    sender: str
    recipient: str
    intent: str
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    confidence: float = 1.0

    def to_dict(self) -> dict:
        return {
            "sender": self.sender,
            "recipient": self.recipient,
            "intent": self.intent,
            "content": self.content,
            "metadata": self.metadata,
            "timestamp": self.timestamp,
            "confidence": self.confidence,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str, indent=2)


@dataclass
class SharedContext:
    """Shared context store accessible by all agents."""
    original_request: str = ""
    intent: Intent | None = None
    triage_reasoning: str = ""
    analysis_result: str = ""
    action_result: str = ""
    messages: list[AgentMessage] = field(default_factory=list)
    tool_calls: list[dict] = field(default_factory=list)
    escalations: list[dict] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def add_message(self, msg: AgentMessage):
        self.messages.append(msg)

    def log_tool_call(self, agent: str, tool: str, params: dict, result: str):
        self.tool_calls.append({
            "agent": agent,
            "tool": tool,
            "params": params,
            "result_preview": result[:300] if result else "",
            "timestamp": time.time(),
        })

    def get_trace(self) -> str:
        """Produce a human-readable trace log of the request processing."""
        lines = [
            "=" * 60,
            f"REQUEST: {self.original_request}",
            f"INTENT:  {self.intent.value if self.intent else 'unknown'}",
            "=" * 60,
        ]
        if self.triage_reasoning:
            lines.append(f"\n[TRIAGE] Reasoning:\n{self.triage_reasoning}")
        for msg in self.messages:
            lines.append(f"\n[MESSAGE] {msg.sender} → {msg.recipient} ({msg.intent}):")
            lines.append(f"  {msg.content[:500]}")
        if self.tool_calls:
            lines.append(f"\n[TOOL CALLS] ({len(self.tool_calls)} total)")
            for tc in self.tool_calls:
                lines.append(f"  - {tc['agent']}: {tc['tool']}({json.dumps(tc['params'], default=str)[:200]})")
        if self.escalations:
            lines.append(f"\n[ESCALATIONS] ({len(self.escalations)} total)")
            for esc in self.escalations:
                lines.append(f"  - [{esc.get('type', 'unknown')}] {esc.get('name', '')}: {esc.get('reason', '')}")
                lines.append(f"    Resolution: {esc.get('resolution', 'N/A')}")
        if self.analysis_result:
            lines.append(f"\n[ANALYSIS RESULT]\n{self.analysis_result}")
        if self.action_result:
            lines.append(f"\n[ACTION RESULT]\n{self.action_result}")
        if self.errors:
            lines.append(f"\n[ERRORS]")
            for e in self.errors:
                lines.append(f"  - {e}")
        lines.append("=" * 60)
        return "\n".join(lines)
