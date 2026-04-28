# Plan: ragforge-skills MVP

## Context

The PRD identifies `ragforge-skills` as the **highest-priority MVP deliverable** — it ships independently of the CLI and works with any coding agent that supports the skills standard (Claude Code, Gemini CLI, Cursor, Codex). The skills encode RAG best-practice knowledge as structured markdown files so coding agents can invoke them on demand. Building skills first unblocks agent-assisted development of the rest of ragforge.

---

## Directory Structure

```
ragforge-skills/
├── README.md                      # Human-facing install docs per agent
├── SKILLS.md                      # Machine-readable manifest / index
├── package.json                   # npm distribution (npx skills add ragforge/skills)
├── pyproject.toml                 # pip/uvx distribution (uvx ragforge setup)
├── ragforge-workflow/SKILL.md
├── ragforge-ingestion/SKILL.md
├── ragforge-retrieval/SKILL.md
├── ragforge-eval/SKILL.md
├── ragforge-observe/SKILL.md
└── ragforge-deploy/SKILL.md
```

---

## Skill Format (derived from existing Claude Code skills)

Each `SKILL.md` follows this structure:
1. **YAML frontmatter** — `name` (kebab-case, must match directory name) + `description` (agent-facing invoke trigger)
2. `<overview>` — ASCII pipeline diagram + one paragraph
3. Named `<*-selection>` tables — decision matrices (the core knowledge)
4. `<ex-*>` tags — each wraps `<python>` and/or `<bash>` code blocks
5. `<boundaries>` — CAN / CANNOT list (always last before fixes)
6. `<fix-*>` tags — WRONG / CORRECT pattern pairs for common mistakes

---

## The 6 Skills (write in this order — each builds on previous)

### 1. `ragforge-workflow/SKILL.md`
**Frontmatter trigger:** "INVOKE THIS SKILL at the start of any RAG project or when deciding what next step to take."

Key sections:
- `<overview>` — lifecycle diagram: `Ingest → Retrieve → Generate → Evaluate → Observe → Deploy` with feedback loop
- `<phase-map>` — table: Goal → Phase → `ragforge` CLI command
- `<when-to-use>` — routes user intent to the correct skill (e.g., "my answers got worse" → `ragforge-observe`)
- `<ex-project-init>` — `ragforge init my-project --prototype --yes` + annotated `ragforge.yaml` skeleton
- `<ex-ragforge-yaml>` — every top-level key with inline explanation
- `<ex-iteration-loop>` — day-2 cycle: ingest → query → eval → observe → adjust yaml → repeat
- `<lifecycle-sequencing>` — which skill to load at each phase
- `<fix-yaml-first>` — WRONG: hand-coded Python pipeline. CORRECT: `ragforge init` → edit yaml → use CLI

### 2. `ragforge-ingestion/SKILL.md`
**Frontmatter trigger:** "INVOKE when configuring loaders, chunking strategy, or embedding models."

Key sections:
- `<overview>` — pipeline: `Raw Files → Loader → Splitter → Chunks → Embedder → Vectors → Store`; critical constraint: embedding model is locked at index time
- `<loader-selection>` — table: File type → Loader class → Notes (PDF, DOCX, TXT, MD, HTML, Directory)
- `<chunking-strategy>` — decision table: Content type → Strategy → chunk_size → chunk_overlap → Why
- `<embedding-selection>` — table: Model → Dims → Max tokens → Best for → Cost (all 4 MVP models)
- `<vector-store-selection>` — Chroma vs Qdrant use case table
- `<ex-basic-ingestion>` — full PDF → Chroma pipeline
- `<ex-hybrid-loader>` — mixed directory with `DirectoryLoader`
- `<ex-metadata-enrichment>` — attaching `source`, `section`, `ingested_at`, `chunk_index`
- `<ex-qdrant-ingestion>` — Qdrant collection creation with explicit vector config
- `<fix-embedding-model-lock>`, `<fix-token-overflow>`, `<fix-missing-metadata>`, `<fix-dimensions-mismatch>`

### 3. `ragforge-retrieval/SKILL.md`
**Frontmatter trigger:** "INVOKE when choosing or tuning retrieval strategy."

Key sections:
- `<overview>` — three-tier stack: Dense → [Keyword/BM25] → [Reranker]
- `<strategy-selection>` — central decision table: Scenario → Strategy → Config value
- `<k-selection>` — table: Use case → recommended k → reasoning (including `fetch_k` for reranker)
- `<ex-dense-retrieval>` — similarity search with score threshold
- `<ex-hybrid-retrieval>` — `EnsembleRetriever` with BM25 + vector, weighted
- `<ex-reranker>` — Cohere `rerank()` wrapping dense results
- `<ex-metadata-filter>` — Chroma `where` filter and Qdrant `Filter`
- `<ex-mmr-retrieval>` — diversity search for summarization tasks
- `<fix-low-recall>`, `<fix-score-threshold>`, `<fix-reranker-fetch-k>`, `<fix-hybrid-weights>`

### 4. `ragforge-eval/SKILL.md`
**Frontmatter trigger:** "INVOKE when setting up evaluation, choosing metrics, defining thresholds, or building an evalset."

Key sections:
- `<overview>` — online eval (production sampling) vs offline eval (CI gate)
- `<metric-selection>` — table: Metric → What it measures → Threshold → Tool (all 7 metrics)
- `<evalset-construction>` — three methods table: Manual golden set vs LLM-generated vs Production sampling
- `<threshold-calibration>` — algorithm: baseline → regression = baseline−5% → target = baseline+10%
- `<ex-eval-run>`, `<ex-eval-compare>`, `<ex-eval-gate>` — CLI command flows
- `<ex-evalset-generation>` — LLM-generated JSONL evalset from chunks
- `<ex-evalset-format>` — JSONL schema ragforge expects
- `<ex-llm-judge>` — faithfulness judge prompt structure
- `<fix-circular-eval>`, `<fix-missing-baseline>`, `<fix-ci-gate>`

