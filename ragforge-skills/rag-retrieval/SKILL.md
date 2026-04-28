---
name: rag-retrieval
description: INVOKE THIS SKILL when choosing or tuning retrieval strategy. Covers dense vs hybrid vs reranker decision logic, k-selection, metadata filtering, MMR for diversity, score threshold calibration, HyDE, and parent-document retrieval.
---

<overview>

## RAG Retrieval

Retrieval is the quality bottleneck of your RAG pipeline. Poor retrieval cannot be fixed downstream — the LLM can only answer well if the right documents are in its context.

```
 User Query
     │
     ▼
[Query Transform?]  ── optional: HyDE, query expansion, sub-question decomposition
     │
     ▼
[Pre-filter]        ── narrow search space by metadata (date, category, access level)
     │
     ▼
[Retrieval Tier 1]  ── dense vector | BM25 | hybrid (both)
     │
     ▼
[Retrieval Tier 2]  ── optional: reranker (cross-encoder scores query-document pairs)
     │
     ▼
[Post-filter]       ── optional: score threshold, deduplication, MMR diversity
     │
     ▼
 Top-k Documents → LLM Context
```

**Three compounding layers:**
1. **Base retrieval** — dense vector search, BM25 keyword search, or hybrid (both fused with RRF)
2. **Reranking** — cross-encoder re-scores top candidates for precision (Cohere Rerank, BGE Reranker)
3. **Diversity / dedup** — MMR or deduplication to avoid redundant context

Each layer adds latency and cost. Add layers only when the quality improvement justifies it.

</overview>

---

<strategy-selection>

## Strategy Selection

| Scenario | Strategy | Initial k | Final m | Notes |
|---|---|---|---|---|
| Simple Q&A, latency-critical | Dense vector only | 5–10 | 5–10 | No reranker |
| Enterprise docs with product codes / IDs | Hybrid (BM25 + dense) | 20–40 | 10–20 | Exact terms matter |
| High-precision answers required | Hybrid → Reranker | 40–75 | 5–10 | 20–35% accuracy gain |
| Diverse multi-topic corpus | Hybrid + MMR | 20–40 | 10 | Prevents redundant context |
| Long-form docs (books, research) | Parent-document retrieval | 40–60 (child) | 5–10 (parent) | Small chunks retrieved, large chunks sent to LLM |
| Complex / exploratory queries | HyDE + Hybrid + Reranker | 40–75 | 5–10 | Extra LLM call; not for factual lookups |
| Large scale (millions of docs) | ColBERT or IVF index + Reranker | 50–100 | 10–20 | Pre-index required |
| Research / synthesis | Hybrid + Reranker | 50–100 | 20–50 | Wide context needed |

**Default starting point for most production RAG:** Hybrid → Reranker with initial k=50, final m=5–10.

</strategy-selection>

---

<hybrid-weights>

## Hybrid Search Weights

Hybrid search fuses BM25 (keyword) and dense (semantic) scores using **Reciprocal Rank Fusion (RRF)**:

```
RRF_score(d) = Σ  1 / (k + rank(d))
```

Or a weighted linear combination:
```
score(d) = alpha × normalized_dense + (1 - alpha) × normalized_bm25
```

| Alpha | Balance | Best for |
|---|---|---|
| 0.0 | Pure BM25 | Exact keyword matching only |
| 0.3–0.4 | BM25-leaning | Domain jargon, product codes, financial/legal docs |
| 0.5 | Equal | **Default starting point** |
| 0.6–0.7 | Dense-leaning | General enterprise Q&A |
| 1.0 | Pure dense | Semantic / conceptual queries |

**Tuning protocol:**
1. Start at alpha=0.5
2. Run eval on 30+ representative queries across your use cases
3. Grid-search alpha ∈ {0.3, 0.4, 0.5, 0.6, 0.7}, pick best MRR@10 or NDCG@10
4. Re-tune quarterly or after corpus updates

Most vector stores implement hybrid via RRF natively (Weaviate, Qdrant, Elasticsearch, Pinecone). Use RRF unless you have a reason to tune alpha manually — it is robust without tuning.

