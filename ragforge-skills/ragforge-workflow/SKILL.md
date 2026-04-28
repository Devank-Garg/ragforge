---
name: ragforge-workflow
description: INVOKE THIS SKILL at the start of any RAG project or when deciding what to build next. Covers the full RAG development lifecycle, phase sequencing, and the ragforge CLI command map.
---

<overview>
ragforge is a CLI-first RAG development kit. It separates concerns into a clean lifecycle — each phase has a dedicated command, and each phase has a dedicated skill that goes deep.

```
Ingest → Retrieve → Generate → Evaluate → Observe → Deploy
  ▲                                                     │
  └─────────────────── feedback loop ──────────────────┘
```

The single config file `ragforge.yaml` drives every phase. You never hand-code a pipeline — you edit yaml and let the CLI execute it.
</overview>

<phase-map>
| Goal | Phase | ragforge command |
|---|---|---|
| Index documents into the vector store | Ingestion | `ragforge ingest` |
| Run a single-turn test against the pipeline | Retrieval + Generation | `ragforge query "<question>"` |
| Score quality across the full evalset | Evaluation | `ragforge eval run` |
| Compare two pipeline versions | Evaluation | `ragforge eval compare v1 v2` |
| Block a deploy on quality regression | Evaluation | `ragforge eval gate` |
| Open the observability dashboard | Observability | `ragforge observe` |
| Package and deploy the pipeline | Deployment | `ragforge deploy --target <target>` |
</phase-map>

<when-to-use>
Use this table to decide which ragforge skill to load next.

| The developer says... | Load this skill |
|---|---|
| "start a new RAG project" or "set up from scratch" | you are here — proceed to `<ex-project-init>` |
| "add documents", "configure chunking", "change embedding model" | `ragforge-ingestion` |
| "retrieval is bad", "change to hybrid", "add a reranker" | `ragforge-retrieval` |
| "set up eval", "define quality thresholds", "add a CI gate" | `ragforge-eval` |
| "answers got worse", "debug quality regression", "add tracing" | `ragforge-observe` |
| "ship to production", "containerize", "deploy to AWS/GCP/Azure" | `ragforge-deploy` |
</when-to-use>

---

## Project Initialization

<ex-project-init>
Run the wizard to scaffold a new project. The `--prototype` flag selects sensible defaults (Chroma local, OpenAI, dense retrieval). Remove `--yes` to answer the wizard interactively.

<bash>
```bash
ragforge init my-project --prototype --yes
cd my-project
```
</bash>

This produces:
```
my-project/
├── ragforge.yaml      # pipeline config — edit this to change anything
├── docs/              # drop your source documents here
├── evalset.jsonl      # evaluation question/answer pairs
└── .env.example       # API keys template
```
</ex-project-init>

<ex-ragforge-yaml>
Every ragforge command reads from `ragforge.yaml`. This is the single source of truth for the pipeline.

<yaml>
```yaml
# ragforge.yaml

embeddings:
  provider: openai                    # openai | sentence-transformers
  model: text-embedding-3-small       # locked at index creation — change requires full re-ingest

vector_store:
  backend: chroma                     # chroma (local dev) | qdrant (dev + prod)
  persist_path: ./chroma_db

llm:
  provider: openai                    # openai | anthropic | ollama
  model: gpt-4o-mini

retrieval:
  strategy: dense                     # dense | hybrid | rerank | hybrid+rerank
  k: 5                                # number of chunks to retrieve

reranker:                             # only used when strategy includes "rerank"
  provider: cohere
  top_n: 5
  fetch_k: 20                         # candidates to fetch before reranking

eval:
  metrics:
    - faithfulness
    - answer_relevance
    - context_recall
  thresholds:
    faithfulness: 0.85
    answer_relevance: 0.80
    context_recall: 0.75

observe:
  exporters:
    - langfuse                        # langfuse | otlp | arize_phoenix | console
  langfuse:
    public_key: ${LANGFUSE_PUBLIC_KEY}
    secret_key: ${LANGFUSE_SECRET_KEY}
```
</yaml>
</ex-ragforge-yaml>

---

## The Iteration Loop

<ex-iteration-loop>
Day-2 workflow: after the initial pipeline is live, use this loop to improve quality.

<bash>
```bash
# 1. Add or update documents
cp new-docs/*.pdf docs/
ragforge ingest

# 2. Spot-check a few queries manually
ragforge query "What is the refund policy?"
ragforge query "How do I reset my password?"

# 3. Run the full eval suite
ragforge eval run --output results/v2.json

# 4. Compare against the previous run
ragforge eval compare results/v1.json results/v2.json

# 5. If scores dropped, open the observability dashboard
ragforge observe
# → check retrieval hit rate (Layer 2) first
# → then check faithfulness scores (Layer 3)
# → then tune ragforge.yaml (chunking, k, strategy)

# 6. Re-ingest and re-eval until the gate passes
ragforge eval gate
```
</bash>
</ex-iteration-loop>

---

## Lifecycle Sequencing

<lifecycle-sequencing>
Load the corresponding skill when you enter each phase. Skills are designed to be loaded progressively — you do not need all of them at once.

| Phase | When you enter it | Skill to load |
|---|---|---|
| Ingestion | First ingest, or changing loaders / chunking / embedding model | `ragforge-ingestion` |
| Retrieval tuning | Query quality is poor, or changing strategy / k | `ragforge-retrieval` |
| Evaluation | First eval run, or building an evalset, or setting CI thresholds | `ragforge-eval` |
| Observability | Debugging a regression, or adding instrumentation | `ragforge-observe` |
| Deployment | Shipping to staging or production | `ragforge-deploy` |
</lifecycle-sequencing>

---

## Common Mistakes

<fix-yaml-first>
**WRONG** — hand-coding a pipeline in Python before running the wizard:
```python
# ❌ don't do this on a fresh project
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma
embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
vectorstore = Chroma(persist_directory="./chroma_db", embedding_function=embeddings)
# ... 80 more lines
```

**CORRECT** — let the wizard scaffold `ragforge.yaml`, then use the CLI:
```bash
# ✅ do this instead
ragforge init my-project --prototype --yes
ragforge ingest
ragforge query "test question"
```
Only drop into Python when you need logic the CLI cannot express.
</fix-yaml-first>

<fix-skipping-eval>
**WRONG** — deploying without running the eval gate:
```bash
# ❌ no quality signal before shipping
ragforge deploy --target docker
```

**CORRECT** — gate the deploy on passing eval:
```bash
# ✅ CI pattern: gate fails (non-zero exit) if any metric regresses
ragforge eval gate && ragforge deploy --target docker
```
</fix-skipping-eval>

<fix-changing-embedding-mid-project>
**WRONG** — editing `embeddings.model` in `ragforge.yaml` and re-running ingest on the same collection:
```yaml
# ❌ changing this after the collection exists corrupts dimension alignment
embeddings:
  model: text-embedding-3-large   # was text-embedding-3-small
```

**CORRECT** — treat embedding model changes as a full re-index:
```bash
# ✅ delete the old collection and re-ingest
rm -rf ./chroma_db
ragforge ingest
ragforge eval compare results/v1.json results/v2.json
```
See `ragforge-ingestion` for the full embedding model lock constraint.
</fix-changing-embedding-mid-project>
