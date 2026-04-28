---
name: rag-workflow
description: INVOKE THIS SKILL at the start of any RAG project or when deciding what to build next. Covers the full RAG development lifecycle, phase sequencing, component decision points, and when to load specialist skills.
---

<overview>
A RAG (Retrieval-Augmented Generation) pipeline answers questions by fetching relevant context from a knowledge base rather than relying on the LLM's training data alone. Every RAG system — regardless of framework — follows the same lifecycle:

```
┌─────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌─────────┐    ┌────────┐
│ Ingest  │───▶│ Retrieve │───▶│ Generate │───▶│ Evaluate │───▶│ Observe │───▶│ Deploy │
└─────────┘    └──────────┘    └──────────┘    └──────────┘    └─────────┘    └────────┘
     ▲                                                                               │
     └───────────────────────── tune & iterate ────────────────────────────────────┘
```

Each phase has distinct concerns, failure modes, and tuning levers. This skill maps the terrain. Specialist skills go deep on each phase.
</overview>

---

## Phase Map

<phase-map>
| Phase | What happens | Key decisions |
|---|---|---|
| **Ingest** | Load documents → chunk → embed → store in vector DB | Loader, chunk size/overlap, embedding model, vector store |
| **Retrieve** | Embed query → search vector DB → return top-k chunks | Strategy (dense/hybrid/rerank), k, score threshold |
| **Generate** | LLM reads retrieved chunks + query → produces answer | Prompt template, LLM, context window budget |
| **Evaluate** | Score answer quality against ground truth | Metrics, thresholds, evalset construction |
| **Observe** | Instrument all 4 layers, export traces | Exporter (Langfuse, OTLP, Arize), dashboard |
| **Deploy** | Package and ship the pipeline | Container, infra, secrets, CI gate |
</phase-map>

---

## When to Load a Specialist Skill

<when-to-use>
| The developer is working on... | Load this skill |
|---|---|
| Loaders, chunking strategy, embedding model, vector store setup | `rag-ingestion` |
| Retrieval strategy, k selection, hybrid search, reranking | `rag-retrieval` |
| Eval metrics, thresholds, evalset, CI quality gate | `rag-eval` |
| Instrumentation, tracing, debugging a quality regression | `rag-observe` |
| Docker, IaC, cloud targets, environment config | `rag-deploy` |
| Unsure — starting from scratch | continue reading this skill |
</when-to-use>

---

## Starting a New Project

<ex-project-init>
Five decisions to lock in before writing any code. Changing them mid-project is expensive.

```
1. Embedding model     →  determines vector dimensions (cannot change without full re-index)
2. Vector store        →  local (Chroma, FAISS) or managed (Qdrant, Pinecone, Weaviate)
3. Chunking strategy   →  fixed-size, semantic, or document-structure-aware
4. Retrieval strategy  →  dense | hybrid (dense + BM25) | rerank
5. LLM                 →  OpenAI GPT-4o, Anthropic Claude, Ollama (local)
```

A minimal pipeline config (framework-agnostic representation):
```yaml
embedding_model: text-embedding-3-small   # OpenAI — 1536 dims
vector_store: chroma                      # local for dev
chunk_size: 1000
chunk_overlap: 150
retrieval_strategy: dense
k: 5
llm: gpt-4o-mini
```
</ex-project-init>

<ex-minimal-pipeline>
The canonical RAG pipeline in pseudocode — maps directly to any framework (LangChain, LlamaIndex, custom):

```python
# 1. INGEST (run once, or when documents change)
documents = load("./docs/")                        # PDF, DOCX, MD, TXT, HTML
chunks = split(documents, size=1000, overlap=150)
vectors = embed(chunks, model="text-embedding-3-small")
store(vectors, db="chroma")

# 2. RETRIEVE (at query time)
query_vector = embed(user_query)
top_chunks = search(query_vector, k=5)

# 3. GENERATE (at query time)
context = format_chunks(top_chunks)
answer = llm(prompt=f"Answer using only this context:\n{context}\n\nQuestion: {user_query}")

# 4. EVALUATE (offline, in CI)
for question, expected in evalset:
    answer = pipeline(question)
    score = judge(answer, expected, context)       # faithfulness, relevance
assert all(score > threshold for score in scores)  # gate
```
</ex-minimal-pipeline>

---

## The Iteration Loop

<ex-iteration-loop>
After the initial pipeline is live, quality improvement follows this loop. Every change to chunking, retrieval strategy, or embedding model should go through it before deploying.

```
┌─────────────────────────────────────────────────────────────┐
│                      ITERATION LOOP                         │
│                                                             │
│  1. ingest    → load new / updated documents                │
│       ↓                                                     │
│  2. query     → spot-check 5–10 representative questions    │
│       ↓                                                     │
│  3. eval      → run full evalset, record scores             │
│       ↓                                                     │
│  4. observe   → find which layer caused any regression      │
│       ↓                                                     │
│  5. tune      → adjust chunk size / k / strategy in config  │
│       ↓                                                     │
│  6. repeat    → until eval gate passes                      │
│                                                             │
│  Only deploy after the eval gate passes.                    │
└─────────────────────────────────────────────────────────────┘
```
</ex-iteration-loop>

