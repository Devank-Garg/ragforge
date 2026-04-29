from rich.console import Console
from rich.text import Text

_console = Console()
_json_mode = False


def set_json_mode(enabled: bool) -> None:
    global _json_mode
    _json_mode = enabled


def is_json_mode() -> bool:
    return _json_mode


def get_console() -> Console:
    return _console


def print_header(command: str) -> None:
    if _json_mode:
        return
    _console.print(f"\n[bold cyan]● ● ●  ragforge {command}[/bold cyan]\n")


def print_next(tip: str) -> None:
    if _json_mode:
        return
    _console.print(f"\n[dim]Next:[/dim] {tip}\n")


def print_error(message: str) -> None:
    if _json_mode:
        import json, sys
        print(json.dumps({"error": message}), file=sys.stderr)
        return
    _console.print(f"[bold red]Error:[/bold red] {message}")


def print_success(message: str) -> None:
    if _json_mode:
        return
    _console.print(f"[bold green]✓[/bold green] {message}")


def print_warning(message: str) -> None:
    if _json_mode:
        return
    _console.print(f"[bold yellow]⚠[/bold yellow]  {message}")
