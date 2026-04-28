---
name: rag-observe
description: INVOKE THIS SKILL when adding instrumentation, debugging a quality regression, or configuring observability exporters. Covers the 4-layer RAG instrumentation model (ingestion, retrieval, generation, system), Langfuse tracing, OpenTelemetry/OTLP, Arize Phoenix, cost tracking, and latency SLOs.
---

<overview>

## RAG Observability

You cannot improve what you cannot see. Observability answers the question: "Which layer of my pipeline caused this bad answer?"

```
 LAYER 1: INGESTION          LAYER 2: RETRIEVAL         LAYER 3: GENERATION       LAYER 4: SYSTEM
 ────────────────────        ───────────────────        ───────────────────       ──────────────────
 chunk_count                 latency_ms (p50/p95)       faithfulness_score        end_to_end_p99_ms
 embedding_time_ms           top_similarity_score       tokens_in / tokens_out    error_rate
 duplicate_rate              k_retrieved                cost_per_query            success_rate
 coverage_score              hit_rate                   generation_latency_ms     cache_hit_rate
                             cache_hit_rate             hallucination_rate        cost_per_day
```

**What each layer tells you:**

| Layer | What it reveals | When to look here |
|---|---|---|
| Ingestion | Chunk quality, embedding coverage, index health | After re-ingestion, poor recall across all queries |
| Retrieval | Whether the right docs are found | Context recall is low; relevant info clearly exists in docs |
| Generation | Whether the LLM uses the retrieved context | Retrieval looks fine but answers still hallucinate |
| System | End-to-end health, cost, tail latency | SLO breaches, cost spikes, after scaling events |

**The two tools you need:**
1. **Traces** (Langfuse / Arize Phoenix) — spans per request, show what happened for one specific query
2. **Metrics** (OpenTelemetry → Prometheus/Grafana) — aggregates over time, show trends and SLOs

Use traces to debug individual failures. Use metrics to detect regressions before users do.

</overview>

---

<layer-1-ingestion>

## Layer 1: Ingestion Metrics

Ingestion runs offline (not per query) but bad ingestion silently kills retrieval quality.

| Metric | What it catches | Alert threshold |
|---|---|---|
| `chunk_count` | Index completeness | Drop > 5% vs last run |
| `embedding_time_ms` | Embedding bottleneck | > 10,000ms per batch |
| `duplicate_rate_pct` | Noisy duplicates | > 10% |
| `avg_chunk_tokens` | Chunks too big (diluted embedding) or too small (no context) | Outside 200–800 token window |
| `failed_docs_count` | Parse failures | Any > 0 (log the filenames) |
| `coverage_score` | Topic gaps in index | < 80% |

</layer-1-ingestion>

---

<ex-ingestion-telemetry>

## Example: Ingestion Telemetry

```python
import time
from langfuse import Langfuse

langfuse = Langfuse()

def ingest_with_telemetry(documents: list, chunk_strategy: str, chunk_size: int) -> dict:
    """Wrap your ingestion pipeline to emit structured telemetry."""
    span = langfuse.span(
        name="document_ingestion",
        input={
            "doc_count": len(documents),
            "chunk_strategy": chunk_strategy,
            "chunk_size": chunk_size,
        },
    )

    t0 = time.time()
    chunks = []
    failed = []
    seen_hashes = set()
    duplicates = 0

    for doc in documents:
        try:
            doc_chunks = split_document(doc, chunk_size=chunk_size)
            for chunk in doc_chunks:
                h = hash(chunk.page_content)
                if h in seen_hashes:
                    duplicates += 1
                else:
                    seen_hashes.add(h)
                    chunks.append(chunk)
        except Exception as e:
            failed.append({"source": doc.metadata.get("source"), "error": str(e)})

    embed_t0 = time.time()
    vectorstore.add_documents(chunks)
    embedding_time_ms = (time.time() - embed_t0) * 1000

    total_time_ms = (time.time() - t0) * 1000
    avg_tokens = sum(count_tokens(c.page_content) for c in chunks) / max(len(chunks), 1)

    span.update(
        output={
            "total_chunks": len(chunks),
            "duplicate_count": duplicates,
            "failed_doc_count": len(failed),
            "failed_docs": failed,
        },
        metadata={
            "embedding_time_ms": embedding_time_ms,
            "total_time_ms": total_time_ms,
            "avg_chunk_tokens": avg_tokens,
            "duplicate_rate_pct": (duplicates / max(len(chunks) + duplicates, 1)) * 100,
        },
    )
    langfuse.flush()

    return {
        "chunks": len(chunks),
        "duplicates": duplicates,
        "failed": len(failed),
        "avg_tokens": avg_tokens,
        "embedding_time_ms": embedding_time_ms,
    }
```

