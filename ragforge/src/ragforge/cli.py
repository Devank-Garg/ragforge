from __future__ import annotations

import json
import sys
from typing import Optional

import typer

from ragforge import __version__
from ragforge.core.exceptions import RagforgeError
from ragforge.ui import console as _con

app = typer.Typer(
    name="ragforge",
    help="RAGForge — build, evaluate, and deploy production RAG pipelines.",
    add_completion=True,
    no_args_is_help=True,
)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"ragforge {__version__}")
        raise typer.Exit()


@app.callback()
def _global_options(
    json_output: bool = typer.Option(
        False, "--json", help="Emit JSON output (CI-friendly).", is_eager=False
    ),
    version: Optional[bool] = typer.Option(
        None, "--version", "-V", callback=_version_callback, is_eager=True, help="Show version."
    ),
) -> None:
    _con.set_json_mode(json_output)


# --- command registration ---

@app.command("init")
def init(
    project_dir: str = typer.Argument(".", help="Directory to initialise"),
) -> None:
    """Initialise a new RAGForge project via interactive wizard."""
    from pathlib import Path
    from ragforge.commands.init import init_command
    _run(init_command, project_dir=Path(project_dir))


@app.command("ingest")
def ingest(
    config: str = typer.Option("ragforge.yaml", "--config", "-c", help="Path to ragforge.yaml"),
    reset: bool = typer.Option(False, "--reset", help="Drop and re-create the vector index."),
) -> None:
    """Ingest documents into the vector store."""
    typer.echo("[stub] ragforge ingest — coming Day 2")


@app.command("query")
def query(
    question: str = typer.Argument(..., help="Question to ask"),
    config: str = typer.Option("ragforge.yaml", "--config", "-c"),
    interactive: bool = typer.Option(False, "--interactive", "-i", help="Open REPL loop"),
) -> None:
    """Query the RAG pipeline."""
    typer.echo("[stub] ragforge query — coming Day 3")


eval_app = typer.Typer(help="Evaluation sub-commands.")
app.add_typer(eval_app, name="eval")


@eval_app.command("generate")
def eval_generate(config: str = typer.Option("ragforge.yaml", "--config", "-c")) -> None:
    """Generate a synthetic eval set."""
    typer.echo("[stub] ragforge eval generate — coming Day 5")


@eval_app.command("run")
def eval_run(config: str = typer.Option("ragforge.yaml", "--config", "-c")) -> None:
    """Run RAGAS evaluation."""
    typer.echo("[stub] ragforge eval run — coming Day 5")


@eval_app.command("compare")
def eval_compare(
    run_a: str = typer.Argument(..., help="Path to first run record"),
    run_b: str = typer.Argument(..., help="Path to second run record"),
) -> None:
    """Compare two eval run records."""
    typer.echo("[stub] ragforge eval compare — coming Day 5")


@eval_app.command("gate")
def eval_gate(
    config: str = typer.Option("ragforge.yaml", "--config", "-c"),
    strict: bool = typer.Option(False, "--strict", help="Treat warnings as failures"),
) -> None:
    """Check eval scores against configured thresholds."""
    typer.echo("[stub] ragforge eval gate — coming Day 5")


@app.command("observe")
def observe(
    config: str = typer.Option("ragforge.yaml", "--config", "-c"),
    no_browser: bool = typer.Option(False, "--no-browser"),
) -> None:
    """Launch the observability dashboard."""
    typer.echo("[stub] ragforge observe — coming Day 4")


@app.command("deploy")
def deploy(
    target: str = typer.Option("docker", "--target", "-t",
                                help="Target: docker | cloud-run | lambda | aci"),
    config: str = typer.Option("ragforge.yaml", "--config", "-c"),
) -> None:
    """Generate deployment artefacts."""
    typer.echo("[stub] ragforge deploy — coming Day 6")


@app.command("status")
def status(
    config: str = typer.Option("ragforge.yaml", "--config", "-c"),
) -> None:
    """Show health status of all pipeline components."""
    typer.echo("[stub] ragforge status — coming Day 6")


@app.command("config")
def config_diff(
    config: str = typer.Option("ragforge.yaml", "--config", "-c"),
) -> None:
    """Show diff between current config and last ingest snapshot."""
    typer.echo("[stub] ragforge config diff — coming Day 6")


# --- central exception → exit-code handler ---

def _run(fn, **kwargs):
    try:
        fn(**kwargs)
    except RagforgeError as exc:
        if _con.is_json_mode():
            print(json.dumps({"error": str(exc), "exit_code": exc.exit_code}), file=sys.stderr)
        else:
            _con.print_error(str(exc))
        raise typer.Exit(exc.exit_code)
    except KeyboardInterrupt:
        typer.echo("\nAborted.")
        raise typer.Exit(0)
