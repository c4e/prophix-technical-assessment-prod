"""Shared configuration and MCP client factory.

Centralises model settings and the MCP client constructor so that every
exercise resolves the Exercise-1 server path in exactly the same way.
"""

from __future__ import annotations

import os
import sys

from dotenv import load_dotenv

load_dotenv()

from mcp import stdio_client, StdioServerParameters
from strands.models import BedrockModel
from strands.tools.mcp import MCPClient

# ---------------------------------------------------------------------------
# Model / MCP defaults (from env or sensible fallbacks)
# ---------------------------------------------------------------------------

MODEL_ID: str = os.getenv("BEDROCK_MODEL_ID", "us.anthropic.claude-sonnet-4-20250514-v1:0")
REGION: str = os.getenv("AWS_REGION", "us-east-1")

MCP_SERVER_CMD: str = sys.executable  # current Python interpreter

# exercise-1/src/server.py relative to the project root
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MCP_SERVER_SCRIPT: str = os.path.join(_PROJECT_ROOT, "exercise-1", "src", "server.py")

# ---------------------------------------------------------------------------
# Factories
# ---------------------------------------------------------------------------


def make_model(temperature: float = 0.1, max_tokens: int = 4096) -> BedrockModel:
    """Create a BedrockModel with the shared defaults."""
    return BedrockModel(model_id=MODEL_ID, region_name=REGION, temperature=temperature, max_tokens=max_tokens)


def make_mcp_client(tool_filters: dict | None = None) -> MCPClient:
    """Create an MCPClient connected to the Exercise-1 MCP server via stdio.

    Parameters
    ----------
    tool_filters:
        Optional filter dict (e.g. ``{"allowed": ["search_tasks", ...]}``).
    """
    return MCPClient(
        lambda: stdio_client(
            StdioServerParameters(command=MCP_SERVER_CMD, args=[MCP_SERVER_SCRIPT])
        ),
        **({"tool_filters": tool_filters} if tool_filters else {}),
    )
