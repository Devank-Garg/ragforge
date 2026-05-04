# ragforge — Codebase Guide for Agents

## Implementation status

| Day | Scope | Status |
|-----|-------|--------|
| 1 | Scaffold · Config · Wizard · `ragforge init` | ✅ Done |
| 2 | `ragforge ingest` (loaders, chunker, embedder, vector store, run records) | ⬜ Next |
| 3 | `ragforge query` (retriever, generator, pipeline, REPL) | ⬜ |
| 4 | `ragforge observe` (tracer, Streamlit dashboard) | ⬜ |
| 5 | `ragforge eval` (generate / run / compare / gate) | ⬜ |
| 6 | `ragforge deploy` · `ragforge status` · `ragforge config diff` | ⬜ |
| 7 | Packaging polish, smoke tests | ⬜ |

---

## Package layout

```
ragforge/
├── pyproject.toml               entry point: ragforge = "ragforge.cli:app"
├── README.md
├── CLAUDE.md                    ← you are here
├── prompts/qa.jinja2            default RAG QA prompt (Jinja2)
└── src/ragforge/
    ├── __init__.py              __version__ = "0.1.0"
    ├── cli.py                   Typer app; all commands registered; exception→exit-code handler
    ├── commands/
    │   ├── init.py              ✅ ragforge init — wizard → yaml + .env.example + prompt
    │   ├── ingest.py            ⬜ stub
    │   ├── query.py             ⬜ stub
    │   ├── eval_.py             ⬜ stub
    │   ├── observe.py           ⬜ stub
    │   ├── deploy.py            ⬜ stub
    │   ├── status.py            ⬜ stub
    │   └── config.py            ⬜ stub
    ├── core/
    │   ├── config.py            ✅ RagforgeConfig (Pydantic v2): load / save / from_wizard_answers
    │   ├── exceptions.py        ✅ ConfigError(2) APIError(3) ValidationError(4) IndexNotFoundError(5)
    │   ├── pipeline.py          ⬜ RAGPipeline orchestrator (Day 3)
    │   ├── ingestion/
    │   │   ├── loader.py        ⬜ per-filetype loaders (Day 2)
    │   │   ├── chunker.py       ⬜ strategy dispatch (Day 2)
    │   │   └── embedder.py      ⬜ provider/model → LangChain Embeddings factory (Day 2)
    │   ├── retrieval/
    │   │   └── retriever.py     ⬜ dense / hybrid / reranked assembly (Day 3)
    │   ├── generation/
    │   │   └── generator.py     ⬜ provider/model → LangChain LLM + Jinja2 prompt (Day 3)
    │   ├── vectorstore/
    │   │   └── store.py         ⬜ Chroma / Qdrant factory (Day 2)
    │   └── observability/
    │       └── tracer.py        ⬜ Langfuse 4-layer spans + console-JSON fallback (Day 4)
    ├── eval/
    │   ├── generate.py          ⬜ synthetic Q&A generation (Day 5)
    │   ├── runner.py            ⬜ RAGAS metric computation (Day 5)
    │   ├── compare.py           ⬜ per-metric delta between runs (Day 5)
    │   └── gate.py              ⬜ threshold check → exit code 1 (Day 5)
    ├── deploy/
    │   ├── docker.py            ⬜ docker-compose.yml generator (Day 6)
    │   ├── cloud_run.py         ⬜ cloudbuild.yaml + Terraform (Day 6)
    │   ├── lambda_.py           ⬜ AWS SAM template (Day 6)
    │   └── aci.py               ⬜ Azure Bicep template (Day 6)
    ├── ui/
    │   ├── console.py           ✅ Rich singleton: print_header / print_next / print_error / print_success
    │   ├── progress.py          ⬜ Rich progress bar + spinner wrappers (Day 2)
    │   └── wizard.py            ✅ 10-step InquirerPy wizard with back navigation
    └── runs/
        └── record.py            ⬜ RunRecord dataclass: write / read / list (Day 2)
```

---