</hybrid-weights>

---

<k-selection>

## k Selection

Retrieval operates in two stages. Fetch broadly, then narrow.

| Stage | What | Typical k |
|---|---|---|
| Initial fetch (dense or hybrid) | Candidate pool | 20–100 |
| After reranking | Passed to LLM | 3–20 |

**No reranker:**

| Use case | k | Notes |
|---|---|---|
| Chat, low latency | 5–10 | Minimize context tokens |
| Standard Q&A | 10–20 | Balanced |
| Comprehensive research | 20–50 | Wider context |

**With reranker (two-stage):**

| Initial k (candidates) | Final m (to LLM) | Notes |
|---|---|---|
| 40–75 | 5–10 | Optimal NDCG@10 for most workloads |
| 75–100 | 10–20 | Noisy corpora, synthesis tasks |
| 100+ | 20–50 | Diminishing returns beyond 100 |

**Rule of thumb:** rerank 50 candidates → return top 5. Reranking more than 100 yields minimal gains while costs scale linearly.

</k-selection>

---

<score-thresholds>

## Score Threshold Calibration

Score thresholds filter out low-confidence results before passing to the LLM.

| Content quality | Recommended threshold | Effect |
|---|---|---|
| Well-curated, clean corpus | 0.3–0.5 | Permissive; max recall |
| Mixed enterprise content | 0.5–0.6 | Balanced |
| Noisy / diverse web content | 0.6–0.8 | Aggressive filter |
| Domain-specific (medical, legal) | 0.5–0.7 | Tune per domain |

**Calibration method:**
1. Pick 30–50 queries with known borderline-relevant documents
2. Record their similarity scores
3. Set threshold = mean(borderline scores)
4. Validate: hallucination rate should drop; recall should stay acceptable
5. Re-baseline after embedding model changes or corpus updates

**Warning:** Do not use score thresholds as a proxy for quality without calibration. Scores are not globally comparable across embedding models or corpora.

</score-thresholds>

---

<ex-dense-retrieval>

## Example: Dense Retrieval (LangChain + Chroma)

```python
from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings

vectorstore = Chroma(
    persist_directory="./chroma_db",
    embedding_function=OpenAIEmbeddings(model="text-embedding-3-large"),
)

retriever = vectorstore.as_retriever(
    search_type="similarity_score_threshold",
    search_kwargs={
        "k": 10,
        "score_threshold": 0.5,
    },
)

docs = retriever.invoke("What is the refund policy?")
```

```python
# LlamaIndex equivalent
from llama_index.core import VectorStoreIndex, StorageContext
from llama_index.vector_stores.chroma import ChromaVectorStore
import chromadb

chroma_client = chromadb.PersistentClient(path="./chroma_db")
collection = chroma_client.get_collection("my_collection")
vector_store = ChromaVectorStore(chroma_collection=collection)
index = VectorStoreIndex.from_vector_store(vector_store)

retriever = index.as_retriever(similarity_top_k=10)
nodes = retriever.retrieve("What is the refund policy?")
```

</ex-dense-retrieval>

---

<ex-hybrid-retrieval>

## Example: Hybrid Retrieval

```python
# LangChain: EnsembleRetriever (BM25 + dense)
from langchain.retrievers import EnsembleRetriever, BM25Retriever
from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings

# Build BM25 from raw docs
bm25_retriever = BM25Retriever.from_documents(documents, k=20)

# Build dense retriever
vectorstore = Chroma.from_documents(documents, OpenAIEmbeddings())
dense_retriever = vectorstore.as_retriever(search_kwargs={"k": 20})

# Ensemble: weights sum to 1.0; first weight = BM25, second = dense
hybrid_retriever = EnsembleRetriever(
    retrievers=[bm25_retriever, dense_retriever],
    weights=[0.4, 0.6],  # adjust based on your alpha tuning
)

docs = hybrid_retriever.invoke("invoice processing workflow")
```

