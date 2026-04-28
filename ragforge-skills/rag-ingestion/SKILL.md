---
name: rag-ingestion
description: INVOKE THIS SKILL when configuring document loaders, chunking strategy, embedding models, or choosing a vector store. Covers loader selection by file type, chunking strategies with size/overlap guidance, MTEB-ranked embedding models, vector store types with built-in capabilities, and metadata enrichment.
---

<overview>
Ingestion is the foundation of every RAG system. Poor chunking is the single most common cause of retrieval failure — even a perfect retrieval algorithm cannot fix poorly prepared data.

```
Raw Files
    │
    ▼
┌─────────┐   ┌───────────┐   ┌──────────┐   ┌──────────┐   ┌──────────────────┐
│  Load   │──▶│ Pre-proc  │──▶│  Chunk   │──▶│  Embed   │──▶│   Vector Store   │
└─────────┘   └───────────┘   └──────────┘   └──────────┘   └──────────────────┘
 by file type  clean/convert   split strategy  model locked   index type matters
```

Two decisions are irreversible once made:
1. **Embedding model** — dimensions are fixed at collection creation. Changing the model requires full re-index.
2. **Vector store index type** — HNSW vs IVF vs Flat affects recall, speed, and memory permanently for that collection.

Get these right before ingesting at scale.
</overview>

---

## Loader Selection

<loader-selection>
Always prefer structure-preserving loaders. The cleaner the text going into the chunker, the better the embeddings.

| File Type | Recommended Loader | Notes |
|---|---|---|
| PDF (text-based) | `PyPDFLoader` | Page-level metadata attached; splits by page |
| PDF (scanned / image) | `UnstructuredPDFLoader` | Runs OCR — slower but required for image PDFs |
| DOCX | `Docx2txtLoader` | Strips formatting; fast |
| TXT / MD | `TextLoader` | Always set `encoding="utf-8"` explicitly |
| HTML | `BSHTMLLoader` | Strips tags; loses table structure — prefer Markdown conversion |
| CSV / tabular | Custom — load rows as docs | Treat each row as a document; attach column names as metadata |
| JSON | `JSONLoader` with `jq_schema` | Extract the text field explicitly; don't embed raw JSON |
| Mixed directory | `DirectoryLoader` + glob | Combine per-type loaders; set `use_multithreading=True` |
| Web page | `WebBaseLoader` | Strips boilerplate; verify output before ingesting |

**Pre-processing rules:**
- Convert PDFs to Markdown before chunking when the document has headings, tables, or section structure
- Run OCR on scanned PDFs — text loaders return empty strings on image-only PDFs silently
- Strip navigation, headers, footers, and boilerplate from HTML before chunking
</loader-selection>

---

## Chunking Strategy

<chunking-strategy>
There is no single best strategy. The right choice depends on content type and query pattern. Always measure chunk quality before committing to a strategy at scale.

### Strategy Decision Table

| Content Type | Strategy | chunk_size | chunk_overlap | Why |
|---|---|---|---|---|
| General prose (articles, docs, reports) | `RecursiveCharacterTextSplitter` | 1000 chars | 200 chars | Preserves sentence boundaries; reliable baseline |
| Dense technical / legal text | `RecursiveCharacterTextSplitter` | 1500 chars | 300 chars | Needs more context per chunk to stay coherent |
| Markdown / structured docs with headings | `MarkdownHeaderTextSplitter` → then recursive | 1000 chars | 100 chars | Section title attached as metadata; preserves hierarchy |
| Code (Python, JS, SQL, etc.) | `RecursiveCharacterTextSplitter` with code separators | 500–800 chars | 50–100 chars | Keeps function/class boundaries intact |
| Short facts, Q&A pairs, tabular rows | `RecursiveCharacterTextSplitter` | 256–512 chars | 0–50 chars | Atomic units — no bleed between distinct facts |
| Multi-topic / wiki-style documents | Semantic chunking (embedding-based splits) | Dynamic | Dynamic | Detects topic shifts via sentence similarity breakpoints |
| Large complex docs (contracts, manuals, textbooks) | Hierarchical chunking | Multiple levels | Per level | Parent chunks for overview; child chunks for precision |
| Technical docs needing cross-section context | Late chunking | N/A | N/A | Embeds full doc first, derives chunk vectors from token-level representations |