</ex-ingestion-telemetry>

---

<layer-2-retrieval>

## Layer 2: Retrieval Metrics

| Metric | What it catches | Target | Alert |
|---|---|---|---|
| `retrieval_latency_ms` (p95) | Slow vector search | < 500ms | > 1,000ms |
| `top_similarity_score` | Query-index mismatch | > 0.7 | < 0.5 |
| `k_retrieved` | Retriever returning fewer docs than expected | == configured k | < k |
| `hit_rate` | Relevant doc in top-k (from sampled eval) | > 80% | < 70% |
| `embedding_cache_hit_rate` | Repeated queries not cached | > 60% | < 40% |

</layer-2-retrieval>

---

<ex-retrieval-telemetry>

## Example: Retrieval Telemetry

```python
import time

def retrieve_with_telemetry(
    query: str,
    retriever,
    trace_id: str,
) -> list:
    span = langfuse.span(
        name="vector_retrieval",
        trace_id=trace_id,
        input={"query": query},
    )

    t0 = time.time()
    docs = retriever.invoke(query)
    latency_ms = (time.time() - t0) * 1000

    scores = [doc.metadata.get("score", None) for doc in docs]
    top_score = max((s for s in scores if s is not None), default=None)

    span.update(
        output={
            "k_retrieved": len(docs),
            "doc_ids": [doc.metadata.get("id", i) for i, doc in enumerate(docs)],
            "top_score": top_score,
        },
        metadata={
            "retrieval_latency_ms": latency_ms,
            "scores": scores,
        },
    )

    return docs
```

```python
# Tracking retrieval hit rate over time (sampled online eval)
import random

def retrieval_hit_rate_sample(query: str, docs: list, ground_truth_ids: list | None, rate: float = 0.10) -> None:
    """Sample 10% of queries and check if relevant doc was retrieved."""
    if not ground_truth_ids or random.random() > rate:
        return
    retrieved_ids = {doc.metadata.get("id") for doc in docs}
    hit = bool(retrieved_ids & set(ground_truth_ids))
    langfuse.create_score(
        trace_id=langfuse.get_current_trace_id(),
        name="retrieval_hit",
        value=1.0 if hit else 0.0,
        data_type="boolean",
    )
```

</ex-retrieval-telemetry>

---

<layer-3-generation>

## Layer 3: Generation Metrics

| Metric | What it catches | Target | Alert |
|---|---|---|---|
| `faithfulness_score` | LLM hallucinating despite good retrieval | > 0.85 | < 0.75 |
| `tokens_in` | Prompt bloat (too much context) | < 4,000 | > 8,000 |
| `tokens_out` | Unexpectedly verbose or truncated answers | domain-specific | sudden change |
| `generation_latency_ms` (p95) | Model latency SLO | < 2,000ms | > 5,000ms |
| `cost_per_query` | Cost efficiency | < $0.05 | > $0.10 |

**LLM token pricing (as of 2025–2026):**

| Model | Input (per 1M tokens) | Output (per 1M tokens) | Cache discount |
|---|---|---|---|
| GPT-4o | $2.50 | $10.00 | 50% on cached input |
| Claude 3.5 Sonnet | $3.00 | $15.00 | 50% on cached input |
| Claude Opus 4 | $15.00 | $75.00 | 50% on cached input |
| Gemini 2.5 Pro | $1.25 | $10.00 | 50% on cached input |
| Gemini 2.5 Flash | $0.30 | $2.50 | 50% on cached input |

</layer-3-generation>

---

<ex-generation-telemetry>

## Example: Generation Telemetry