## What is already built (Day 1)

### `core/config.py` — `RagforgeConfig`
- Full Pydantic v2 model for `ragforge.yaml` (all sections, all fields).
- `RagforgeConfig.load(path)` — reads and validates YAML; raises `ConfigError` on missing file or bad YAML.
- `RagforgeConfig.save(directory)` — writes `ragforge.yaml`; creates directory if needed.
- `RagforgeConfig.from_wizard_answers(answers: dict)` — maps flat wizard dict to nested config.
- `@model_validator` — raises `ValidationError` (exit 4) if `chunk_size` exceeds the embedding model's token limit.
- `_MODEL_TOKEN_LIMITS` dict — token ceilings for every supported embedding model; used by both config validator and wizard live-check.

### `core/exceptions.py`
Four typed exceptions, each with an `exit_code` class attribute:
```
ConfigError(2)  APIError(3)  ValidationError(4)  IndexNotFoundError(5)
```
All are subclasses of `RagforgeError`. Caught centrally in `cli._run()`.

### `ui/console.py`
Rich `Console` singleton with `--json` mode support:
- `set_json_mode(bool)` / `is_json_mode()` — toggled by the global `--json` CLI flag.
- `print_header(command)` — prints `● ● ●  ragforge <command>` cyan header.
- `print_next(tip)` — prints the "Next:" suggestion at end of every command.
- `print_error` / `print_success` / `print_warning` — consistent styled output; in JSON mode, errors go to stderr as `{"error": "..."}`.

### `ui/wizard.py` — `run_wizard() → dict`
10-step wizard using InquirerPy (arrow-key navigation, no `?` prefix):
- Each step is a standalone function `_step_<name>(answers: dict) → dict | _BACK`.
- `run_wizard()` drives a step-loop: increments on success, decrements on `_BACK`.
- Back navigation: select `← Back` in any list, or submit an empty text/number field.
- Ctrl+C raises `KeyboardInterrupt` (not swallowed) → clean `Aborted.` exit via `cli._run()`.
- Screen 4 live token-ceiling check: if `chunk_size > model limit`, prompts for correction before continuing.
- All previous answers are preserved as defaults when re-entering a step.

### `commands/init.py` — `init_command(project_dir)`
Orchestrates init:
1. Calls `run_wizard()` → flat answers dict.
2. Calls `RagforgeConfig.from_wizard_answers(answers)` → validated config (raises `ValidationError` on bad params).
3. `config.save(project_dir)` → `ragforge.yaml`.
4. Writes `.env.example` with all credential groups.
5. Copies `prompts/qa.jinja2` from the package into the project (falls back to inline template if missing).
6. Creates `.ragforge/runs/` directory.
7. Calls `print_next(tip)` with the ingest command.

### `cli.py`
- Global Typer app with `--json` and `--version` callbacks.
- All Day 2–6 commands registered as stubs (print `[stub] … coming Day N`).
- `_run(fn, **kwargs)` — central try/except: catches `RagforgeError` → `typer.Exit(exit_code)`, catches `KeyboardInterrupt` → clean exit 0.

---

## Key conventions (read before writing any code)

### Provider strings
Always `"provider/model"` (e.g. `"openai/text-embedding-3-small"`). Dispatched via `_PROVIDER_MAP` dict in each factory module. Adding a new provider = one dict entry, nothing else.

```python
_PROVIDER_MAP = {
    "openai":      lambda model: OpenAIEmbeddings(model=model),
    "huggingface": lambda model: HuggingFaceEmbeddings(model_name=model),
    "cohere":      lambda model: CohereEmbeddings(model=model),
}
```

### Exit codes
| Code | Exception | Cause |
|------|-----------|-------|
| 0 | — | Success |
| 1 | — | Eval gate failure |
| 2 | `ConfigError` | Invalid / missing ragforge.yaml |
| 3 | `APIError` | Embedding / LLM / vector store unreachable |
| 4 | `ValidationError` | Incompatible params |
| 5 | `IndexNotFoundError` | query/eval called before ingest |