### Safe Starting Point (when unsure)
```
chunk_size    = 1000 characters  (≈ 250 tokens)
chunk_overlap = 200  characters  (20% of chunk_size)
strategy      = RecursiveCharacterTextSplitter
```
Research shows `RecursiveCharacterTextSplitter` at ~400 tokens achieves 85–90% recall. Start here, run eval, then tune.

### Overlap Guidelines

| Content | Recommended Overlap |
|---|---|
| Highly structured (code, tables) | 5–10% of chunk_size |
| General prose | 10–20% of chunk_size |
| Conversational / narrative text | 15–25% of chunk_size |
| Semantic / late chunking | Not applicable |

> **Microsoft Azure AI Search recommendation:** 2000 chars / 500 char overlap as a robust default for pages-mode splitting across diverse document types.

### Advanced Strategies at a Glance

| Strategy | How it works | When to use | Cost |
|---|---|---|---|
| Fixed-size | Split by character/token count with overlap | Baseline, unstructured text | Low |
| Recursive | Hierarchical separators (paragraphs → sentences → words) | Most unstructured text | Low |
| Document-based | Split at Markdown headers, HTML tags, code structure | Structured documents | Low |
| Semantic | Group sentences by embedding similarity; split at topic shifts | Multi-topic, dense docs | Medium |
| Hierarchical | Multiple granularity levels (summary + detail) | Large complex documents | Medium |
| Late chunking | Embed full doc, derive chunk embeddings from token representations | Cross-section dependencies | High |
| LLM-based / Agentic | LLM decides split boundaries | High-value, critical documents | Very high |
</chunking-strategy>

---

## Embedding Model Selection

<embedding-selection>
The embedding model determines vector dimensions and is locked at collection creation. Changing it requires full re-index.

### Benchmark Reference

The **MTEB (Massive Text Embedding Benchmark)** leaderboard is the authoritative source for embedding model rankings. Always check it before choosing a model for production.

> Live leaderboard: **https://huggingface.co/spaces/mteb/leaderboard**  
> Filter by **Retrieval** task type to find the best models for RAG.

### Current Top Models (MTEB Retrieval, April 2026)

| Model | MTEB Retrieval Score | Dims | Max Tokens | Type | Notes |
|---|---|---|---|---|---|
| Gemini Embedding 001 | 67.71 | 3072 | — | Managed API | Supports Matryoshka — truncatable to 768 dims |
| Qwen3-Embedding-8B | ~70 (overall) | 4096 | 32768 | Open-weight | Top overall; high resource requirement |
| Microsoft Harrier-OSS-v1 (27B) | 74.3 (MTEB v2) | — | — | Open-weight | Best overall; very large model |
| NVIDIA Llama-Embed-Nemotron-8B | Top multilingual | — | — | Open-weight | Best for multilingual / global applications |
| Cohere embed-v4 | 65.2 | — | — | Managed API | Strong commercial option |
| `text-embedding-3-large` | 64.6 | 3072 | 8191 | Managed API | Best OpenAI option; Matryoshka support |
| `text-embedding-3-small` | ~62 | 1536 | 8191 | Managed API | Good cost/quality ratio for most RAG |
| BGE-M3 | 63.0 | 1024 | 8192 | Open-weight | Multilingual; free to self-host |
| `all-mpnet-base-v2` | — | 768 | 384 | Open-weight | Solid local baseline |
| `all-MiniLM-L6-v2` | — | 384 | 256 | Open-weight | Fastest local; lower quality |

### Practical Selection Guide