```python
import time

PRICING = {
    "gpt-4o":              {"input": 2.50,  "output": 10.00, "cache": 1.25},
    "claude-3-5-sonnet":   {"input": 3.00,  "output": 15.00, "cache": 1.50},
    "gemini-2-5-pro":      {"input": 1.25,  "output": 10.00, "cache": 0.625},
    "gemini-2-5-flash":    {"input": 0.30,  "output": 2.50,  "cache": 0.15},
}

def calculate_cost(model: str, input_tokens: int, output_tokens: int, cached_tokens: int = 0) -> float:
    rates = PRICING.get(model, PRICING["gpt-4o"])
    fresh = input_tokens - cached_tokens
    input_cost  = (fresh * rates["input"] + cached_tokens * rates["cache"]) / 1_000_000
    output_cost = output_tokens * rates["output"] / 1_000_000
    return round(input_cost + output_cost, 6)


def generate_with_telemetry(
    query: str,
    contexts: list[str],
    llm_client,
    model: str,
    trace_id: str,
) -> str:
    messages = [
        {"role": "system", "content": "Answer only from the provided context. If unsure, say so."},
        {"role": "user",   "content": f"Context:\n{chr(10).join(contexts)}\n\nQuestion: {query}"},
    ]

    generation = langfuse.generation(
        name="llm_answer",
        trace_id=trace_id,
        model=model,
        input=messages,
    )

    t0 = time.time()
    response = llm_client.chat.completions.create(model=model, messages=messages, temperature=0)
    latency_ms = (time.time() - t0) * 1000

    answer = response.choices[0].message.content
    usage  = response.usage
    cost   = calculate_cost(model, usage.prompt_tokens, usage.completion_tokens)

    generation.update(
        output=answer,
        usage={
            "input":  usage.prompt_tokens,
            "output": usage.completion_tokens,
            "total":  usage.total_tokens,
        },
        metadata={
            "generation_latency_ms": latency_ms,
            "cost_usd": cost,
            "model": model,
        },
    )

    return answer
```

```python
# Attaching an async faithfulness score after generation
def score_generation_async(trace_id: str, query: str, answer: str, contexts: list[str]) -> None:
    """Score faithfulness in the background; don't block the user response."""
    import threading

    def _score():
        score = score_faithfulness(contexts="\n\n".join(contexts), answer=answer)
        langfuse.create_score(
            trace_id=trace_id,
            name="faithfulness",
            value=score["faithfulness_score"],
            data_type="numeric",
            comment=str(score.get("hallucinated_claims", [])),
        )
        langfuse.flush()

    threading.Thread(target=_score, daemon=True).start()
```

</ex-generation-telemetry>

---

<layer-4-system>

## Layer 4: System Metrics

| Metric | What it catches | Target | Alert |
|---|---|---|---|
| `e2e_latency_ms` (p99) | Tail latency SLO | < 3,000ms | > 5,000ms |
| `error_rate_pct` | Pipeline failures | < 1% | > 2% |
| `success_rate_pct` | Queries returning valid answers | > 99% | < 95% |
| `fallback_rate_pct` | Queries needing retry/fallback | < 5% | > 10% |
| `cost_per_day_usd` | Budget burn | budget-dependent | > daily budget |
| `llm_cache_hit_rate` | Repeated queries not cached | > 60% | < 30% |

</layer-4-system>

---

<ex-system-telemetry>

## Example: System-Level Telemetry with OpenTelemetry

