"""MCP client for the deployed PM MCP Server via boto3 invoke_agent_runtime.

Calls the AgentCore-deployed MCP server using SigV4-signed requests,
the same way proxy.py does but through the boto3 SDK.
"""

import json
import logging
import os

import boto3

logger = logging.getLogger("orchestrator.mcp_client")

REGION = os.getenv("AWS_REGION", "us-west-2")
MCP_SERVER_ARN = os.getenv(
    "MCP_SERVER_ARN",
    "arn:aws:bedrock-agentcore:us-west-2:108782061904:runtime/server-7iBhkG30on",
)
QUALIFIER = os.getenv("QUALIFIER", "DEFAULT")

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = boto3.client("bedrock-agentcore", region_name=REGION)
    return _client


def call_mcp(method: str, params: dict | None = None) -> dict:
    """Call an MCP method on the deployed PM MCP server.

    Args:
        method: MCP method (e.g. "tools/list", "tools/call").
        params: Method parameters.

    Returns:
        The "result" field from the MCP JSON-RPC response.
    """
    if params is None:
        params = {}

    payload = json.dumps({
        "jsonrpc": "2.0",
        "id": 1,
        "method": method,
        "params": params,
    }).encode()

    client = _get_client()
    response = client.invoke_agent_runtime(
        agentRuntimeArn=MCP_SERVER_ARN,
        payload=payload,
        qualifier=QUALIFIER,
        contentType="application/json",
        accept="application/json, text/event-stream",
    )

    raw = response["response"].read().decode()
    json_data = json.loads(raw[raw.find("{"):])
    logger.debug(f"MCP {method} → {json.dumps(json_data)[:200]}")
    return json_data.get("result", json_data)


def call_tool(name: str, arguments: dict) -> str:
    """Call a specific MCP tool and return the text result.

    Args:
        name: Tool name (e.g. "search_tasks").
        arguments: Tool arguments dict.

    Returns:
        The tool's text response as a string.
    """
    result = call_mcp("tools/call", {"name": name, "arguments": arguments})

    # Extract text from MCP tool result content array
    if isinstance(result, dict):
        content = result.get("content", [])
        if isinstance(content, list):
            texts = [c.get("text", "") for c in content if c.get("type") == "text"]
            if texts:
                return "\n".join(texts)
        # Fallback: structured content
        structured = result.get("structuredContent")
        if structured:
            return json.dumps(structured, indent=2)

    return json.dumps(result, indent=2, default=str)