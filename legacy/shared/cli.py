"""Shared interactive CLI loop for agent exercises.

Provides a reusable Rich-powered REPL that handles user input, quit/clear
commands, error display, and Markdown rendering.  Each exercise supplies
lightweight callbacks to plug in its own agent logic.

Usage
-----
::

    from shared.cli import interactive_cli

    interactive_cli(
        title="My Agent",
        subtitles=["Powered by Strands SDK"],
        create=lambda: (my_agent, session_id),
        process=lambda state, msg: str(state(msg)),
        reset=lambda state: (new_agent, new_session_id),
    )
"""

from __future__ import annotations

import logging
from typing import Any, Callable

from rich.console import Console
from rich.markdown import Markdown

logger = logging.getLogger(__name__)
console = Console()

# Type aliases for clarity
State = Any


def interactive_cli(
    *,
    title: str,
    subtitles: list[str] | None = None,
    create: Callable[[], tuple[State, str]],
    process: Callable[[State, str], str],
    reset: Callable[[State], tuple[State, str]],
    commands: dict[str, Callable[[State], None]] | None = None,
    after_response: Callable[[State, str], str | None] | None = None,
) -> None:
    """Run a generic interactive CLI loop.

    Parameters
    ----------
    title:
        Bold blue header printed on startup.
    subtitles:
        Optional dim lines printed below the title.
    create:
        Factory that returns ``(state, session_id)``.  ``state`` is an
        opaque object passed to every other callback.
    process:
        ``(state, user_input) -> answer_text``.  May mutate *state*.
    reset:
        ``(state) -> (new_state, new_session_id)``.
    commands:
        Extra single-word commands (e.g. ``{"trace": fn}``).  The
        callback receives *state* and should print output itself.
    after_response:
        Optional hook called after each response is printed.  Return a
        string to display as dim text, or ``None`` to skip.
    """
    subtitles = subtitles or []
    commands = commands or {}

    # Build hint line from built-in + extra commands
    extra_cmds = ", ".join(f"'{c}' to {c}" for c in commands)
    hint_parts = ["Type 'quit' to exit", "'clear' to reset"]
    if extra_cmds:
        hint_parts.append(extra_cmds)
    hint = ", ".join(hint_parts) + "."

    # ── Banner ────────────────────────────────────────────────────────────
    console.print(f"\n[bold blue]{title}[/bold blue]")
    for sub in subtitles:
        console.print(f"[dim]{sub}[/dim]")
    console.print(f"[dim]{hint}[/dim]\n")

    state, session_id = create()
    console.print(f"[dim]Session: {session_id}[/dim]\n")

    # ── Main loop ─────────────────────────────────────────────────────────
    while True:
        try:
            user_input = console.input("[bold green]You:[/bold green] ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[bold blue]Goodbye![/bold blue]")
            break

        if not user_input:
            continue

        lowered = user_input.lower()

        if lowered in ("quit", "exit"):
            console.print("[bold blue]Goodbye![/bold blue]")
            break

        if lowered == "clear":
            state, session_id = reset(state)
            console.print(f"[dim]Conversation cleared. New session: {session_id}[/dim]\n")
            continue

        # Extra commands
        if lowered in commands:
            commands[lowered](state)
            console.print()
            continue

        logger.info("User: %s", user_input)
        console.print()

        try:
            answer = process(state, user_input)
            logger.info("Agent: %s...", answer[:200])
            console.print("[bold blue]Assistant:[/bold blue]")
            console.print(Markdown(answer))
            console.print()

            if after_response:
                extra = after_response(state, answer)
                if extra:
                    console.print(f"[dim]  {extra}[/dim]\n")
        except Exception as e:
            logger.error("Agent error: %s", e, exc_info=True)
            console.print(f"[bold red]Error:[/bold red] {e}\n")
