# Example Traces

Transcripts from running the 4 required multi-agent workflow scenarios.

## Generate all transcripts

```bash
python exercise-3/src/orchestrator.py --save-examples
```

This runs all 4 scenarios and saves Markdown transcripts (response + agent trace) to this directory.

## Run a single scenario

```bash
python exercise-3/src/orchestrator.py "Generate a project health report for all active projects"
```

Use `trace` command in interactive mode to view the full agent trace after each request.

Full trace logs are also saved to `exercise-3/logs/`.

> **Note:** Traces are generated at runtime against live data.
> Run `--save-examples` to produce fresh transcripts for your environment.
