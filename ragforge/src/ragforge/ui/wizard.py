from __future__ import annotations

from typing import Any

from InquirerPy import inquirer
from InquirerPy.base.control import Choice
from InquirerPy.separator import Separator
from InquirerPy.utils import get_style
from rich.console import Console
from rich.prompt import Confirm

from ragforge.core.config import _DEFAULT_TOKEN_LIMIT, _MODEL_TOKEN_LIMITS

_console = Console()

_BACK = object()
_BACK_VALUE = "__back__"

_STYLE = get_style({
    "question":    "bold",
    "answer":      "fg:#00bcd4 bold",
    "pointer":     "fg:#00bcd4 bold",
    "highlighted": "fg:#000000 bg:#00bcd4 bold",
    "selected":    "fg:#00bcd4",
    "checkbox":    "fg:#00bcd4",
    "instruction": "fg:#6c6c6c",
    "separator":   "fg:#6c6c6c",
})

_KEYBINDINGS = {
    "toggle": [{"key": "space"}],
    "toggle-all": [{"key": "a"}],
}

_HINT_SELECT   = "(arrow keys · Ctrl+C to exit · Esc to go back)"
_HINT_CHECKBOX = "(space to select · Ctrl+C to exit · Esc to go back)"
_HINT_TEXT     = "(Ctrl+C to exit · leave blank + Enter to go back)"

_EMBEDDING_MODELS = [
    "openai/text-embedding-3-small",
    "openai/text-embedding-3-large",
    "openai/text-embedding-ada-002",
    "huggingface/BAAI/bge-small-en-v1.5",
    "huggingface/BAAI/bge-large-en-v1.5",
    "huggingface/sentence-transformers/all-MiniLM-L6-v2",
    "cohere/embed-english-v3.0",
]

_LLM_MODELS = [
    "openai/gpt-4o-mini",
    "openai/gpt-4o",
    "openai/gpt-3.5-turbo",
    "anthropic/claude-3-5-haiku-20241022",
    "anthropic/claude-3-5-sonnet-20241022",
    "anthropic/claude-opus-4-7",
]


# ── helpers ───────────────────────────────────────────────────────────────────

def _section(title: str) -> None:
    _console.print(f"\n[bold cyan]{title}[/bold cyan]")


def _select(
    question: str,
    choices: list[str],
    default: str | None = None,
    can_go_back: bool = True,
) -> Any:
    all_choices: list = []
    if can_go_back:
        all_choices.append(Choice(value=_BACK_VALUE, name="← Back"))
        all_choices.append(Separator())
    all_choices += choices

    result = inquirer.select(
        message=question,
        choices=all_choices,
        default=default if default in choices else None,
        instruction=_HINT_SELECT,
        qmark="",
        amark="›",
        style=_STYLE,
        vi_mode=False,
    ).execute()

    if result is None or result == _BACK_VALUE:
        return _BACK
    return result


def _checkbox(
    question: str,
    choices: list[str],
    defaults: list[str] | None = None,
    can_go_back: bool = True,
) -> Any:
    defaults = defaults or []
    all_choices: list = []
    if can_go_back:
        all_choices.append(Choice(value=_BACK_VALUE, name="← Back"))
        all_choices.append(Separator())
    all_choices += [
        Choice(value=c, name=c, enabled=(c in defaults))
        for c in choices
    ]

    result = inquirer.checkbox(
        message=question,
        choices=all_choices,
        instruction=_HINT_CHECKBOX,
        qmark="",
        amark="›",
        style=_STYLE,
        keybindings=_KEYBINDINGS,
        validate=lambda x: _BACK_VALUE in x or len([v for v in x if v != _BACK_VALUE]) > 0,
        invalid_message="Select at least one option (or ← Back).",
    ).execute()

    if result is None or _BACK_VALUE in result:
        return _BACK
    return result


def _text(
    question: str,
    default: str = "",
    can_go_back: bool = True,
) -> Any:
    hint = _HINT_TEXT if can_go_back else "(Ctrl+C to exit)"
    result = inquirer.text(
        message=question,
        default=default,
        instruction=hint,
        qmark="",
        amark="›",
        style=_STYLE,
    ).execute()

    if result is None:
        return _BACK
    if can_go_back and result.strip() == "":
        return _BACK
    return result


def _text_required(question: str, default: str = "", can_go_back: bool = True) -> Any:
    """Text prompt that requires a non-empty value (back still allowed via empty on first screen)."""
    hint = _HINT_TEXT if can_go_back else "(Ctrl+C to exit)"
    result = inquirer.text(
        message=question,
        default=default,
        instruction=hint,
        qmark="",
        amark="›",
        style=_STYLE,
        validate=lambda v: len(v.strip()) > 0,
        invalid_message="This field is required.",
    ).execute()

    if result is None:
        return _BACK
    return result


