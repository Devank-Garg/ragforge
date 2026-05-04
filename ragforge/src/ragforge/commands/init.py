from __future__ import annotations

import shutil
from pathlib import Path

from ragforge.core.config import RagforgeConfig
from ragforge.ui.console import print_header, print_next, print_success
from ragforge.ui.wizard import run_wizard

_ENV_EXAMPLE = """\
# ragforge — environment variables
# Copy to .env and fill in your keys. Never commit .env.

# OpenAI
OPENAI_API_KEY=sk-...

# Anthropic (if using claude models)
ANTHROPIC_API_KEY=sk-ant-...

# Cohere (if using cohere embeddings / reranker)
COHERE_API_KEY=...

# Langfuse (if observability_backend = langfuse)
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_HOST=http://localhost:3000

# Qdrant (if vector_store.provider = qdrant)
QDRANT_API_KEY=
"""

_QA_TEMPLATE_SRC = Path(__file__).parent.parent.parent.parent / "prompts" / "qa.jinja2"


def init_command(project_dir: Path = Path(".")) -> None:
    print_header("init")

    answers = run_wizard()
    config = RagforgeConfig.from_wizard_answers(answers)

    project_dir.mkdir(parents=True, exist_ok=True)

    # write ragforge.yaml
    config_path = config.save(project_dir)
    print_success(f"ragforge.yaml → {config_path}")

    # write .env.example
    env_path = project_dir / ".env.example"
    env_path.write_text(_ENV_EXAMPLE)
    print_success(f".env.example    → {env_path}")

    # copy prompts/qa.jinja2
    prompts_dir = project_dir / "prompts"
    prompts_dir.mkdir(exist_ok=True)
    dest_template = prompts_dir / "qa.jinja2"
    if _QA_TEMPLATE_SRC.exists():
        shutil.copy2(_QA_TEMPLATE_SRC, dest_template)
    else:
        dest_template.write_text(_FALLBACK_QA_TEMPLATE)
    print_success(f"prompts/qa.jinja2 → {dest_template}")

    # create .ragforge/runs dir
    runs_dir = project_dir / ".ragforge" / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)

    print_next(
        f"Add documents to {project_dir}/docs/, then run: "
        f"ragforge ingest --config {config_path}"
    )


_FALLBACK_QA_TEMPLATE = """\
You are a helpful assistant. Answer the question using ONLY the context below.
{% if citation_mode == 'inline' %}Cite sources inline as [1], [2], …{% endif %}
{% if citation_mode == 'footnote' %}List sources as footnotes at the end.{% endif %}

Context:
{% for chunk in chunks %}
[{{ loop.index }}] {{ chunk.page_content }}
{% endfor %}

Question: {{ question }}

Answer:
"""