```python
# Qdrant native hybrid (BM25 + dense, RRF fusion built-in)
from qdrant_client import QdrantClient
from qdrant_client.models import Query, FusionQuery, Fusion

client = QdrantClient(url="http://localhost:6333")

results = client.query_points(
    collection_name="my_collection",
    query=FusionQuery(fusion=Fusion.RRF),
    prefetch=[
        {"query": dense_vector, "using": "dense", "limit": 40},
        {"query": sparse_vector, "using": "sparse", "limit": 40},
    ],
    limit=20,
)
```

```python
# Weaviate hybrid search
import weaviate

client = weaviate.connect_to_local()
collection = client.collections.get("Document")

results = collection.query.hybrid(
    query="invoice processing workflow",
    alpha=0.5,          # 0 = pure BM25, 1 = pure vector
    limit=20,
)
```

</ex-hybrid-retrieval>

---

<ex-reranker>

## Example: Reranker (Two-Stage)

```python
# Cohere Rerank v3 after hybrid retrieval
import cohere
from langchain.retrievers import EnsembleRetriever

co = cohere.Client(api_key="YOUR_COHERE_API_KEY")

# Stage 1: broad hybrid fetch
hybrid_retriever = EnsembleRetriever(
    retrievers=[bm25_retriever, dense_retriever],
    weights=[0.4, 0.6],
)
candidates = hybrid_retriever.invoke(query)

# Stage 2: Cohere rerank
reranked = co.rerank(
    query=query,
    documents=[doc.page_content for doc in candidates],
    model="rerank-v3.5",
    top_n=5,            # return top 5 to LLM
)

# Retrieve top-n original doc objects in reranked order
top_docs = [candidates[r.index] for r in reranked.results]
```

```python
# BGE Reranker (open-source, self-hosted)
from FlagEmbedding import FlagReranker

reranker = FlagReranker("BAAI/bge-reranker-v2-m3", use_fp16=True)

# Format as (query, document) pairs
pairs = [[query, doc.page_content] for doc in candidates]
scores = reranker.compute_score(pairs)

# Sort by score descending
ranked = sorted(zip(scores, candidates), key=lambda x: x[0], reverse=True)
top_docs = [doc for _, doc in ranked[:5]]
```

```python
# LlamaIndex with Cohere Reranker
from llama_index.postprocessor.cohere_rerank import CohereRerank
from llama_index.core import VectorStoreIndex

index = VectorStoreIndex.from_documents(documents)
reranker = CohereRerank(api_key="YOUR_COHERE_API_KEY", top_n=5)

query_engine = index.as_query_engine(
    similarity_top_k=50,          # fetch 50 candidates
    node_postprocessors=[reranker] # rerank to top 5
)

response = query_engine.query("What is the refund policy?")
```

</ex-reranker>

---

<ex-metadata-filter>

## Example: Metadata Filtering

```python
# Chroma pre-filter (LangChain)
retriever = vectorstore.as_retriever(
    search_kwargs={
        "k": 10,
        "filter": {
            "$and": [
                {"doc_type": {"$eq": "policy"}},
                {"ingested_at": {"$gte": "2024-01-01"}},
            ]
        },
    }
)
```

```python
# Qdrant pre-filter
from qdrant_client.models import Filter, FieldCondition, MatchValue, Range

results = client.search(
    collection_name="my_collection",
    query_vector=query_vector,
    query_filter=Filter(
        must=[
            FieldCondition(key="doc_type", match=MatchValue(value="policy")),
            FieldCondition(key="year", range=Range(gte=2024)),
        ]
    ),
    limit=10,
)
```

```python
# Weaviate pre-filter
from weaviate.classes.query import Filter

results = collection.query.near_text(
    query="refund policy",
    filters=Filter.by_property("doc_type").equal("policy"),
    limit=10,
)
```

**Pre-filter vs post-filter guidance:**
- **Pre-filter** on immutable metadata (date, category, access level, language) — narrows search space, faster
- **Post-filter** on computed metadata (score ranges, dynamic tags) — simpler but processes more candidates
- **Recommended:** Broad pre-filter (e.g., date range) + fine-grained post-filter (confidence threshold)

</ex-metadata-filter>