def _int(
    question: str,
    default: int,
    min_val: int = 1,
    max_val: int = 999999,
    can_go_back: bool = True,
) -> Any:
    hint = _HINT_TEXT if can_go_back else "(Ctrl+C to exit)"

    def _validate(raw: str) -> bool:
        if can_go_back and raw.strip() == "":
            return True
        return raw.isdigit() and min_val <= int(raw) <= max_val

    result = inquirer.text(
        message=question,
        default=str(default),
        instruction=hint,
        qmark="",
        amark="›",
        style=_STYLE,
        validate=_validate,
        invalid_message=f"Enter a number between {min_val} and {max_val}.",
    ).execute()

    if result is None or (can_go_back and result.strip() == ""):
        return _BACK
    return int(result)


def _float01(
    question: str,
    default: float,
    can_go_back: bool = True,
) -> Any:
    hint = _HINT_TEXT if can_go_back else "(Ctrl+C to exit)"

    def _validate(raw: str) -> bool:
        if can_go_back and raw.strip() == "":
            return True
        try:
            return 0.0 <= float(raw) <= 1.0
        except ValueError:
            return False

    result = inquirer.text(
        message=question,
        default=str(default),
        instruction=hint,
        qmark="",
        amark="›",
        style=_STYLE,
        validate=_validate,
        invalid_message="Enter a decimal between 0.0 and 1.0.",
    ).execute()

    if result is None or (can_go_back and result.strip() == ""):
        return _BACK
    return float(result)


# ── wizard steps ──────────────────────────────────────────────────────────────

def _step_project(a: dict) -> Any:
    _section("Project  [dim](1 / 10)[/dim]")
    name = _text_required("Project name:", default=a.get("project_name", ""), can_go_back=False)
    if name is _BACK:
        return _BACK
    desc = _text("Short description (optional):", default=a.get("project_description", ""), can_go_back=False)
    if desc is _BACK:
        return _BACK
    return {"project_name": name, "project_description": desc}


def _step_doc_types(a: dict) -> Any:
    _section("Ingestion  [dim](2 / 10)[/dim]")
    result = _checkbox(
        "Document types to ingest:",
        choices=["pdf", "docx", "txt", "html", "csv"],
        defaults=a.get("document_types", ["pdf", "docx"]),
    )
    if result is _BACK:
        return _BACK
    return {"document_types": result}


def _step_chunking(a: dict) -> Any:
    _section("Chunking  [dim](3 / 10)[/dim]")
    strategy = _select(
        "Chunking strategy:",
        choices=["semantic", "fixed", "markdown"],
        default=a.get("chunking_strategy", "semantic"),
    )
    if strategy is _BACK:
        return _BACK

    chunk_size = _int("Chunk size (tokens):", default=a.get("chunk_size", 512), min_val=1)
    if chunk_size is _BACK:
        return _BACK

    overlap = _int("Overlap (tokens):", default=a.get("overlap", 64), min_val=0)
    if overlap is _BACK:
        return _BACK

    return {"chunking_strategy": strategy, "chunk_size": chunk_size, "overlap": overlap}


def _step_embedding(a: dict) -> Any:
    _section("Embedding  [dim](4 / 10)[/dim]")
    model = _select(
        "Embedding model:",
        choices=_EMBEDDING_MODELS,
        default=a.get("embedding_model", "openai/text-embedding-3-small"),
    )
    if model is _BACK:
        return _BACK

    updates: dict[str, Any] = {"embedding_model": model}

    limit = _MODEL_TOKEN_LIMITS.get(model, _DEFAULT_TOKEN_LIMIT)
    if a.get("chunk_size", 512) > limit:
        _console.print(
            f"\n  [yellow]⚠  chunk_size={a['chunk_size']} exceeds the token limit "
            f"({limit}) for [bold]{model}[/bold].[/yellow]"
        )
        new_size = _int(f"Adjust chunk_size (max {limit}):", default=limit, min_val=1, max_val=limit)
        if new_size is _BACK:
            return _BACK
        updates["chunk_size"] = new_size

    return updates


def _step_vectorstore(a: dict) -> Any:
    _section("Vector Store  [dim](5 / 10)[/dim]")
    provider = _select(
        "Vector database:",
        choices=["chroma", "qdrant"],
        default=a.get("vector_store_provider", "chroma"),
    )
    if provider is _BACK:
        return _BACK

    host = _text("Host:", default=a.get("vector_store_host", "localhost"))
    if host is _BACK:
        return _BACK

    port = _int("Port:", default=a.get("vector_store_port", 8000), min_val=1, max_val=65535)
    if port is _BACK:
        return _BACK

    collection = _text(
        "Collection name:",
        default=a.get("vector_store_collection", a.get("project_name", "")),
    )
    if collection is _BACK:
        return _BACK

    return {
        "vector_store_provider": provider,
        "vector_store_host": host,
        "vector_store_port": port,
        "vector_store_collection": collection,
    }