---

## Component Decision Guide

<component-selection>

### Embedding Model
| Model | Dims | Max tokens | Best for | Cost |
|---|---|---|---|---|
| `text-embedding-3-small` | 1536 | 8191 | General purpose, low cost | $0.02 / 1M tokens |
| `text-embedding-3-large` | 3072 | 8191 | High-precision retrieval | $0.13 / 1M tokens |
| `all-MiniLM-L6-v2` | 384 | 256 | Local, no API cost | Free |
| `all-mpnet-base-v2` | 768 | 384 | Local, higher quality | Free |

### Vector Store
| Store | Best for | Persistence | Notes |
|---|---|---|---|
| Chroma | Local dev, prototypes | Disk | Zero config |
| FAISS | In-memory, batch search | In-memory | No server needed |
| Qdrant | Dev + production | Disk / managed | Best OSS prod option |
| Pinecone | Managed, serverless | Managed | No infra to run |
| Weaviate | Hybrid search built-in | Disk / managed | GraphQL API |

### LLM
| Model | Best for | Context window |
|---|---|---|
| `gpt-4o-mini` | Cost-efficient, high volume | 128k tokens |
| `gpt-4o` | High accuracy, complex reasoning | 128k tokens |
| `claude-haiku-4-5` | Fast, low cost | 200k tokens |
| `claude-sonnet-4-5` | Balanced quality + speed | 200k tokens |
| Ollama (local) | No API cost, air-gapped | Model-dependent |
</component-selection>

---

## Lifecycle Sequencing

<lifecycle-sequencing>
Load specialist skills progressively as you move through phases. You do not need all of them upfront.

| When you reach this point | Load |
|---|---|
| Choosing loaders, chunk size, embedding model | `rag-ingestion` |
| Retrieval quality is poor, or first time configuring search | `rag-retrieval` |
| First eval run, or building an evalset | `rag-eval` |
| Adding tracing, debugging a quality drop | `rag-observe` |
| Containerizing or deploying to cloud | `rag-deploy` |
</lifecycle-sequencing>

---

## Common Mistakes

<fix-no-eval-before-deploy>
**WRONG** — shipping without measuring quality:
```python
# ❌ "it looked good in my manual tests"
deploy(pipeline)
```

**CORRECT** — run an evalset and set a pass threshold before any deploy:
```python
# ✅ automated gate — blocks deploy if faithfulness < 0.85
scores = eval_pipeline(pipeline, evalset)
assert scores["faithfulness"] >= 0.85, "Quality gate failed"
assert scores["answer_relevance"] >= 0.80, "Quality gate failed"
```
See `rag-eval` for how to build the evalset and calibrate thresholds.
</fix-no-eval-before-deploy>

<fix-embedding-model-lock>
**WRONG** — changing the embedding model after the index is built:
```python
# ❌ old index used 1536-dim vectors, new model produces 384-dim
# this silently corrupts similarity search results
embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")  # was OpenAI
results = vectorstore.similarity_search(query)   # dimension mismatch → garbage results
```

**CORRECT** — treat embedding model changes as a full re-index:
```python
# ✅ delete the old collection, re-embed everything, re-run eval
vectorstore.delete_collection()
chunks = split(documents)
vectorstore = Chroma.from_documents(chunks, new_embedding_model)
# then re-run eval to confirm quality held or improved
```
See `rag-ingestion` for the full embedding model lock constraint.
</fix-embedding-model-lock>

<fix-context-stuffing>
**WRONG** — retrieving a large k and dumping all chunks into the prompt:
```python
# ❌ k=20 chunks * 1000 tokens = 20k tokens of context
# LLM loses focus; cost spikes; "lost in the middle" degradation
chunks = vectorstore.similarity_search(query, k=20)
context = "\n\n".join([c.page_content for c in chunks])
```

**CORRECT** — use a small k (3–5) or apply a reranker to keep only the highest-signal chunks:
```python
# ✅ retrieve wide, then rerank down to the most relevant chunks
candidates = vectorstore.similarity_search(query, k=20)
top_chunks = reranker.rerank(query, candidates, top_n=5)
```
See `rag-retrieval` for k selection and reranker setup.
</fix-context-stuffing>

<fix-monolithic-pipeline>
**WRONG** — building the entire pipeline in one script before testing any individual phase:
```python
# ❌ 300-line script before verifying chunking, retrieval, or generation separately
# when something breaks, you cannot isolate which phase failed
```

**CORRECT** — build and validate one phase at a time:
```python
# ✅ phase 1: verify ingestion output before moving on
chunks = split(load("docs/"))
print(f"chunks: {len(chunks)}, avg length: {avg_len(chunks)} chars")

# ✅ phase 2: verify retrieval before wiring in the LLM
results = vectorstore.similarity_search("test query", k=5)
for r in results:
    print(r.page_content[:200])

# ✅ phase 3: only then wire in the LLM and test generation
```
</fix-monolithic-pipeline>
