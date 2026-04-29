# ragforge CLI — Implementation Plan

## Context

The RAGFORGE repo currently has only 5 RAG skill SKILL.md files + a Node.js installer (`ragforge-skills/`). Zero Python code exists. The CLI PRD (`ragforge_CLI_PRD_v0.1.docx`) defines a full developer tool: `ragforge init` (10-screen wizard) → `ingest` → `query` → `eval` → `observe` → `deploy` → `status` → `config diff`. This plan implements the complete v1 CLI as a new Python package at `/home/devank/RAGFORGE/ragforge/`.

---

## Project Structure

```
/home/devank/RAGFORGE/ragforge/
├── pyproject.toml                  ← entry point: ragforge = "ragforge.cli:app"
├── CLAUDE.md
├── prompts/
│   └── qa.jinja2                   ← default QA prompt template
└── src/
    └── ragforge/
        ├── __init__.py             ← __version__ = "0.1.0"
        ├── cli.py                  ← Typer app + all command registration
        ├── commands/
        │   ├── init.py             ← ragforge init (10-screen wizard orchestration)
        │   ├── ingest.py           ← ragforge ingest
        │   ├── query.py            ← ragforge query + --interactive REPL
        │   ├── eval_.py            ← ragforge eval sub-app (generate/run/compare/gate)
        │   ├── observe.py          ← ragforge observe (launches Streamlit dashboard)
        │   ├── deploy.py           ← ragforge deploy
        │   ├── status.py           ← ragforge status
        │   └── config.py           ← ragforge config diff
        ├── core/
        │   ├── config.py           ← RagforgeConfig (Pydantic v2), load/save/from_wizard_answers
        │   ├── exceptions.py       ← ConfigError(2), APIError(3), ValidationError(4), IndexNotFoundError(5)
        │   ├── pipeline.py         ← RAGPipeline orchestrator (retriever + generator)
        │   ├── ingestion/
        │   │   ├── loader.py       ← per-filetype loaders: PDF/DOCX/TXT/HTML/CSV
        │   │   ├── chunker.py      ← strategy dispatch + chunk_size vs token limit guard
        │   │   └── embedder.py     ← "provider/model" → LangChain Embeddings factory
        │   ├── retrieval/
        │   │   └── retriever.py    ← dense / hybrid (BM25+dense) / reranked assembly
        │   ├── generation/
        │   │   └── generator.py    ← "provider/model" → LangChain LLM factory + Jinja2 prompt
        │   ├── vectorstore/
        │   │   └── store.py        ← Chroma/Qdrant factory; raises IndexNotFoundError if absent
        │   └── observability/
        │       └── tracer.py       ← Langfuse 4-layer spans; console-JSON fallback
        ├── eval/
        │   ├── generate.py         ← synthetic Q&A generation from ingested chunks
        │   ├── runner.py           ← RAGAS metric computation → EvalResult
        │   ├── compare.py          ← per-metric delta between two run records
        │   └── gate.py             ← threshold check → (passed, failures) → exit code
        ├── deploy/
        │   ├── docker.py           ← docker-compose.yml generator
        │   ├── cloud_run.py        ← cloudbuild.yaml + Terraform generator
        │   ├── lambda_.py          ← AWS SAM template generator
        │   └── aci.py              ← Azure Bicep template generator
        ├── ui/
        │   ├── console.py          ← Rich Console singleton; print_header/print_next/print_error
        │   ├── progress.py         ← Rich progress bar + spinner wrappers
        │   └── wizard.py           ← questionary 11-screen wizard → dict of answers
        └── runs/
            └── record.py           ← RunRecord dataclass; write/read .ragforge/runs/<ts>-<type>.json
```

---

## Key Design Decisions

### Provider Abstraction (embedding / LLM / vector store)

All providers use a `"provider/model"` string (e.g. `"openai/text-embedding-3-small"`) dispatched via a dict factory in each module. Adding a new provider = one dict entry. The same string appears verbatim in `ragforge.yaml`.

