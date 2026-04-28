# @ragforge/rag-skills

Framework-agnostic RAG development skills for coding agents. Teaches best-practice patterns for every phase of the RAG lifecycle — works with LangChain, LlamaIndex, any custom stack.

Installs 5 skills into Claude Code (or any agent that reads from `~/.claude/skills/`):

| Skill | Invoke when |
|---|---|
| `/rag-workflow` | Starting a new RAG project or unsure of next step |
| `/rag-ingestion` | Configuring loaders, chunking strategy, or embedding models |
| `/rag-retrieval` | Choosing or tuning retrieval strategy |
| `/rag-eval` | Setting up evaluation, metrics, thresholds, or CI gate |
| `/rag-observe` | Adding instrumentation or debugging quality regressions |

## Install

```bash
npx @ragforge/rag-skills
```

That copies all 5 skills to `~/.claude/skills/`. Restart Claude Code and the skills are available immediately.

## Manual install

```bash
git clone https://github.com/Devank-Garg/ragforge.git
cp -r ragforge/ragforge-skills/rag-workflow \
      ragforge/ragforge-skills/rag-ingestion \
      ragforge/ragforge-skills/rag-retrieval \
      ragforge/ragforge-skills/rag-eval \
      ragforge/ragforge-skills/rag-observe \
      ~/.claude/skills/
```

## Usage

After install, invoke any skill directly in Claude Code:

```
/rag-ingestion
/rag-eval
```

Or let the agent load the right skill automatically — each skill's `description` field tells the agent when to invoke it.

## What's in each skill

**rag-workflow** — lifecycle diagram, phase-to-skill routing table, component selection guide, iteration loop patterns.

**rag-ingestion** — loader selection (9 file types), 8-strategy chunking decision table, MTEB leaderboard link + top embedding models, vector store comparison (7 stores, index types, built-in chunking capabilities).

**rag-retrieval** — dense vs hybrid vs reranker decision logic, alpha tuning protocol, k-selection tables, score threshold calibration, HyDE, parent-document retrieval, metadata filtering.

**rag-eval** — all core RAG metrics with formulas and worked examples, LLM-as-judge prompt templates, 3 evalset construction methods, RAGAS + DeepEval CI gate integration, threshold calibration protocol, root cause diagnosis decision tree.

**rag-observe** — 4-layer instrumentation model (ingestion/retrieval/generation/system), full Langfuse trace setup, Arize Phoenix auto-instrumentation, OpenTelemetry + Prometheus SLOs, cost tracking with current LLM pricing, regression debugging workflow.

## Requirements

- Node.js >= 16.7.0 (for `fs.cpSync`)
- Claude Code (or any agent that reads skills from `~/.claude/skills/`)

## License

Apache 2.0
