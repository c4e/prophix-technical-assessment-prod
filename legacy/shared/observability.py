"""Shared observability helpers for Strands Agents.

Provides a single ``setup_telemetry()`` call that:
- Configures the Strands ``StrandsTelemetry`` exporter to write JSONL trace
  files (one JSON object per OpenTelemetry span).
- Optionally mirrors spans to the console (useful during development).
- Sets up Python ``logging`` for the ``strands`` SDK so that agent reasoning,
  tool calls, and errors are captured in a standard log file.

Usage
-----
::

    from shared.observability import setup_telemetry, trace_attributes

    # Call once at process start-up
    setup_telemetry("exercise-2", log_dir="exercise-2/logs")

    # Pass per-agent custom span attributes
    agent = Agent(
        ...,
        trace_attributes=trace_attributes(session_id="abc", agent_name="analysis"),
    )

Trace files are written to ``<log_dir>/traces.jsonl`` and standard logs to
``<log_dir>/strands.log``.
"""

from __future__ import annotations

import atexit
import logging
import os
from os import linesep
from typing import IO

from strands.telemetry import StrandsTelemetry

# ---------------------------------------------------------------------------
# Module-level state (singleton pattern – setup_telemetry is idempotent)
# ---------------------------------------------------------------------------

_initialised: bool = False
_trace_file_handle: IO[str] | None = None

# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------


def setup_telemetry(
    service_name: str,
    log_dir: str | None = None,
    *,
    console_traces: bool = False,
    strands_log_level: int = logging.DEBUG,
    app_log_name: str | None = None,
) -> str:
    """Initialise Strands OpenTelemetry tracing **and** Python logging.

    Parameters
    ----------
    service_name:
        Logical name written into every span (e.g. ``"exercise-2"``).
    log_dir:
        Directory for ``traces.jsonl`` and ``strands.log``.  Created
        automatically if it does not exist.  Defaults to ``./logs``.
    console_traces:
        If *True*, spans are also printed to *stderr* (human-readable).
    strands_log_level:
        Python log level for the ``strands`` logger.  ``DEBUG`` captures
        full LLM reasoning, tool calls, and intermediate results.
    app_log_name:
        If given, also calls ``setup_logging(app_log_name, log_dir)`` to
        configure the root logger with a file + stderr handler.  Pass e.g.
        ``"agent"`` to create ``<log_dir>/agent.log``.

    Returns
    -------
    str
        The resolved *log_dir* path.
    """
    global _initialised, _trace_file_handle

    if _initialised:
        return

    log_dir = log_dir or os.path.join(os.getcwd(), "logs")
    os.makedirs(log_dir, exist_ok=True)

    # ── 1. OpenTelemetry trace exporter (JSONL file) ──────────────────────
    #
    # Strands wraps the OTel ConsoleSpanExporter.  By passing ``out`` we
    # redirect the output to a file instead of stdout.  Each span is
    # serialised as a single JSON line via ``formatter``.

    os.environ.setdefault("OTEL_SERVICE_NAME", service_name)

    telemetry = StrandsTelemetry()

    trace_path = os.path.join(log_dir, "traces.jsonl")
    _trace_file_handle = open(trace_path, "a", encoding="utf-8")  # noqa: SIM115

    telemetry.setup_console_exporter(
        out=_trace_file_handle,
        formatter=lambda span: span.to_json() + linesep,
    )

    # Optionally also dump to stderr for local dev
    if console_traces:
        telemetry.setup_console_exporter()  # default → stdout

    # ── 2. Python logging for the strands SDK ─────────────────────────────
    #
    # The Strands SDK logs under the ``strands`` root logger.  At DEBUG
    # level it emits LLM reasoning steps, tool selection, intermediate
    # results, and errors — exactly what the exercises require.

    strands_logger = logging.getLogger("strands")
    strands_logger.setLevel(strands_log_level)

    # File handler – full SDK debug output
    fh = logging.FileHandler(os.path.join(log_dir, "strands.log"), encoding="utf-8")
    fh.setLevel(strands_log_level)
    fh.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    )
    strands_logger.addHandler(fh)

    # Avoid duplicate stderr output if parent already has a StreamHandler
    strands_logger.propagate = False

    # ── 3. Cleanup ────────────────────────────────────────────────────────
    atexit.register(_cleanup)

    _initialised = True
    logging.getLogger(__name__).info(
        "Strands telemetry initialised – traces → %s, logs → %s/strands.log",
        trace_path,
        log_dir,
    )

    # ── 4. Optional app-level logging ─────────────────────────────────────
    if app_log_name:
        setup_logging(app_log_name, log_dir)

    return log_dir


def setup_logging(
    name: str,
    log_dir: str,
    *,
    level: int = logging.INFO,
) -> None:
    """Configure ``logging.basicConfig`` with a file + stderr handler.

    Parameters
    ----------
    name:
        Base name for the log file (e.g. ``"agent"`` → ``agent.log``).
    log_dir:
        Directory where the log file is written (created if needed).
    level:
        Python log level (default ``INFO``).
    """
    import sys as _sys  # avoid module-level dep on sys

    os.makedirs(log_dir, exist_ok=True)
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(os.path.join(log_dir, f"{name}.log"), encoding="utf-8"),
            logging.StreamHandler(_sys.stderr),
        ],
    )


def trace_attributes(
    session_id: str | None = None,
    agent_name: str | None = None,
    **extra: str,
) -> dict[str, str]:
    """Build a ``trace_attributes`` dict suitable for ``Agent(...)``.

    Custom key/value pairs end up on every OTel span the agent produces,
    making it trivial to filter traces by session or agent name.
    """
    attrs: dict[str, str] = {}
    if session_id:
        attrs["session.id"] = session_id
    if agent_name:
        attrs["agent.name"] = agent_name
    attrs.update(extra)
    return attrs


# ---------------------------------------------------------------------------
# Internal
# ---------------------------------------------------------------------------


def _cleanup() -> None:
    global _trace_file_handle
    if _trace_file_handle and not _trace_file_handle.closed:
        _trace_file_handle.flush()
        _trace_file_handle.close()
        _trace_file_handle = None