### 5. `ragforge-observe/SKILL.md`
**Frontmatter trigger:** "INVOKE when adding instrumentation, debugging a quality regression, or configuring exporters."

Key sections:
- `<overview>` — 4-layer model with metrics per layer
- `<exporter-selection>` — table: Langfuse / OTLP / Arize Phoenix / Console JSON
- `<layer-1-ingestion>` → `<ex-ingestion-telemetry>` — `chunk_count`, `coverage_pct`, `duplicate_rate`
- `<layer-2-retrieval>` → `<ex-retrieval-telemetry>` — `retrieved_k`, `top_score`, `latency_ms`, `hit`
- `<layer-3-generation>` → `<ex-generation-telemetry>` — `faithfulness_score`, `tokens_in`, `tokens_out`
- `<layer-4-system>` → `<ex-system-telemetry>` — cost from token counts, p95 latency, cache hit rate
- `<ex-langfuse-setup>` — full trace/span/generation hierarchy
- `<ex-debug-regression>` — regression workflow table linking layers together
- `<fix-missing-trace-correlation>`, `<fix-console-exporter-only>`, `<fix-cost-calculation>`

### 6. `ragforge-deploy/SKILL.md`
**Frontmatter trigger:** "INVOKE when containerizing, provisioning infrastructure, or deploying a ragforge pipeline."

Key sections:
- `<overview>` — 4-service topology: API (stateless) + Qdrant (stateful) + Langfuse (stateful) + LLM (external)
- `<target-selection>` — decision table: Scenario → Target → `ragforge deploy` command
- `<ex-docker-compose>` — generated `docker-compose.yml` structure
- `<ex-dockerfile>` — multi-stage, `python:3.11-slim`, non-root, health check
- `<ex-aws-ecs>` — Terraform/CDK skeleton for ECS Fargate + EFS + ALB
- `<ex-gcp-cloudrun>` — Cloud Run yaml with `min-instances=1` + Filestore
- `<ex-env-config>` — table: ragforge.yaml key → env var name → required
- `<ex-ci-deploy-gate>` — GitHub Actions: eval gate → pass → deploy
- `<fix-qdrant-ephemeral>`, `<fix-api-key-in-image>`, `<fix-cold-start>`

---

## Packaging Files

### `package.json`
```json
{
  "name": "@ragforge/skills",
  "version": "0.1.0",
  "description": "RAG development skills for coding agents",
  "license": "Apache-2.0",
  "files": ["ragforge-workflow/", "ragforge-ingestion/", "ragforge-retrieval/",
            "ragforge-eval/", "ragforge-observe/", "ragforge-deploy/", "SKILLS.md"]
}
```

### `pyproject.toml`
Standard hatch/setuptools config. Script entrypoint `ragforge-skills install` copies skill dirs to `~/.claude/skills/` (or agent-detected path).

### `SKILLS.md` — manifest table

| Skill | Description | Invoke When |
|---|---|---|
| ragforge-workflow | Full RAG lifecycle | Starting a project or unsure of next step |
| ragforge-ingestion | Loaders, chunking, embeddings | Configuring data ingestion |
| ragforge-retrieval | Dense / hybrid / reranker logic | Choosing or tuning retrieval |
| ragforge-eval | Metrics, thresholds, CI gate | Setting up or debugging evaluation |
| ragforge-observe | 4-layer instrumentation | Adding telemetry or debugging regressions |
| ragforge-deploy | Docker, IaC, cloud targets | Containerizing or deploying |

---

## Execution Sequence

1. **Scaffold** — create `ragforge-skills/` dir + `package.json` + `pyproject.toml` + `README.md` + 6 subdirs
2. **Write skills** in dependency order: workflow → ingestion → retrieval → eval → observe → deploy
3. **Write index** — `SKILLS.md` manifest table
4. **Validate** — all frontmatter parses as YAML; every `<ex-*>` has a code block; every `<fix-*>` has WRONG+CORRECT; skill `name` matches directory

---

## Critical Files

| File | Purpose |
|---|---|
| `ragforge-skills/SKILLS.md` | Agent-facing manifest / index |
| `ragforge-skills/ragforge-workflow/SKILL.md` | Lifecycle orchestrator skill |
| `ragforge-skills/ragforge-ingestion/SKILL.md` | Ingestion + chunking skill |
| `ragforge-skills/ragforge-retrieval/SKILL.md` | Retrieval strategy skill |
| `ragforge-skills/ragforge-eval/SKILL.md` | Evaluation + CI gate skill |
| `ragforge-skills/ragforge-observe/SKILL.md` | 4-layer observability skill |
| `ragforge-skills/ragforge-deploy/SKILL.md` | Deployment targets skill |
| `ragforge-skills/package.json` | npm distribution |
| `ragforge-skills/pyproject.toml` | pip/uvx distribution |

---

## Verification

1. Run `python -c "import yaml; yaml.safe_load(open('SKILL.md').read().split('---')[1])"` on all 6 files — should parse cleanly.
2. Copy skill dirs to `~/.claude/skills/`, restart Claude Code session, verify skills appear in `/skills` list.
3. Ask a RAG question that should trigger `ragforge-ingestion` — confirm agent loads the skill and applies the chunking strategy table correctly.
4. Run `npm pack` in `ragforge-skills/` and verify tarball contains all 6 skill directories.
