"""Entry point for AgentCore deployment – Project Management MCP Server.

AgentCore Runtime expects MCP servers at 0.0.0.0:8000/mcp (Streamable HTTP).
"""

from src.mcp_server import server

server.run(transport="streamable-http")
