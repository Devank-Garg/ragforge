from __future__ import annotations

from typing import Any

import questionary
from questionary import Style

from ragforge.core.config import _MODEL_TOKEN_LIMITS, _DEFAULT_TOKEN_LIMIT

_STYLE = Style([
    ("qmark", "fg:#00bcd4 bold"),
    ("question", "bold"),
    ("answer", "fg:#00bcd4 bold"),
    ("pointer", "fg:#00bcd4 bold"),
    ("highlighted", "fg:#00bcd4 bold"),
    ("selected", "fg:#00bcd4"),
    ("separator", "fg:#6c6c6c"),
    ("instruction", "fg:#6c6c6c"),
])

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


def run_wizard() -> dict[str, Any]:
    answers: dict[str, Any] = {}

    # Screen 0 — Project
    answers["project_name"] = questionary.text(
        "Project name:",
        style=_STYLE,
    ).ask()

    answers["project_description"] = questionary.text(
        "Short description (optional):",
        default="",
        style=_STYLE,
    ).ask()

    # Screen 1 — Document types
    answers["document_types"] = questionary.checkbox(
        "Document types to ingest:",
        choices=["pdf", "docx", "txt", "html", "csv"],
        default=["pdf", "docx"],
        style=_STYLE,
    ).ask()

    # Screen 2 — Chunking
    answers["chunking_strategy"] = questionary.select(
        "Chunking strategy:",
        choices=["semantic", "fixed", "markdown"],
        default="semantic",
        style=_STYLE,
    ).ask()

    raw_chunk = questionary.text(
        "Chunk size (tokens):",
        default="512",
        style=_STYLE,
        validate=lambda v: v.isdigit() and int(v) > 0 or "Must be a positive integer",
    ).ask()
    answers["chunk_size"] = int(raw_chunk)

    raw_overlap = questionary.text(
        "Overlap (tokens):",
        default="64",
        style=_STYLE,
        validate=lambda v: v.isdigit() and int(v) >= 0 or "Must be a non-negative integer",
    ).ask()
    answers["overlap"] = int(raw_overlap)

    # Screen 3 — Embedding model (live token-ceiling warning)
    emb_model = questionary.select(
        "Embedding model:",
        choices=_EMBEDDING_MODELS,
        default="openai/text-embedding-3-small",
        style=_STYLE,
    ).ask()
    answers["embedding_model"] = emb_model

    limit = _MODEL_TOKEN_LIMITS.get(emb_model, _DEFAULT_TOKEN_LIMIT)
    if answers["chunk_size"] > limit:
        import click
        click.echo(
            f"\n⚠  chunk_size={answers['chunk_size']} exceeds token limit={limit} "
            f"for '{emb_model}'.\n"
            f"   Reduce chunk_size or choose a model with a higher ceiling.\n"
        )
        raw_chunk2 = questionary.text(
            f"Adjust chunk_size (must be ≤ {limit}):",
            default=str(limit),
            style=_STYLE,
            validate=lambda v, lim=limit: (
                v.isdigit() and 0 < int(v) <= lim
                or f"Must be 1–{lim}"
            ),
        ).ask()
        answers["chunk_size"] = int(raw_chunk2)

    # Screen 4 — Vector store
    answers["vector_store_provider"] = questionary.select(
        "Vector database:",
        choices=["chroma", "qdrant"],
        default="chroma",
        style=_STYLE,
    ).ask()

    answers["vector_store_host"] = questionary.text(
        "Vector store host:",
        default="localhost",
        style=_STYLE,
    ).ask()

    raw_port = questionary.text(
        "Vector store port:",
        default="8000",
        style=_STYLE,
        validate=lambda v: v.isdigit() and 1 <= int(v) <= 65535 or "Must be a valid port",
    ).ask()
    answers["vector_store_port"] = int(raw_port)

    answers["vector_store_collection"] = questionary.text(
        "Collection name:",
        default=answers["project_name"],
        style=_STYLE,
    ).ask()

    # Screen 5 — Retrieval
    answers["retrieval_strategy"] = questionary.select(
        "Retrieval strategy:",
        choices=["dense", "hybrid", "rerank"],
        default="hybrid",
        style=_STYLE,
    ).ask()

    raw_topk = questionary.text(
        "Top-K results:",
        default="10",
        style=_STYLE,
        validate=lambda v: v.isdigit() and int(v) > 0 or "Must be a positive integer",
    ).ask()
    answers["top_k"] = int(raw_topk)

    if answers["retrieval_strategy"] == "rerank":
        answers["reranker"] = questionary.select(
            "Reranker model:",
            choices=["cohere/rerank-english-v3.0", "cohere/rerank-multilingual-v3.0"],
            style=_STYLE,
        ).ask()
    else:
        answers["reranker"] = None

    # Screen 6 — Generation
    answers["llm_model"] = questionary.select(
        "LLM model:",
        choices=_LLM_MODELS,
        default="openai/gpt-4o-mini",
        style=_STYLE,
    ).ask()

    answers["citation_mode"] = questionary.select(
        "Citation mode:",
        choices=["inline", "footnote", "none"],
        default="inline",
        style=_STYLE,
    ).ask()

    raw_tokens = questionary.text(
        "Max output tokens:",
        default="1024",
        style=_STYLE,
        validate=lambda v: v.isdigit() and int(v) > 0 or "Must be a positive integer",
    ).ask()
    answers["max_tokens"] = int(raw_tokens)

    # Screen 7 — Eval thresholds
    for metric, defaults in [
        ("faithfulness", (0.75, 0.60)),
        ("answer_relevance", (0.80, 0.65)),
    ]:
        for level, default in [("warning", defaults[0]), ("critical", defaults[1])]:
            key = f"{metric}_{level}"
            raw = questionary.text(
                f"Eval threshold — {metric} {level}:",
                default=str(default),
                style=_STYLE,
                validate=lambda v: _is_float_01(v) or "Must be a float between 0 and 1",
            ).ask()
            answers[key] = float(raw)

    raw_nq = questionary.text(
        "Synthetic eval questions to generate:",
        default="50",
        style=_STYLE,
        validate=lambda v: v.isdigit() and int(v) > 0 or "Must be a positive integer",
    ).ask()
    answers["num_questions"] = int(raw_nq)

    # Screen 8 — Observability
    answers["observability_backend"] = questionary.select(
        "Observability backend:",
        choices=["langfuse", "otlp", "none"],
        default="langfuse",
        style=_STYLE,
    ).ask()

    if answers["observability_backend"] != "none":
        answers["observability_host"] = questionary.text(
            "Observability host URL:",
            default="http://localhost:3000",
            style=_STYLE,
        ).ask()
    else:
        answers["observability_host"] = ""

    # Screen 9 — Deployment
    answers["deployment_target"] = questionary.select(
        "Deployment target:",
        choices=["local", "docker", "cloud-run", "lambda", "aci"],
        default="local",
        style=_STYLE,
    ).ask()

    # Screen 10 — Confirmation
    _print_summary(answers)
    confirmed = questionary.confirm(
        "Generate ragforge.yaml and project files?",
        default=True,
        style=_STYLE,
    ).ask()

    if not confirmed:
        raise SystemExit(0)

    return answers


def _is_float_01(value: str) -> bool:
    try:
        f = float(value)
        return 0.0 <= f <= 1.0
    except ValueError:
        return False


def _print_summary(answers: dict[str, Any]) -> None:
    import click
    click.echo("\n─── Configuration Summary ───────────────────────────────")
    click.echo(f"  Project      : {answers['project_name']}")
    click.echo(f"  Doc types    : {', '.join(answers.get('document_types', []))}")
    click.echo(f"  Chunking     : {answers['chunking_strategy']} / size={answers['chunk_size']} / overlap={answers['overlap']}")
    click.echo(f"  Embedding    : {answers['embedding_model']}")
    click.echo(f"  Vector store : {answers['vector_store_provider']} @ {answers['vector_store_host']}:{answers['vector_store_port']}")
    click.echo(f"  Retrieval    : {answers['retrieval_strategy']} / top-k={answers['top_k']}")
    click.echo(f"  LLM          : {answers['llm_model']} / citation={answers['citation_mode']}")
    click.echo(f"  Observability: {answers['observability_backend']}")
    click.echo(f"  Deploy to    : {answers['deployment_target']}")
    click.echo("─────────────────────────────────────────────────────────\n")