| Scenario | Recommended Model |
|---|---|
| Production, high quality, OpenAI stack | `text-embedding-3-large` |
| Production, cost-sensitive, OpenAI stack | `text-embedding-3-small` |
| Local / offline / no API cost | `BGE-M3` or `all-mpnet-base-v2` |
| Multilingual documents | NVIDIA Llama-Embed-Nemotron-8B or BGE-M3 |
| Prototype / dev loop | `text-embedding-3-small` or `all-MiniLM-L6-v2` |
| State-of-the-art (check MTEB for latest) | See live leaderboard — this table goes stale |

**Hard constraint:** A chunk's character length must stay below the embedding model's token limit. For `text-embedding-3-small` (8191 tokens), keep chunks under ~6000 characters to leave headroom for overlap.
</embedding-selection>

---

## Vector Store Selection

<vector-store-selection>
Choosing the right vector store is one of the most consequential decisions in your ingestion pipeline. It determines:
- What index type handles similarity search (affects recall, speed, memory)
- Whether you get built-in hybrid search or need to wire it yourself
- Whether the store handles chunking and embedding for you
- How you scale from prototype to production

### Index Types

| Index Type | How it works | Best for | Recall | Speed |
|---|---|---|---|---|
| **HNSW** (Hierarchical Navigable Small World) | Graph-based ANN; navigates layers from coarse to fine | Most RAG workloads | 95–99% | Sub-100ms |
| **IVF** (Inverted File) | Clusters vectors; searches nearest clusters only | Very large datasets (>10M vectors) | 90–95% | Fast with large corpora |
| **Flat** (Brute Force) | Exact exhaustive search | Small datasets, offline eval | 100% | Slow at scale |
| **Scalar Quantization** | Compresses float32 → int8 | Memory-constrained production | Slight drop | Fast + memory-efficient |

> **Default to HNSW** for almost all RAG use cases. It delivers 95%+ recall at sub-100ms latency.

### Vector Store Comparison

| Store | Index | Hybrid Search | Built-in Chunking | Built-in Embedding | Deployment | Best For |
|---|---|---|---|---|---|---|
| **Chroma** | HNSW | No | No | No | Local / self-hosted / managed | Dev, prototyping, small projects |
| **FAISS** | Flat / IVF / HNSW | No | No | No | In-memory / self-hosted | Offline eval, batch, no server |
| **Qdrant** | HNSW | Yes (sparse vectors) | No | No | Self-hosted / managed cloud | Production RAG — best OSS option |
| **Weaviate** | HNSW | Yes (BM25 built-in) | No | Yes (via modules) | Self-hosted / managed cloud | Hybrid search without extra infra |
| **Pinecone** | Proprietary | Yes | Yes (Assistant) | Yes (Inference API) | Managed cloud only | Fully managed, zero-infra RAG |
| **Milvus** | HNSW + IVF | Yes | No | No | Self-hosted / Zilliz managed | Billions of vectors; enterprise scale |
| **pgvector** | HNSW / IVF | No | No | No | PostgreSQL extension | Teams already on Postgres |

### When Built-in Chunking Matters

Some vector stores handle parts of the ingestion pipeline for you:

- **Pinecone Assistant** (GA 2025) — upload docs, it handles chunking, embedding, search, and reranking in one endpoint. Best when you want zero ingestion code.
- **Weaviate modules** — configure OpenAI/Cohere/HuggingFace modules to auto-embed at write time. You still chunk externally.
- **All others** — you own the chunking and embedding pipeline. More control, more code.

### Decision Guide

| Scenario | Choose |
|---|---|
| Local dev, prototype, zero config | **Chroma** |
| In-memory, batch processing, no server | **FAISS** |
| Production OSS, rich metadata filtering, self-hosted | **Qdrant** |
| Production + hybrid search without extra BM25 setup | **Weaviate** |
| Fully managed, no infra, built-in pipeline | **Pinecone** |
| Billions of vectors, enterprise, multi-modal | **Milvus** |
| Already using PostgreSQL | **pgvector** |

### Metadata Filtering (critical for production)

All production vector stores support metadata filtering. Attach metadata at ingest time and use it to narrow search scope at query time — this dramatically improves precision without touching chunking or embedding.