---

<ex-mmr-retrieval>

## Example: MMR (Maximal Marginal Relevance)

MMR balances relevance and diversity. Use it when your corpus has near-duplicate documents or when the query spans multiple topics.

```python
# LangChain MMR retriever
retriever = vectorstore.as_retriever(
    search_type="mmr",
    search_kwargs={
        "k": 10,            # number of documents to return
        "fetch_k": 30,      # candidate pool to apply MMR over
        "lambda_mult": 0.5, # 1.0 = pure relevance, 0.0 = pure diversity
    }
)

docs = retriever.invoke("climate change economic impacts")
```

```python
# LlamaIndex MMR node postprocessor
from llama_index.core.postprocessor import MMRPostprocessor

mmr = MMRPostprocessor(similarity_cutoff=0.5, top_n=10)
query_engine = index.as_query_engine(
    similarity_top_k=30,
    node_postprocessors=[mmr],
)
```

**lambda_mult tuning:**
| Value | Behavior |
|---|---|
| 1.0 | Pure relevance (no diversity) |
| 0.5 | Balanced (default; start here) |
| 0.3 | More diversity |
| 0.0 | Pure diversity (not recommended) |

**When to use MMR:**
- Corpus contains near-duplicate documents (e.g., news articles, product variants)
- Query spans multiple independent sub-topics
- Summarization tasks where redundant context wastes the context window

**When NOT to use MMR:**
- Precise factual lookups — relevance always wins
- Single-topic deep dives — similar chunks are equally valid, not redundant

</ex-mmr-retrieval>

---

<ex-hyde>

## Example: HyDE (Hypothetical Document Embeddings)

HyDE closes the query-document language gap. Instead of embedding the question, use an LLM to generate a hypothetical answer, then embed the answer and search for real documents matching that pattern.

```python
from langchain.chains import HypotheticalDocumentEmbedder
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_community.vectorstores import Chroma

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
embeddings = OpenAIEmbeddings(model="text-embedding-3-large")

hyde_embeddings = HypotheticalDocumentEmbedder.from_llm(
    llm=llm,
    embeddings=embeddings,
    prompt_key="web_search",  # built-in prompt: generates 1 hypothetical doc
)

vectorstore = Chroma(embedding_function=hyde_embeddings, persist_directory="./chroma_db")
docs = vectorstore.similarity_search("What are best practices for database indexing?", k=10)
```

```python
# Manual HyDE (more control over hypothetical prompt)
from openai import OpenAI

client = OpenAI()

def hyde_retrieve(query: str, vectorstore, k: int = 10) -> list:
    # Step 1: generate hypothetical answer
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "Write a short factual passage that directly answers the question."},
            {"role": "user", "content": query},
        ],
    )
    hypothetical_doc = response.choices[0].message.content

    # Step 2: embed hypothetical doc and search
    return vectorstore.similarity_search(hypothetical_doc, k=k)
```

**When to use HyDE:**
- Exploratory / conceptual queries ("what are best practices for X?")
- Domain-specific search where query phrasing differs from document phrasing
- Complex multi-part questions

**When NOT to use HyDE:**
- Factual lookups ("reset password link") — exact match is better
- Latency-critical paths — adds one LLM call (~500ms–2s)
- Simple keyword searches — BM25 alone is sufficient

</ex-hyde>

---

<ex-parent-document>

## Example: Parent-Document Retrieval

Index small child chunks for precise embeddings; retrieve large parent chunks for rich LLM context.

```python
# LangChain ParentDocumentRetriever
from langchain.retrievers import ParentDocumentRetriever
from langchain.storage import InMemoryStore
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings

# Child splitter: small chunks for precise embeddings
child_splitter = RecursiveCharacterTextSplitter(chunk_size=400, chunk_overlap=50)

# Parent splitter: large chunks for rich LLM context
parent_splitter = RecursiveCharacterTextSplitter(chunk_size=2000, chunk_overlap=200)

vectorstore = Chroma(embedding_function=OpenAIEmbeddings())
docstore = InMemoryStore()  # use Redis or similar for production

retriever = ParentDocumentRetriever(
    vectorstore=vectorstore,
    docstore=docstore,
    child_splitter=child_splitter,
    parent_splitter=parent_splitter,
)

retriever.add_documents(documents)

# Retrieval: searches child embeddings, returns parent documents
docs = retriever.invoke("how does the refund process work?")
# docs contain full parent chunks (~2000 tokens each)
```