```python
from opentelemetry import metrics as otel_metrics
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.exporter.prometheus import PrometheusMetricReader
from prometheus_client import start_http_server

# Start Prometheus scrape endpoint on port 8000
start_http_server(8000)
reader = PrometheusMetricReader()
MeterProvider(metric_readers=[reader])

meter = otel_metrics.get_meter("rag.system")

e2e_latency    = meter.create_histogram("rag_e2e_latency_ms",   description="End-to-end query latency")
query_counter  = meter.create_counter("rag_queries_total",       description="Total queries by outcome")
cost_counter   = meter.create_counter("rag_cost_usd_total",      description="Cumulative cost in USD")
cache_hit_rate = meter.create_observable_gauge(
    "rag_cache_hit_rate",
    callbacks=[lambda obs: obs.observe(_cache.hit_rate, {})],
    description="LLM response cache hit rate",
)


def rag_query(question: str) -> str:
    """Full RAG pipeline with system-level telemetry."""
    import time

    t0 = time.time()
    outcome = "success"

    try:
        trace = langfuse.trace(name="rag_query", input={"question": question})
        docs   = retrieve_with_telemetry(question, retriever, trace.id)
        answer = generate_with_telemetry(question, [d.page_content for d in docs], llm, MODEL, trace.id)
        trace.update(output={"answer": answer})
        score_generation_async(trace.id, question, answer, [d.page_content for d in docs])
        return answer

    except Exception as e:
        outcome = "error"
        raise

    finally:
        elapsed_ms = (time.time() - t0) * 1000
        e2e_latency.record(elapsed_ms,  {"model": MODEL})
        query_counter.add(1,            {"outcome": outcome})
        if outcome == "success":
            cost = calculate_cost(MODEL, last_input_tokens, last_output_tokens)
            cost_counter.add(cost,      {"model": MODEL})
```

```python
# Prometheus alert rules (alerts.yml)
ALERT_RULES = """
groups:
  - name: rag_slos
    rules:
      - alert: RAGTailLatencyHigh
        expr: histogram_quantile(0.99, rate(rag_e2e_latency_ms_bucket[5m])) > 5000
        for: 5m
        annotations:
          summary: "p99 latency {{ $value }}ms exceeds 5s SLO"

      - alert: RAGErrorRateHigh
        expr: rate(rag_queries_total{outcome="error"}[5m]) / rate(rag_queries_total[5m]) > 0.02
        for: 5m
        annotations:
          summary: "Error rate {{ $value | humanizePercentage }} exceeds 2%"

      - alert: RAGDailyCostExceeded
        expr: increase(rag_cost_usd_total[24h]) > 100
        for: 1m
        annotations:
          summary: "Daily RAG spend ${{ $value }} exceeds $100 budget"
"""
```

</ex-system-telemetry>

---

<ex-langfuse-setup>

## Example: Full Langfuse Trace (End-to-End)

```python
from langfuse import Langfuse
from langfuse.decorators import observe, langfuse_context

langfuse = Langfuse(
    public_key=os.environ["LANGFUSE_PUBLIC_KEY"],
    secret_key=os.environ["LANGFUSE_SECRET_KEY"],
    host="https://cloud.langfuse.com",   # or your self-hosted URL
)


# Decorator approach — simplest; wraps the entire function as a trace
@observe()
def rag_pipeline(question: str, user_id: str) -> dict:
    # Add metadata to the current trace
    langfuse_context.update_current_trace(
        user_id=user_id,
        tags=["production", "v2"],
        metadata={"app": "support-bot"},
    )

    docs   = retrieve(question)     # child span auto-created
    answer = generate(question, docs)  # child span auto-created

    return {"answer": answer, "sources": [d.metadata["source"] for d in docs]}


# Manual approach — more control over span names and metadata
def rag_pipeline_manual(question: str, user_id: str) -> dict:
    trace = langfuse.trace(
        name="rag_query",
        user_id=user_id,
        input={"question": question},
        tags=["production"],
    )

    # Retrieval span
    ret_span = trace.span(name="retrieval", input={"query": question})
    docs = retriever.invoke(question)
    ret_span.end(output={"k": len(docs), "top_score": docs[0].metadata.get("score")})

    # Generation span
    gen = trace.generation(
        name="llm_answer",
        model="gpt-4o",
        input=[{"role": "user", "content": question}],
    )
    answer = llm.invoke(question, context=docs)
    gen.end(
        output=answer,
        usage={"input": answer.usage.input_tokens, "output": answer.usage.output_tokens},
        metadata={"cost_usd": calculate_cost("gpt-4o", answer.usage.input_tokens, answer.usage.output_tokens)},
    )

    trace.update(output={"answer": answer.content})
    langfuse.flush()

    return {"answer": answer.content, "trace_id": trace.id}
```

