# ragforge — Codebase Guide

## Package layout

```
ragforge/
├── pyproject.toml          entry point: ragforge = "ragforge.cli:app"
├── prompts/qa.jinja2       default QA prompt (Jinja2)
└── src/ragforge/
    ├── cli.py              Typer app; all commands registered here; exception→exit-code handler
    ├── commands/           one file per top-level command
    ├── core/               business logic (config, pipeline, ingestion, retrieval, generation, …)
    ├── eval/               RAGAS evaluation helpers
    ├── deploy/             IaC template generators
    ├── ui/                 Rich console helpers + questionary wizard
    └── runs/               RunRecord dataclass + read/write helpers
```

## Key conventions

- **Provider strings** — always `"provider/model"` (e.g. `"openai/text-embedding-3-small"`).
  Dispatched via `_PROVIDER_MAP` dict in `embedder.py`, `generator.py`, and `store.py`.
- **Exit codes** — 0 success, 1 eval gate fail, 2 ConfigError, 3 APIError, 4 ValidationError, 5 IndexNotFoundError.
  All exceptions are caught in `cli._run()` and converted to `typer.Exit(code)`.
- **`--json` flag** — set globally via `_con.set_json_mode(True)`; suppresses Rich output and emits JSON to stdout/stderr instead.
- **Credentials** — never accepted as CLI args. Always read from `.env` via `python-dotenv`.
- **Run records** — every command writes `.ragforge/runs/<ISO>-<type>.json`; `config_snapshot` field enables `ragforge config diff`.

## Adding a new command

1. Create `src/ragforge/commands/<name>.py` with a `<name>_command(**kwargs)` function.
2. Register in `cli.py` with `@app.command("<name>")`, delegating to `_run(<name>_command, **kwargs)`.
3. Call `print_header("<name>")` at the top and `print_next(tip)` at the end.

## Adding a new provider

Add one entry to `_PROVIDER_MAP` in the relevant factory module (`embedder.py`, `generator.py`, or `store.py`). No other changes needed.