```
Retrieve only from doc_type="contract" WHERE year=2024
→ filter at vector store query level, not in post-processing
```
Qdrant and Weaviate have the richest filtering query languages. Chroma filtering is basic but adequate for prototypes.
</vector-store-selection>

---

## Code Examples

<ex-basic-ingestion>
Full PDF ingestion — load, chunk, embed, store. Adapt to any framework.

```python
from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma

loader = PyPDFLoader("./docs/manual.pdf")
pages = loader.load()

splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000,
    chunk_overlap=200,
)
chunks = splitter.split_documents(pages)

embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
vectorstore = Chroma.from_documents(
    documents=chunks,
    embedding=embeddings,
    persist_directory="./chroma_db",
)
print(f"Indexed {len(chunks)} chunks")
```
</ex-basic-ingestion>

<ex-token-count-before-chunking>
Always measure token distribution before fixing chunk_size. A chunk_size tuned to your actual content beats any default.

```python
import tiktoken

def token_stats(documents, model="text-embedding-3-small"):
    enc = tiktoken.encoding_for_model(model)
    counts = [len(enc.encode(doc.page_content)) for doc in documents]
    return {
        "min": min(counts),
        "avg": int(sum(counts) / len(counts)),
        "max": max(counts),
        "total": sum(counts),
    }

stats = token_stats(pages)
print(stats)
# Rule of thumb: chunk_size ≈ 2–3× avg token count per page
# Hard ceiling: chunk_size must stay below model's max_tokens (use 75% of the limit)
```
</ex-token-count-before-chunking>

<ex-markdown-header-chunking>
Structure-aware chunking for Markdown — splits at heading boundaries, attaches section title as metadata.

```python
from langchain.text_splitter import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter

header_splitter = MarkdownHeaderTextSplitter(
    headers_to_split_on=[
        ("#",  "title"),
        ("##", "section"),
        ("###","subsection"),
    ]
)
header_chunks = header_splitter.split_text(markdown_text)

# Further split large sections
char_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
chunks = char_splitter.split_documents(header_chunks)
# chunk.metadata now: {"title": "...", "section": "...", "subsection": "..."}
```
</ex-markdown-header-chunking>

<ex-metadata-enrichment>
Attach rich metadata before embedding. Metadata enables citations and precision filtering at retrieval time.

```python
from datetime import datetime, timezone

def enrich_chunks(chunks, source_path, doc_type):
    for i, chunk in enumerate(chunks):
        chunk.metadata.update({
            "source":      source_path,
            "doc_type":    doc_type,
            "chunk_index": i,
            "ingested_at": datetime.now(timezone.utc).isoformat(),
        })
        # Prepend document title to middle-of-doc chunks (prevents context loss)
        if i > 0 and "title" in chunk.metadata:
            chunk.page_content = f"[{chunk.metadata['title']}]\n{chunk.page_content}"
    return chunks
```
</ex-metadata-enrichment>

<ex-mixed-directory>
Load a mixed-type directory in one pass.

```python
from langchain_community.document_loaders import DirectoryLoader, PyPDFLoader
from langchain_community.document_loaders import Docx2txtLoader, TextLoader

loaders = {
    "**/*.pdf":  PyPDFLoader,
    "**/*.docx": Docx2txtLoader,
    "**/*.md":   TextLoader,
    "**/*.txt":  TextLoader,
}

all_docs = []
for glob_pattern, loader_cls in loaders.items():
    loader = DirectoryLoader(
        "./docs/",
        glob=glob_pattern,
        loader_cls=loader_cls,
        use_multithreading=True,
    )
    all_docs.extend(loader.load())

print(f"Loaded {len(all_docs)} documents")
```
</ex-mixed-directory>

<ex-qdrant-production>
Production ingestion with Qdrant — explicit vector config, collection naming convention.

