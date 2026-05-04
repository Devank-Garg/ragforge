# ragforge

A developer CLI for building, evaluating, and deploying production RAG pipelines — without boilerplate.

```
ragforge init        → 10-screen wizard writes ragforge.yaml
ragforge ingest      → chunk, embed, index your documents
ragforge query       → ask questions, get cited answers
ragforge eval        → measure faithfulness & relevance with RAGAS
ragforge observe     → Streamlit dashboard over Langfuse traces
ragforge deploy      → generate docker-compose / Cloud Run / Lambda / ACI
ragforge status      → health check for every pipeline component
ragforge config diff → see what changed since last ingest
```

---

## Installation

**Requires Python 3.10+**

```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e .
```

Verify:

```bash
ragforge --version   # ragforge 0.1.0
ragforge --help
```

---

## Quick start

```bash
# 1. Initialise a project (interactive wizard)
ragforge init my-project

# 2. Add documents
mkdir -p my-project/docs
cp your-files/*.pdf my-project/docs/

# 3. Set credentials
cp my-project/.env.example my-project/.env
# Edit .env and fill in OPENAI_API_KEY (minimum required)

# 4. Ingest
ragforge ingest --config my-project/ragforge.yaml

# 5. Query
ragforge query "What does the policy say about remote work?" \
  --config my-project/ragforge.yaml
```

---

## ragforge init

Launches an interactive 10-screen wizard that writes three files:

| File | Purpose |
|---|---|
| `ragforge.yaml` | Full pipeline configuration |
| `.env.example` | Credential template (copy to `.env`) |
| `prompts/qa.jinja2` | Default RAG prompt (customisable) |

**Navigation**
- Arrow keys to move, Enter to select
- Space to toggle checkboxes
- Select `← Back` or press Enter on an empty text field to go back
- Ctrl+C to exit at any point

**Screens**

| # | Screen | What you configure |
|---|---|---|
| 1 | Project | Name and description |
| 2 | Ingestion | Document types (PDF, DOCX, TXT, HTML, CSV) |
| 3 | Chunking | Strategy (semantic / fixed / markdown), chunk size, overlap |
| 4 | Embedding | Model — live token-ceiling guard included |
| 5 | Vector store | Chroma or Qdrant, host / port / collection |
| 6 | Retrieval | Dense / hybrid / rerank, top-K |
| 7 | Generation | LLM, citation mode, max tokens |
| 8 | Eval thresholds | Faithfulness & answer relevance warning / critical |
| 9 | Observability | Langfuse / OTLP / none |
| 10 | Deployment | local / docker / cloud-run / lambda / ACI |

---

## ragforge.yaml reference

```yaml
project:
  name: my-project
  description: ""

ingestion:
  sources: ["./docs"]
  document_types: [pdf, docx]
  chunking:
    strategy: semantic        # fixed | semantic | markdown
    chunk_size: 512
    overlap: 64
  embedding:
    model: openai/text-embedding-3-small

vector_store:
  provider: chroma            # chroma | qdrant
  host: localhost
  port: 8000
  collection: my-project

retrieval:
  strategy: hybrid            # dense | hybrid | rerank
  top_k: 10
  reranker: null              # e.g. cohere/rerank-english-v3.0

generation:
  model: openai/gpt-4o-mini
  citation_mode: inline       # inline | footnote | none
  max_tokens: 1024

eval:
  thresholds:
    faithfulness:     {warning: 0.75, critical: 0.60}
    answer_relevance: {warning: 0.80, critical: 0.65}
  synthetic:
    num_questions: 50

observability:
  backend: langfuse           # langfuse | otlp | none
  host: "http://localhost:3000"

deployment:
  target: local               # local | docker | cloud-run | lambda | aci
```

---

## Supported providers

### Embedding models

| String | Provider |
|---|---|
| `openai/text-embedding-3-small` | OpenAI |
| `openai/text-embedding-3-large` | OpenAI |
| `openai/text-embedding-ada-002` | OpenAI |
| `huggingface/BAAI/bge-small-en-v1.5` | HuggingFace |
| `huggingface/BAAI/bge-large-en-v1.5` | HuggingFace |
| `huggingface/sentence-transformers/all-MiniLM-L6-v2` | HuggingFace |
| `cohere/embed-english-v3.0` | Cohere |

### LLM models

| String | Provider |
|---|---|
| `openai/gpt-4o-mini` | OpenAI |
| `openai/gpt-4o` | OpenAI |
| `openai/gpt-3.5-turbo` | OpenAI |
| `anthropic/claude-3-5-haiku-20241022` | Anthropic |
| `anthropic/claude-3-5-sonnet-20241022` | Anthropic |
| `anthropic/claude-opus-4-7` | Anthropic |

---

## Environment variables

Copy `.env.example` to `.env` and fill in the keys for your chosen providers:

```bash
# OpenAI (required if using openai/* models)
OPENAI_API_KEY=sk-...

# Anthropic (required if using anthropic/* models)
ANTHROPIC_API_KEY=sk-ant-...

# Cohere (required if using cohere/* embeddings or reranker)
COHERE_API_KEY=...

# Langfuse (required if observability.backend = langfuse)
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_HOST=http://localhost:3000

# Qdrant (required if vector_store.provider = qdrant)
QDRANT_API_KEY=
```

Credentials are **never** accepted as CLI arguments — always read from `.env`.

---

## Exit codes

| Code | Meaning |
|---|---|
| 0 | Success |
| 1 | Eval gate failed (scores below threshold) |
| 2 | Config error (missing or invalid `ragforge.yaml`) |
| 3 | API error (embedding / LLM / vector store unreachable) |
| 4 | Validation error (e.g. chunk_size exceeds model token limit) |
| 5 | Index not found (`query` or `eval` called before `ingest`) |

---

## Global flags

```bash
ragforge --json <command>    # Machine-readable JSON output (CI-friendly)
ragforge --version           # Print version and exit
```

---

## Project structure

```
my-project/
├── ragforge.yaml          pipeline config
├── .env                   credentials (never commit)
├── .env.example           credential template
├── docs/                  source documents
├── prompts/
│   └── qa.jinja2          RAG prompt template
└── .ragforge/
    └── runs/              per-run JSON records (used by eval compare + config diff)
```

---

## Implementation status

| Command | Status |
|---|---|
| `ragforge init` | ✅ Complete |
| `ragforge ingest` | 🔧 Day 2 |
| `ragforge query` | 🔧 Day 3 |
| `ragforge observe` | 🔧 Day 4 |
| `ragforge eval` | 🔧 Day 5 |
| `ragforge deploy` | 🔧 Day 6 |
| `ragforge status` | 🔧 Day 6 |
| `ragforge config diff` | 🔧 Day 6 |

---

## Development

```bash
# Install with dev extras
pip install -e ".[dev]"

# Run tests
pytest

# Run the wizard against a temp directory
ragforge init /tmp/test-project
```
