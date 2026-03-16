"""FastAPI streaming server for the multi-agent orchestrator.

Exposes a POST /chat endpoint that streams the orchestrator's response
using Server-Sent Events (SSE).  Uses the Strands SDK stream_async()
and FileSessionManager for persistent conversation sessions.
"""

import asyncio
import json
import logging
import os
import sys
import time
import uuid

# Add exercise-3/src to path for sibling imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from strands import Agent

from protocol import Intent, SharedContext
from agents import run_triage, analysis_agent, action_agent
from orchestrator import Orchestrator, ORCHESTRATOR_PROMPT, SESSIONS_DIR
from shared.config import make_model
from shared.sessions import create_session_manager, delete_session
from shared.observability import setup_telemetry, trace_attributes

# ---------------------------------------------------------------------------
# Logging & Telemetry
# ---------------------------------------------------------------------------

LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
setup_telemetry("exercise-3-api", log_dir=LOG_DIR, app_log_name="api_server")
logger = logging.getLogger("exercise3.api")

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Multi-Agent Orchestrator API",
    description="Streaming chat API powered by the Exercise-3 multi-agent orchestrator",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Session helpers
# ---------------------------------------------------------------------------


def _make_streaming_agent(session_id: str) -> tuple[str, Agent]:
    """Create a streaming Agent with session persistence.

    Uses the shared session helper and SESSIONS_DIR from the orchestrator module.
    Returns (session_id, agent). The FileSessionManager automatically
    restores previous messages when the Agent is initialised.
    """
    session_id, session_manager = create_session_manager(
        session_id or None, SESSIONS_DIR
    )

    agent = Agent(
        model=make_model(),
        system_prompt=ORCHESTRATOR_PROMPT,
        tools=[analysis_agent, action_agent],
        callback_handler=None,
        session_manager=session_manager,
        trace_attributes=trace_attributes(
            session_id=session_id, agent_name="api-orchestrator"
        ),
    )

    return session_id, agent


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None


class ChatResponse(BaseModel):
    session_id: str
    response: str
    intent: str | None = None
    trace: str | None = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/chat")
async def chat(req: ChatRequest):
    """Non-streaming chat endpoint (simple JSON response)."""
    session_id, agent = _make_streaming_agent(req.session_id or "")

    async def _invoke():
        result = await agent.invoke_async(req.message)
        return str(result)

    answer = await _invoke()
    return ChatResponse(
        session_id=session_id,
        response=answer,
    )


@app.post("/chat/stream")
async def chat_stream(req: ChatRequest):
    """Streaming chat endpoint using Server-Sent Events (SSE).

    Uses the Strands SDK stream_async() with FileSessionManager for
    persistent conversation sessions.  The final SSE event is `[DONE]`.
    """
    session_id, agent = _make_streaming_agent(req.session_id or "")

    async def _event_stream():
        # Send the session_id first so the client can track it
        yield f"data: {json.dumps({'session_id': session_id})}\n\n"

        try:
            # Stream tokens via the native async iterator
            # FileSessionManager auto-restores prior messages; new messages
            # are persisted after the invocation completes.
            async for event in agent.stream_async(req.message):
                if "data" in event:
                    yield f"data: {json.dumps({'token': event['data']})}\n\n"

        except Exception as e:
            logger.error(f"Stream error: {e}", exc_info=True)
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

        yield "data: [DONE]\n\n"

    return StreamingResponse(
        _event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/reset")
async def reset_session(session_id: str | None = None):
    """Reset an orchestrator session by removing its persisted files."""
    if session_id and delete_session(session_id, SESSIONS_DIR):
        logger.info(f"Deleted session: {session_id}")
        return {"status": "reset", "session_id": session_id}
    return {"status": "no_session"}


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("API_PORT", "8000"))
    logger.info(f"Starting API server on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