Never call `sys.exit()` directly — always raise the appropriate `RagforgeError` subclass and let `cli._run()` handle it.

### Run records
Every command must write `.ragforge/runs/<ISO>-<type>.json` via `runs/record.py` (Day 2):
```json
{
  "run_id": "2026-04-29T10-15-30",
  "run_type": "ingest | eval | query",
  "config_snapshot": { "...full ragforge.yaml at time of run..." },
  "stats": { "...command-specific metrics..." },
  "ragforge_version": "0.1.0"
}
```

### UX conventions
- Every command starts with `print_header("<command>")` and ends with `print_next(tip)`.
- `--json` flag: all Rich output is suppressed; errors go to stderr as `{"error": "...", "exit_code": N}`.
- `--reset` (ingest) always requires an explicit flag + confirmation prompt.
- Progress bars on all operations > 2 s via `ui/progress.py` (Day 2).
- Credentials never in CLI args — always from `.env`.

### `--json` mode
`_con.is_json_mode()` is the gate. Check it in any code that writes to the terminal. Do not use `print()` directly — use `console.py` helpers or `_console.print()`.

---

## Day 2 — What to build next (`ragforge ingest`)

Files to create in order:

**`ui/progress.py`**
- `track(iterable, description)` — thin wrapper over `rich.progress.track`.
- `spinner(description)` — context manager using `rich.progress.Progress` with spinner column.
- Respect `is_json_mode()` — suppress visual output in JSON mode.

**`core/ingestion/loader.py`** — `load_documents(sources, doc_types) → list[Document]`
- Dispatch by extension: `.pdf` → `pdfplumber`, `.docx` → `python-docx`, `.txt` → `TextLoader`, `.html` → `BSHTMLLoader`, `.csv` → `CSVLoader`.
- Attach metadata: `source`, `doc_type`, `ingested_at` (ISO timestamp).
- Raise `APIError` (exit 3) if a source directory does not exist.

**`core/ingestion/chunker.py`** — `chunk_documents(docs, config) → list[Document]`
- Strategy dispatch: `fixed` → `RecursiveCharacterTextSplitter`, `semantic` → `SemanticChunker`, `markdown` → `MarkdownHeaderTextSplitter`.
- Call `_validate_chunk_size(chunk_size, model_key)` — raises `ValidationError` (exit 4) if over token limit.

**`core/ingestion/embedder.py`** — `get_embeddings(model_string) → Embeddings`
- Parse `"provider/model"` string, dispatch via `_PROVIDER_MAP`.
- Raise `APIError` (exit 3) wrapping any provider auth / network error.

**`core/vectorstore/store.py`** — `get_vectorstore(config, embeddings, create=False)`
- `create=True` → create or overwrite collection.
- `create=False` → raise `IndexNotFoundError` (exit 5) if collection absent.
- Chroma: use `langchain_chroma.Chroma`.
- Qdrant: use `langchain_community.vectorstores.Qdrant`.

**`runs/record.py`** — `RunRecord` dataclass
- Fields: `run_id`, `run_type`, `config_snapshot`, `stats`, `ragforge_version`.
- `write_run(record, project_dir)` → `.ragforge/runs/<run_id>-<run_type>.json`.
- `read_run(path)` → `RunRecord`.
- `list_runs(project_dir, run_type=None)` → sorted list of paths.

**`commands/ingest.py`** — `ingest_command(config_path, reset)`
1. Load config via `RagforgeConfig.load(config_path)`.
2. Load documents with progress spinner.
3. Chunk documents.
4. Get embeddings.
5. Get / create vector store (`create=True`, or confirm reset if `--reset`).
6. Add documents with progress bar.
7. Write `RunRecord` with stats (doc count, chunk count, duration).
8. Print Rich summary table + `print_next(tip)`.

**Verification:**
```bash
ragforge ingest --config my-project/ragforge.yaml
# → indexes docs into Chroma
# → writes .ragforge/runs/<ts>-ingest.json
```