```python
# embedder.py — same pattern used in generator.py and store.py
_PROVIDER_MAP = {
    "openai":      lambda model: OpenAIEmbeddings(model=model),
    "huggingface": lambda model: HuggingFaceEmbeddings(model_name=model),
    "cohere":      lambda model: CohereEmbeddings(model=model),
}
```

### Exit Codes (centralized in cli.py exception handler)

| Code | Exception | Cause |
|------|-----------|-------|
| 0 | — | Success |
| 1 | — | Eval gate failure |
| 2 | ConfigError | Invalid / missing ragforge.yaml |
| 3 | APIError | Embedding / LLM / vector store unreachable |
| 4 | ValidationError | Incompatible params (e.g. chunk_size > model token limit) |
| 5 | IndexNotFoundError | query/eval called before ingest |

### Run Records (shared data bus between commands)

Every command writes `.ragforge/runs/<ISO>-<type>.json` containing:
```json
{
  "run_id": "2026-04-29T10-15-30",
  "run_type": "ingest | eval | query",
  "config_snapshot": { "...full ragforge.yaml at time of run..." },
  "stats": { "...command-specific metrics..." },
  "ragforge_version": "0.1.0"
}
```
`config_snapshot` is what `ragforge config diff` compares against to flag which changes require re-ingestion.

### UX Conventions (per PRD)

- Every command prints `● ● ●  ragforge <command>` header via `console.print_header()`
- Every command ends with a `Next:` suggestion via `console.print_next(tip)`
- `--json` global flag: skip Rich output, emit JSON to stdout (CI-friendly)
- `--reset` always requires explicit flag + confirmation prompt (never automatic)
- Progress bars on all operations > 2 seconds via `ui/progress.py`
- Credentials never accepted as CLI args — always read from `.env`

---

## ragforge.yaml Schema

```yaml
project:
  name: my-project
  description: ""

ingestion:
  sources: ["./docs"]
  document_types: [pdf, docx]
  chunking:
    strategy: semantic       # fixed | semantic | markdown
    chunk_size: 512
    overlap: 64
  embedding:
    model: openai/text-embedding-3-small

vector_store:
  provider: chroma           # chroma | qdrant
  host: localhost
  port: 8000
  collection: my-project

retrieval:
  strategy: hybrid           # dense | hybrid | rerank
  top_k: 10
  reranker: null             # e.g. "cohere/rerank-english-v3"

generation:
  model: openai/gpt-4o-mini
  citation_mode: inline      # inline | footnote | none
  max_tokens: 1024

eval:
  thresholds:
    faithfulness:     {warning: 0.75, critical: 0.60}
    answer_relevance: {warning: 0.80, critical: 0.65}
  synthetic:
    num_questions: 50

observability:
  backend: langfuse          # langfuse | otlp | none
  host: "http://localhost:3000"

deployment:
  target: local              # local | docker | cloud-run | lambda | aci
```

---

## Wizard Screens (ragforge init)

| Screen | Prompt | Config Key |
|--------|--------|------------|
| 0 | Project name + description | `project.name`, `project.description` |
| 1 | Document types (multi-select) | `ingestion.document_types` |
| 2 | Chunking strategy + chunk_size + overlap | `ingestion.chunking.*` |
| 3 | Embedding model (live token-ceiling check) | `ingestion.embedding.model` |
| 4 | Vector database + host/port/collection | `vector_store.*` |
| 5 | Retrieval strategy + top-k | `retrieval.*` |
| 6 | LLM + citation mode + max_tokens | `generation.*` |
| 7 | Eval metrics + thresholds | `eval.thresholds.*` |
| 8 | Observability backend | `observability.*` |
| 9 | Deployment target | `deployment.target` |
| 10 | Confirmation summary → generate files | — |

Post-init files created: `ragforge.yaml`, `.env.example`, `prompts/qa.jinja2`

---

## Implementation Sequence (Day-by-Day)

### Day 1 — Scaffold + Config + Wizard (`ragforge init`)