**Langfuse self-hosted (Docker Compose):**
```yaml
# docker-compose.yml — minimal Langfuse stack
services:
  langfuse-server:
    image: langfuse/langfuse:latest
    ports: ["3000:3000"]
    environment:
      DATABASE_URL: postgresql://postgres:postgres@db/langfuse
      NEXTAUTH_SECRET: change-me-in-production
      SALT: change-me-in-production
      NEXTAUTH_URL: http://localhost:3000
    depends_on: [db]

  db:
    image: postgres:15
    environment:
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: langfuse
    volumes: ["pgdata:/var/lib/postgresql/data"]

volumes:
  pgdata:
```

</ex-langfuse-setup>

---

<ex-arize-phoenix>

## Example: Arize Phoenix (Auto-Instrumentation)

Phoenix auto-instruments LangChain, LlamaIndex, OpenAI SDK, and other frameworks via OpenTelemetry.

```python
import phoenix as px
from phoenix.otel import register

# Start Phoenix server (local)
session = px.launch_app()

# Register auto-instrumentation — instruments LangChain, LlamaIndex, OpenAI automatically
tracer_provider = register(
    project_name="my-rag-project",
    endpoint="http://127.0.0.1:6006/v1/traces",  # Phoenix OTLP endpoint
)

# Now just run your RAG pipeline normally — Phoenix captures all spans
from langchain_openai import ChatOpenAI
from langchain_community.vectorstores import Chroma

llm = ChatOpenAI(model="gpt-4o")   # every call is traced automatically
vectorstore = Chroma(...)           # every similarity_search is traced automatically

# View traces in Phoenix UI at http://127.0.0.1:6006
print(f"Phoenix dashboard: {session.url}")
```

```python
# Phoenix with LlamaIndex — full auto-instrumentation
from llama_index.core import Settings, VectorStoreIndex
import llama_index.core

llama_index.core.set_global_handler("arize_phoenix")  # single line enables Phoenix tracing

index = VectorStoreIndex.from_documents(docs)
query_engine = index.as_query_engine()
response = query_engine.query("What is the refund policy?")
# Full trace captured: embedding → retrieval → synthesis
```

**Phoenix vs Langfuse — when to choose:**

| Scenario | Use |
|---|---|
| Need prompt management + eval pipelines | Langfuse |
| Need auto-instrumentation with zero code changes | Arize Phoenix |
| Already using LangChain/LlamaIndex | Either (both auto-instrument) |
| Need custom span metadata and scoring | Langfuse |
| Want visual trace comparison UI out of the box | Arize Phoenix |
| Self-hosted with Postgres backend | Langfuse |

</ex-arize-phoenix>

---

<exporter-selection>

## Exporter Selection

| Exporter | Best for | Setup effort | Self-hosted |
|---|---|---|---|
| **Langfuse** | Full RAG dev lifecycle — traces + evals + prompts | Low (SDK decorators) | Yes (Docker) |
| **Arize Phoenix** | Auto-instrumentation, visual debugging | Very low (one line) | Yes |
| **OTLP → Jaeger** | Distributed tracing, microservices | Medium | Yes |
| **OTLP → Grafana Tempo** | Time-series traces paired with Prometheus metrics | Medium | Yes |
| **OTLP → Honeycomb** | High-cardinality production analysis | Low (managed) | No (SaaS) |
| **Console JSON** | Local development only | Zero | N/A |

**Minimum production setup:** Langfuse (traces + eval scores) + Prometheus + Grafana (system metrics + alerting).

```bash
# Environment variables for OTLP export
export OTEL_EXPORTER_OTLP_ENDPOINT="http://localhost:4317"
export OTEL_EXPORTER_OTLP_PROTOCOL="grpc"
export OTEL_SERVICE_NAME="rag-api"
export OTEL_RESOURCE_ATTRIBUTES="deployment.environment=production"
```

</exporter-selection>

---

<ex-debug-regression>

## Example: Debugging a Quality Regression

When eval scores drop, traces give you the evidence to identify which layer failed.