**When to use:**
- Long-form documents (books, research papers, lengthy technical docs)
- LLM answers are missing context (relevant chunk found but surrounding info needed)
- Acceptable indexing overhead (2× storage for parent + child)

**Not necessary for:**
- Short self-contained documents (FAQs, product descriptions)
- Already-structured content where each section is independent
- Speed-critical systems

</ex-parent-document>

---

<reranker-selection>

## Reranker Selection

| Reranker | Type | Quality | Latency | Cost | Best for |
|---|---|---|---|---|---|
| Cohere rerank-v3.5 | API (managed) | ★★★★★ | ~100–300ms/batch | Pay-per-use | Production; no infra overhead |
| Cohere rerank-v4.0 | API (managed) | ★★★★★ | ~100–300ms/batch | Pay-per-use | Long queries (16k token input) |
| BAAI/bge-reranker-v2-m3 | OSS (self-host) | ★★★★☆ | ~50–150ms/batch (GPU) | Infra cost | Cost-sensitive production |
| BAAI/bge-reranker-large | OSS (self-host) | ★★★★☆ | ~50–150ms/batch (GPU) | Infra cost | English-only, high precision |
| cross-encoder/ms-marco-MiniLM | OSS (self-host) | ★★★☆☆ | ~20–50ms/batch (CPU) | Low | CPU-only, acceptable quality |
| ColBERT (RAGatouille) | OSS (self-host) | ★★★★★ | Sub-ms (pre-indexed) | High indexing | Large-scale, pre-indexed corpora |

**Cohere rerank v3.5 token limits:**
- Query: max 2,048 tokens (truncated if longer)
- Total context: 32,768 tokens
- Documents: auto-chunked if individual docs are too long (pre-chunk yourself for consistent control)

</reranker-selection>

---

<boundaries>

## Boundaries

**This skill CAN help you:**
- Choose between dense / hybrid / reranker strategies
- Set initial k, final m, and alpha values with a principled starting point
- Configure score thresholds using calibration data
- Implement MMR for diversity, HyDE for query transformation, parent-document for context richness
- Wire up Cohere Rerank, BGE Reranker, or ColBERT
- Apply metadata pre-filters and post-filters correctly

**This skill CANNOT:**
- Tune hyperparameters without your evaluation data — numbers here are starting points, not ground truth
- Predict optimal alpha or k for your specific corpus without benchmarking
- Recommend which embedding model to use — see `rag-ingestion`
- Advise on LLM prompt construction after retrieval — see `rag-workflow`
- Configure observability for retrieval quality — see `rag-observe`

</boundaries>

---

<fix-low-recall>

## Fix: Low Recall — Relevant Documents Not Retrieved

**WRONG** — undersized k with tight threshold:
```python
retriever = vectorstore.as_retriever(
    search_kwargs={"k": 3, "score_threshold": 0.8}
)
# Relevant document has score 0.72 — never retrieved
```

**CORRECT** — fetch broadly, filter after reranking:
```python
# Stage 1: loose fetch
candidates = vectorstore.similarity_search(query, k=50)

# Stage 2: rerank
reranked = co.rerank(query=query, documents=[d.page_content for d in candidates], top_n=10)

# Stage 3: apply threshold only to final ranked results
top_docs = [candidates[r.index] for r in reranked.results if r.relevance_score > 0.4]
```

**Why:** Score thresholds that are calibrated on raw vector similarity become too tight when applied pre-reranking. Reranker scores are more reliable — apply thresholds there.

</fix-low-recall>

---

<fix-score-threshold>

## Fix: Miscalibrated Score Threshold

