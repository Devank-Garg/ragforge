# ragforge — PRD v0.1

> **The RAG Development Kit.** CLI-first, wizard-driven, best-in-class observability. Provider-agnostic by design.

---

## Document Info

| Field | Value |
|---|---|
| Version | 0.1 — MVP |
| Status | Draft — For Review |
| Author | DEVANK / YMSLI AI Team |
| Date | April 2026 |
| Horizon | Week 1 Deliverable |

---

## What Is ragforge?

ragforge is an open-source, CLI-first RAG development kit that takes any developer — individual or enterprise — from zero to a production-grade RAG pipeline in minutes.

Inspired by Google's Agents CLI architecture, it cleanly separates:

- **`ragforge-core`** — provider-agnostic pipeline engine (pip-installable standalone)
- **`ragforge`** — lifecycle CLI (wizard → ingest → eval → deploy)
- **`ragforge-skills`** — RAG knowledge package for coding agents (Claude Code, Gemini CLI, Cursor, Codex)

---

## The One-Liner

```
ragforge init my-project --prototype --yes
```

Produces a working local RAG pipeline. Under 5 minutes. No code written.

---

## RAG Skills — MVP Priority

The skills package is the **highest-priority MVP deliverable**. It ships independently of the CLI and works with any coding agent that supports the skills standard.

```bash
# Install skills into your coding agent
npx skills add ragforge/skills
# OR
uvx ragforge setup
```

### Skill Files

| Skill | What It Teaches |
|---|---|
| `ragforge-workflow` | Full RAG development lifecycle |
| `ragforge-ingestion` | Chunking strategies, embedding model compatibility |
| `ragforge-retrieval` | Dense vs hybrid vs reranker decision logic |
| `ragforge-eval` | Metrics, thresholds, evalset construction |
| `ragforge-observe` | 4-layer instrumentation patterns |
| `ragforge-deploy` | Docker, IaC, cloud target patterns |

---

## CLI Commands

```bash
ragforge init [name]              # Guided wizard → ragforge.yaml
ragforge ingest                   # Run ingestion pipeline
ragforge query "<question>"       # Single-turn test
ragforge eval run                 # Full eval suite
ragforge eval compare v1 v2       # Diff two runs
ragforge eval gate                # CI pass/fail (exit code)
ragforge observe                  # Open dashboard
ragforge deploy --target docker   # Deploy
```

---

## Observability — The Differentiator

4-layer instrumentation from day one. No other open-source RAG tool does this.

| Layer | Metrics |
|---|---|
| Ingestion | Chunk count, coverage %, duplicate rate |
| Retrieval | Hit rate @k, MRR, NDCG, latency p95 |
| Generation | Faithfulness, relevance, hallucination proxy |
| System | Token cost, LLM latency, cache hit rate |

Exporters: Langfuse (primary), OTLP, Arize Phoenix, Console JSON (always-on fallback).

---

## Week 1 Plan

| Day | Focus | Done When |
|---|---|---|
| 1 | Scaffold + Wizard | `ragforge init` produces valid yaml |
| 2 | Ingestion Core | `ragforge ingest` indexes a PDF |
| 3 | Retrieval + Query | `ragforge query` returns cited answer |
| 4 | Observability MVP | Langfuse shows all 4 layers |
| 5 | Eval + Gate | Gate returns non-zero on regression |
| 6 | RAG Skills MVP | Skills visible in two coding agents |
| 7 | Packaging + Launch | Public repo live, `pip install ragforge` works |

---

## Provider Matrix (MVP)

| Layer | MVP Adapters |
|---|---|
| Embeddings | OpenAI text-embedding-3-small/large, sentence-transformers |
| Vector Store | Chroma (local), Qdrant |
| LLM | OpenAI GPT-4o/mini, Anthropic Claude, Ollama |
| Reranker | Cohere Rerank |
| Loaders | PDF, DOCX, TXT, MD, HTML |

---

## vs The Competition

| | LlamaIndex | LangChain | **ragforge** |
|---|---|---|---|
| Entry point | Python code | Python code | **CLI wizard** |
| Observability layers | 1 | 1 | **4** |
| Eval CI gate | Manual | Manual | **Native** |
| Coding agent skills | None | None | **First-class** |
| Time to first RAG | 30–60 min | 30–60 min | **< 5 min** |
| Provider lock-in | Low | Low | **Zero** |

---

## License

Apache 2.0