Files to create, in order:

1. `ragforge/pyproject.toml` — all deps, `ragforge = "ragforge.cli:app"` entry point
2. `ragforge/CLAUDE.md` — codebase guide for agents
3. `src/ragforge/__init__.py` — `__version__ = "0.1.0"`
4. `core/exceptions.py` — 4 exception classes mapped to exit codes
5. `ui/console.py` — Rich Console singleton: `print_header`, `print_next`, `print_error`, `print_success`
6. `core/config.py` — `RagforgeConfig` (Pydantic v2): `load`, `save`, `from_wizard_answers`; chunk_size vs token-ceiling validator
7. `ui/wizard.py` — `run_wizard()`: 11-screen questionary flow → `dict`; Screen 3 live compatibility warning
8. `commands/init.py` — calls `run_wizard` → `from_wizard_answers` → `config.save`; writes `.env.example`; renders `prompts/qa.jinja2`
9. `cli.py` — Typer app; all command stubs registered; `--json` + `--version` callbacks; exception→exit-code handler
10. `prompts/qa.jinja2` — default RAG QA prompt template

**Done when:** `ragforge init my-project` completes wizard and writes `ragforge.yaml`, `.env.example`, `prompts/qa.jinja2`.

---

### Day 2 — Ingestion (`ragforge ingest`)

11. `ui/progress.py` — `track()` and `spinner()` wrappers over Rich
12. `core/ingestion/loader.py` — `load_documents(sources, doc_types)`: dispatches to `pdfplumber`, `python-docx`, `TextLoader`, `BSHTMLLoader`; attaches `source`, `doc_type`, `ingested_at` metadata
13. `core/ingestion/chunker.py` — strategy dispatch (fixed → `RecursiveCharacterTextSplitter`, semantic → `SemanticChunker`, markdown → `MarkdownHeaderTextSplitter`); `_validate_chunk_size` vs `_MODEL_TOKEN_LIMITS`
14. `core/ingestion/embedder.py` — `get_embeddings("provider/model")` factory
15. `core/vectorstore/store.py` — `get_vectorstore(config, embeddings, create)` → Chroma or Qdrant; raises `IndexNotFoundError` (exit 5) when collection absent and `create=False`
16. `runs/record.py` — `RunRecord` dataclass; `write_run`, `read_run`, `list_runs`
17. `commands/ingest.py` — progress bars, ingestion summary Rich table, run record write

**Done when:** `ragforge ingest` indexes PDFs into Chroma and writes `.ragforge/runs/<ts>-ingest.json`.

---

### Day 3 — Retrieval + Query (`ragforge query`)

18. `core/retrieval/retriever.py` — dense / `EnsembleRetriever` (hybrid BM25+dense) / Cohere reranker assembly
19. `core/generation/generator.py` — `get_llm("provider/model", max_tokens)` factory; `generate(llm, question, chunks, template_path, citation_mode)` via Jinja2
20. `core/pipeline.py` — `RAGPipeline(config)`: `run(question)` → `RAGResult(answer, sources, latency_ms)`; `run_repl()` for `--interactive`
21. `commands/query.py` — single-turn (answer panel + sources table) + `--interactive` REPL loop

**Done when:** `ragforge query "What is X?"` returns a cited answer. `--interactive` opens a working REPL.

---

### Day 4 — Observability (`ragforge observe`)

22. `core/observability/tracer.py` — `RagforgeTracer`: `ingestion_span`, `retrieval_span`, `generation_span`, `system_span`; Langfuse SDK v2 decorator API; console-JSON fallback when Langfuse not configured
23. `commands/observe.py` — `subprocess.run(["streamlit", "run", <dashboard_path>])` launching a Streamlit app with 4 tabs (Ingestion, Retrieval, Generation, System) reading `.ragforge/runs/*.json`

**Done when:** Langfuse shows 4-layer traces per query. `ragforge observe` opens the dashboard.

---

### Day 5 — Eval (`ragforge eval *`)