def _step_retrieval(a: dict) -> Any:
    _section("Retrieval  [dim](6 / 10)[/dim]")
    strategy = _select(
        "Strategy:",
        choices=["dense", "hybrid", "rerank"],
        default=a.get("retrieval_strategy", "hybrid"),
    )
    if strategy is _BACK:
        return _BACK

    top_k = _int("Top-K results:", default=a.get("top_k", 10), min_val=1)
    if top_k is _BACK:
        return _BACK

    reranker = None
    if strategy == "rerank":
        reranker = _select(
            "Reranker model:",
            choices=["cohere/rerank-english-v3.0", "cohere/rerank-multilingual-v3.0"],
            default=a.get("reranker", "cohere/rerank-english-v3.0"),
        )
        if reranker is _BACK:
            return _BACK

    return {"retrieval_strategy": strategy, "top_k": top_k, "reranker": reranker}


def _step_generation(a: dict) -> Any:
    _section("Generation  [dim](7 / 10)[/dim]")
    model = _select(
        "LLM model:",
        choices=_LLM_MODELS,
        default=a.get("llm_model", "openai/gpt-4o-mini"),
    )
    if model is _BACK:
        return _BACK

    citation = _select(
        "Citation mode:",
        choices=["inline", "footnote", "none"],
        default=a.get("citation_mode", "inline"),
    )
    if citation is _BACK:
        return _BACK

    max_tokens = _int("Max output tokens:", default=a.get("max_tokens", 1024), min_val=1)
    if max_tokens is _BACK:
        return _BACK

    return {"llm_model": model, "citation_mode": citation, "max_tokens": max_tokens}


def _step_eval(a: dict) -> Any:
    _section("Eval Thresholds  [dim](8 / 10)[/dim]")
    updates: dict[str, Any] = {}
    for metric, (wd, cd) in [
        ("faithfulness", (0.75, 0.60)),
        ("answer_relevance", (0.80, 0.65)),
    ]:
        warn = _float01(f"{metric} — warning threshold:", default=a.get(f"{metric}_warning", wd))
        if warn is _BACK:
            return _BACK
        crit = _float01(f"{metric} — critical threshold:", default=a.get(f"{metric}_critical", cd))
        if crit is _BACK:
            return _BACK
        updates[f"{metric}_warning"] = warn
        updates[f"{metric}_critical"] = crit

    nq = _int("Synthetic eval questions to generate:", default=a.get("num_questions", 50))
    if nq is _BACK:
        return _BACK
    updates["num_questions"] = nq
    return updates


def _step_observability(a: dict) -> Any:
    _section("Observability  [dim](9 / 10)[/dim]")
    backend = _select(
        "Backend:",
        choices=["langfuse", "otlp", "none"],
        default=a.get("observability_backend", "langfuse"),
    )
    if backend is _BACK:
        return _BACK

    host = ""
    if backend != "none":
        host = _text(
            "Host URL:",
            default=a.get("observability_host", "http://localhost:3000"),
        )
        if host is _BACK:
            return _BACK

    return {"observability_backend": backend, "observability_host": host}


def _step_deployment(a: dict) -> Any:
    _section("Deployment  [dim](10 / 10)[/dim]")
    target = _select(
        "Target:",
        choices=["local", "docker", "cloud-run", "lambda", "aci"],
        default=a.get("deployment_target", "local"),
    )
    if target is _BACK:
        return _BACK
    return {"deployment_target": target}


def _step_confirm(a: dict) -> Any:
    _print_summary(a)
    if not Confirm.ask("Generate ragforge.yaml and project files?", default=True, console=_console):
        return _BACK
    return {}


# ── main entry point ──────────────────────────────────────────────────────────

_STEPS = [
    _step_project,
    _step_doc_types,
    _step_chunking,
    _step_embedding,
    _step_vectorstore,
    _step_retrieval,
    _step_generation,
    _step_eval,
    _step_observability,
    _step_deployment,
    _step_confirm,
]


def run_wizard() -> dict[str, Any]:
    answers: dict[str, Any] = {}
    i = 0
    while i < len(_STEPS):
        result = _STEPS[i](answers)
        if result is _BACK:
            i = max(0, i - 1)
        else:
            answers.update(result)
            i += 1
    return answers


# ── summary ───────────────────────────────────────────────────────────────────

def _print_summary(a: dict[str, Any]) -> None:
    _console.print("\n[bold]─── Configuration Summary ───────────────────────────────[/bold]")
    _console.print(f"  Project      : [cyan]{a.get('project_name')}[/cyan]")
    _console.print(f"  Doc types    : {', '.join(a.get('document_types', []))}")
    _console.print(f"  Chunking     : {a.get('chunking_strategy')} / size={a.get('chunk_size')} / overlap={a.get('overlap')}")
    _console.print(f"  Embedding    : {a.get('embedding_model')}")
    _console.print(f"  Vector store : {a.get('vector_store_provider')} @ {a.get('vector_store_host')}:{a.get('vector_store_port')}")
    _console.print(f"  Retrieval    : {a.get('retrieval_strategy')} / top-k={a.get('top_k')}")
    _console.print(f"  LLM          : {a.get('llm_model')} / citation={a.get('citation_mode')}")
    _console.print(f"  Observability: {a.get('observability_backend')}")
    _console.print(f"  Deploy to    : {a.get('deployment_target')}")
    _console.print("[bold]─────────────────────────────────────────────────────────[/bold]\n")