**WRONG** — using a hardcoded threshold without calibration:
```python
# "0.7 sounds safe" — not calibrated to your corpus
search_kwargs={"score_threshold": 0.7}
# Result: drops 40% of relevant documents
```

**CORRECT** — calibrate on representative borderline queries:
```python
# Collect 30-50 queries where you know relevant documents exist
borderline_scores = []
for query, known_relevant_doc in calibration_set:
    results = vectorstore.similarity_search_with_score(query, k=20)
    for doc, score in results:
        if doc.page_content == known_relevant_doc:
            borderline_scores.append(score)

threshold = sum(borderline_scores) / len(borderline_scores)
print(f"Calibrated threshold: {threshold:.3f}")
# Use threshold - 0.05 for a small safety margin
```

**Why:** Similarity scores are corpus-dependent and embedding-model-dependent. There is no universal safe threshold.

</fix-score-threshold>

---

<fix-reranker-fetch-k>

## Fix: Reranker Not Improving Quality

**WRONG** — reranking too few candidates:
```python
candidates = vectorstore.similarity_search(query, k=5)
reranked = co.rerank(query=query, documents=[d.page_content for d in candidates], top_n=5)
# Reranker can only reshuffle 5 items — no meaningful improvement
```

**CORRECT** — fetch a large candidate pool, then rerank down:
```python
# Fetch 50 candidates for reranker to work with
candidates = vectorstore.similarity_search(query, k=50)
reranked = co.rerank(query=query, documents=[d.page_content for d in candidates], top_n=5)
# Reranker can now surface the best 5 from 50 candidates — meaningful signal
```

**Why:** The reranker's job is to find the best few from many. If you give it 5 docs to rank down to 5, it does nothing. The recall improvement comes from the large initial pool.

</fix-reranker-fetch-k>

---

<fix-hybrid-weights>

## Fix: Hybrid Search Not Beating Dense-Only

**WRONG** — using default equal weights without tuning on your query mix:
```python
# alpha=0.5 assumed optimal; never validated
hybrid_retriever = EnsembleRetriever(
    retrievers=[bm25_retriever, dense_retriever],
    weights=[0.5, 0.5],
)
```

**CORRECT** — evaluate alpha on your actual query distribution:
```python
from langchain.retrievers import EnsembleRetriever

results = {}
for alpha in [0.3, 0.4, 0.5, 0.6, 0.7]:
    bm25_weight = 1 - alpha
    dense_weight = alpha
    retriever = EnsembleRetriever(
        retrievers=[bm25_retriever, dense_retriever],
        weights=[bm25_weight, dense_weight],
    )
    # Evaluate MRR@10 on your eval set
    results[alpha] = evaluate_mrr(retriever, eval_queries)

best_alpha = max(results, key=results.get)
print(f"Best alpha: {best_alpha}, MRR@10: {results[best_alpha]:.3f}")
```

**Why:** For domain-specific corpora with specialized terminology (legal, medical, financial, technical), BM25 often outweighs dense. For general conversational queries, dense dominates. You cannot know without measuring.

</fix-hybrid-weights>

---

<fix-no-query-transform>

## Fix: Query-Document Language Mismatch

**WRONG** — embedding user question directly when document vocabulary differs:
```python
# User: "How do I get my money back?"
# Document: "Refund eligibility criteria and reimbursement procedures"
# Low similarity score despite high relevance
docs = vectorstore.similarity_search("How do I get my money back?", k=5)
```

**CORRECT** — use HyDE or query rewriting to bridge the vocabulary gap:
```python
from openai import OpenAI

client = OpenAI()

def rewrite_query(query: str) -> str:
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "Rewrite the query using formal, document-style language that would appear in policy or technical documents."},
            {"role": "user", "content": query},
        ],
    )
    return response.choices[0].message.content

rewritten = rewrite_query("How do I get my money back?")
# → "Refund request procedure and reimbursement eligibility"
docs = vectorstore.similarity_search(rewritten, k=10)
```

**Why:** User queries are conversational; knowledge base documents are formal. Embedding a hypothetical answer or a rewritten formal query produces an embedding closer to document space, significantly improving recall.

</fix-no-query-transform>