```python
# Step 1 — pull low-scoring traces from Langfuse
from langfuse import Langfuse

langfuse = Langfuse()

# Fetch traces scored below faithfulness threshold
failing_traces = langfuse.get_traces(
    tags=["production"],
    # filter by score in Langfuse UI, or post-process here:
)

# Step 2 — classify each failure
results = {"retrieval_failure": [], "generation_failure": [], "unknown": []}

for trace in failing_traces:
    spans = {s.name: s for s in trace.observations}

    retrieval_span = spans.get("vector_retrieval") or spans.get("retrieval")
    generation_span = spans.get("llm_answer") or spans.get("generation")

    if not retrieval_span:
        results["unknown"].append(trace.id)
        continue

    top_score = retrieval_span.metadata.get("top_score", 1.0) if retrieval_span.metadata else 1.0
    faithfulness = next(
        (s.value for s in trace.scores if s.name == "faithfulness"), None
    )

    if top_score < 0.5:
        # Retrieval didn't find relevant docs
        results["retrieval_failure"].append({
            "trace_id": trace.id,
            "query": trace.input,
            "top_score": top_score,
            "k_retrieved": retrieval_span.output.get("k_retrieved") if retrieval_span.output else None,
        })
    elif faithfulness is not None and faithfulness < 0.75:
        # Retrieval was OK, LLM hallucinated
        results["generation_failure"].append({
            "trace_id": trace.id,
            "query": trace.input,
            "answer": trace.output,
            "faithfulness": faithfulness,
        })

# Step 3 — print diagnosis
print(f"Retrieval failures : {len(results['retrieval_failure'])}")
print(f"Generation failures: {len(results['generation_failure'])}")
print(f"Unknown failures   : {len(results['unknown'])}")

if len(results["retrieval_failure"]) > len(results["generation_failure"]):
    print("\nPRIMARY CAUSE: Retrieval")
    print("Actions: check k, hybrid alpha, re-chunk, verify embedding model")
else:
    print("\nPRIMARY CAUSE: Generation")
    print("Actions: tighten system prompt, reduce context noise, lower temperature")
```

**Regression diagnosis decision table:**

| Retrieval top_score | Context Recall | Faithfulness | Root cause | Fix |
|---|---|---|---|---|
| < 0.5 | Low | Low | Retrieval miss — wrong embedding or missing chunk | Re-chunk, check embedding model, increase k |
| > 0.7 | High | Low | LLM hallucinating despite good context | Tighten system prompt, reduce context size, switch model |
| > 0.7 | Low | High | Retrieval finds partial info, LLM extrapolates | Increase k, add hybrid search, check chunking |
| > 0.7 | High | High | Healthy | Nothing broken; look at answer relevancy |
| Varies | Varies | Varies | Recent deployment | Compare span metadata before/after deployment timestamp |

</ex-debug-regression>

---

<boundaries>

## Boundaries

**This skill CAN help you:**
- Instrument all 4 RAG layers with the right metrics
- Set up Langfuse traces with spans, generation records, and programmatic scoring
- Configure OpenTelemetry + Prometheus for system-level SLOs and alerting
- Use Arize Phoenix for auto-instrumented tracing with zero code changes
- Calculate cost per query from token counts with current pricing
- Debug a quality regression by classifying it as retrieval or generation failure
- Set alert thresholds for latency, cost, error rate, and faithfulness

**This skill CANNOT:**
- Fix retrieval quality problems — see `rag-retrieval`
- Fix generation quality or hallucinations — see `rag-eval` for scoring patterns
- Build evaluation pipelines or LLM-as-judge prompts — see `rag-eval`
- Deploy the observability stack (Docker, K8s, managed cloud) — see `rag-deploy`

</boundaries>

---

<fix-missing-trace-correlation>

## Fix: Only Logging the Final Answer

**WRONG** — no structured trace, no way to correlate retrieval with generation:
```python
answer = rag_pipeline(question)
print(f"Q: {question} | A: {answer}")
# When answer is wrong: you have no idea which layer failed
```

**CORRECT** — full trace with retrieval and generation spans:
```python
from langfuse.decorators import observe

@observe()  # creates trace + child spans automatically
def rag_pipeline(question: str) -> str:
    docs   = retrieve(question)   # captured as child span
    answer = generate(question, docs)  # captured as child span
    return answer
# Now: every bad answer has a trace_id → inspect exactly what was retrieved and generated
```