```python
from langchain_community.vectorstores import Qdrant
from langchain_openai import OpenAIEmbeddings

embeddings = OpenAIEmbeddings(model="text-embedding-3-small")  # 1536 dims

vectorstore = Qdrant.from_documents(
    documents=chunks,
    embedding=embeddings,
    url="http://localhost:6333",
    collection_name="docs_text-embedding-3-small",  # encode model in name
    force_recreate=False,                            # True only on first run
)
```
</ex-qdrant-production>

---

## Common Mistakes

<fix-embedding-model-lock>
**WRONG** — switching embedding model without rebuilding the collection:
```python
# ❌ old collection: 1536-dim (text-embedding-3-small)
# new model: 384-dim (MiniLM) → dimension mismatch → garbage results
embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
vectorstore = Chroma(persist_directory="./chroma_db", embedding_function=embeddings)
results = vectorstore.similarity_search(query)  # silently broken
```

**CORRECT** — wipe the collection and re-ingest when changing models:
```python
# ✅ treat embedding model changes as a breaking schema change
import shutil
shutil.rmtree("./chroma_db")
chunks = splitter.split_documents(docs)
vectorstore = Chroma.from_documents(chunks, new_embeddings, persist_directory="./chroma_db")
# then re-run eval to confirm quality held
```
</fix-embedding-model-lock>

<fix-token-overflow>
**WRONG** — chunk_size that silently exceeds the model's token limit:
```python
# ❌ 8000 chars + 200-char overlap frequently hits the 8191-token hard limit
splitter = RecursiveCharacterTextSplitter(chunk_size=8000, chunk_overlap=200)
```

**CORRECT** — cap at 75% of the model's limit to leave headroom:
```python
# ✅ 6000 chars ≈ 1500 tokens — safe for text-embedding-3-small (8191 tok limit)
splitter = RecursiveCharacterTextSplitter(chunk_size=6000, chunk_overlap=600)
```
</fix-token-overflow>

<fix-missing-metadata>
**WRONG** — ingesting without metadata:
```python
# ❌ no source, doc_type, or chunk_index
# at query time: cannot cite sources or filter by document type
chunks = splitter.split_documents(pages)
vectorstore = Chroma.from_documents(chunks, embeddings)
```

**CORRECT** — always enrich before storing:
```python
# ✅ metadata enables citations and metadata filtering at retrieval time
chunks = enrich_chunks(chunks, source_path="docs/manual.pdf", doc_type="manual")
vectorstore = Chroma.from_documents(chunks, embeddings)
```
</fix-missing-metadata>

<fix-wrong-index-type>
**WRONG** — using FAISS Flat index for a production collection with 1M+ vectors:
```python
# ❌ Flat index = brute-force exhaustive search
# at 1M vectors, query latency grows to seconds
import faiss
index = faiss.IndexFlatL2(1536)
```

**CORRECT** — use HNSW for production; it gives 95%+ recall at sub-100ms latency:
```python
# ✅ HNSW — graph-based ANN, fast at scale
# Qdrant, Weaviate, Chroma all use HNSW by default
# For FAISS specifically:
index = faiss.IndexHNSWFlat(1536, 32)  # 32 = M parameter (connections per node)
```
</fix-wrong-index-type>

<fix-no-chunk-validation>
**WRONG** — ingesting without validating chunk quality:
```python
# ❌ blind ingest — no idea if chunks are empty, too large, or malformed
chunks = splitter.split_documents(pages)
vectorstore = Chroma.from_documents(chunks, embeddings)
```

**CORRECT** — inspect chunk distribution before committing to the vector store:
```python
# ✅ catch problems before they reach production
chunks = splitter.split_documents(pages)
lengths = [len(c.page_content) for c in chunks]
print(f"count={len(chunks)}, min={min(lengths)}, avg={int(sum(lengths)/len(lengths))}, max={max(lengths)}")

near_empty = [c for c in chunks if len(c.page_content.strip()) < 50]
if near_empty:
    print(f"WARNING: {len(near_empty)} near-empty chunks — check loader or splitter config")
```
</fix-no-chunk-validation>