24. `eval/generate.py` — `generate_evalset(chunks, num_questions, judge_model)` → writes `evals/evalset.jsonl`
25. `eval/runner.py` — `run_eval(evalset_path, pipeline, metrics)` → `EvalResult` via `ragas.evaluate()`
26. `eval/compare.py` — `compare_runs(path_a, path_b)` → `CompareResult` with per-metric delta + regression flag
27. `eval/gate.py` — `check_gate(scores, thresholds, strict=False)` → `(passed, failures)`; `--strict` treats warnings as failures
28. `commands/eval_.py` — Typer sub-app with 4 sub-commands: `generate`, `run`, `compare`, `gate`

**Done when:** `ragforge eval gate` exits 1 when faithfulness < 0.60. `eval compare` shows a color-coded delta table.

---

### Day 6 — Deploy + Status + Config diff

29. `deploy/docker.py` — `generate_docker_compose(config)` string (api + qdrant + langfuse services)
30. `deploy/cloud_run.py`, `deploy/lambda_.py`, `deploy/aci.py` — IaC string generators
31. `commands/deploy.py` — pre-deploy gate check → dispatch to generator → write files → print paths + apply instructions
32. `commands/status.py` — reads latest run records + checks env vars + pings vector store → Rich health table (green/yellow/red per component)
33. `commands/config.py` — loads last ingest run's `config_snapshot` vs current `ragforge.yaml` → diff table with re-ingest flags

**Done when:** `ragforge deploy --target docker` writes valid `docker-compose.yml`. `ragforge status` shows full health summary.

---

### Day 7 — Packaging + Polish

- Finalize `pyproject.toml` with pinned versions
- Complete `ragforge/CLAUDE.md` codebase guide
- Update root `.gitignore` for `ragforge/dist/`, `*.egg-info/`
- End-to-end smoke test on real PDFs

---

## Dependencies (pyproject.toml)

```toml
[project]
name = "ragforge"
version = "0.1.0"
requires-python = ">=3.10"

dependencies = [
    "typer[all]>=0.12.0",
    "rich>=13.7.0",
    "questionary>=2.0.1",
    "pyyaml>=6.0.1",
    "python-dotenv>=1.0.1",
    "jinja2>=3.1.3",
    "pydantic>=2.7.0",
    "langchain>=0.3.0",
    "langchain-community>=0.3.0",
    "langchain-openai>=0.2.0",
    "langchain-anthropic>=0.2.0",
    "langchain-chroma>=0.1.3",
    "chromadb>=0.5.0",
    "qdrant-client>=1.9.0",
    "pdfplumber>=0.11.0",
    "python-docx>=1.1.2",
    "beautifulsoup4>=4.12.3",
    "ragas>=0.1.18",
    "datasets>=2.18.0",
    "langfuse>=2.40.0",
    "streamlit>=1.35.0",
    "sentence-transformers>=3.0.0",
    "cohere>=5.5.0",
    "watchfiles>=0.21.0",
]

[project.scripts]
ragforge = "ragforge.cli:app"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/ragforge"]
```

---

## Verification

```bash
# Install in editable mode
cd /home/devank/RAGFORGE/ragforge
pip install -e ".[dev]"

# Day 1: wizard produces ragforge.yaml
ragforge init test-project -y
cat test-project/ragforge.yaml

# Day 2: ingest indexes PDFs
mkdir -p test-project/docs
ragforge ingest --config test-project/ragforge.yaml
ls test-project/.ragforge/runs/

# Day 3: query returns cited answer
ragforge query "What is X?" --config test-project/ragforge.yaml

# Day 4: observability dashboard
ragforge observe --no-browser --config test-project/ragforge.yaml

# Day 5: eval pipeline
ragforge eval generate --config test-project/ragforge.yaml
ragforge eval run
ragforge eval gate    # exit 0 or 1 depending on scores

# Day 6: deploy + status
ragforge deploy --target docker
cat docker-compose.yml
ragforge status
```