**Why:** Without traces, debugging a bad answer requires guesswork. With traces, you can open one specific failing query and see: top retrieval score was 0.3 (retrieval miss), or retrieval was fine but the LLM ignored it (generation failure). These require completely different fixes.

</fix-missing-trace-correlation>

---

<fix-no-retrieval-context-in-trace>

## Fix: Missing Retrieval Context in Trace

**WRONG** — retrieval happens but nothing is captured:
```python
@observe()
def answer(question: str) -> str:
    docs = retriever.invoke(question)
    return llm.invoke(question)
# Traces show the question and final answer — but what was retrieved?
```

**CORRECT** — explicitly record retrieved documents in the span:
```python
@observe()
def answer(question: str) -> str:
    ret_span = langfuse.span(name="retrieval", input={"query": question})
    docs = retriever.invoke(question)
    ret_span.end(output={
        "k_retrieved": len(docs),
        "top_score": docs[0].metadata.get("score") if docs else None,
        "doc_ids": [d.metadata.get("id", i) for i, d in enumerate(docs)],
        "preview": docs[0].page_content[:200] if docs else None,
    })
    return llm.invoke(question)
# Now: you can inspect exactly which chunks were retrieved for every failing query
```

**Why:** The most common debugging scenario is "the answer is wrong." Without seeing what was retrieved, you cannot distinguish between "wrong chunk retrieved" and "right chunk retrieved, LLM hallucinated." These require different fixes.

</fix-no-retrieval-context-in-trace>

---

<fix-console-exporter-only>

## Fix: Console Logging Only

**WRONG** — all observability goes to stdout:
```python
print(f"Retrieved {len(docs)} docs, top score: {score:.3f}")
print(f"Answer: {answer}")
print(f"Latency: {latency_ms:.0f}ms")
# Not queryable, not aggregatable, lost after log rotation
```

**CORRECT** — structured metrics to Prometheus, traces to Langfuse:
```python
# Metrics: queryable, time-series, alertable
e2e_latency.record(latency_ms, {"model": MODEL, "env": "production"})
query_counter.add(1, {"outcome": "success"})

# Traces: per-request, debuggable, searchable by score/tag/user
trace = langfuse.trace(name="rag_query", input={"question": question})
# ...

# Logs: structured JSON for correlation
import structlog
log = structlog.get_logger()
log.info("rag_query_completed", latency_ms=latency_ms, trace_id=trace.id, cost=cost)
```

**Why:** Console logs cannot be aggregated into a p99 latency chart, cannot be filtered to "all queries where faithfulness < 0.7 in the last 24h," and cannot trigger alerts. Structured metrics and traces are queryable after the fact.

</fix-console-exporter-only>

---

<fix-cost-calculation>

## Fix: Not Tracking Cost Per Query

**WRONG** — cost tracked only as a monthly invoice surprise:
```python
response = llm.invoke(prompt)
# "We'll see the cost on the OpenAI bill next month"
```

**CORRECT** — calculate and record cost per query in the trace:
```python
response = llm_client.chat.completions.create(model=MODEL, messages=messages)
usage = response.usage

cost = calculate_cost(
    model=MODEL,
    input_tokens=usage.prompt_tokens,
    output_tokens=usage.completion_tokens,
    cached_tokens=getattr(usage, "prompt_tokens_cached", 0),
)

langfuse.generation(
    ...,
    usage={"input": usage.prompt_tokens, "output": usage.completion_tokens},
    metadata={"cost_usd": cost},
)
cost_counter.add(cost, {"model": MODEL})

# Alert when daily spend exceeds budget
if daily_cost_total > DAILY_BUDGET_USD:
    send_alert(f"Daily RAG spend ${daily_cost_total:.2f} exceeds ${DAILY_BUDGET_USD} budget")
```

**Why:** Without per-query cost tracking, you cannot identify which query types are expensive, whether a model upgrade is cost-justified, or catch a runaway prompt before it burns your budget. A 10× cost spike from a single bad deployment is detectable in minutes with per-query tracking and invisible until invoice day without it.

</fix-cost-calculation>

