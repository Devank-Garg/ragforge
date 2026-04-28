# rag-skills

Framework-agnostic RAG development skills for coding agents. Teaches best-practice patterns for every phase of the RAG lifecycle — works with LangChain, LlamaIndex, custom stacks, or ragforge.

## Install

```bash
# npm / npx
npx skills add ragforge/rag-skills

# pip / uvx
uvx ragforge setup
```

## Manual install (Claude Code)

```bash
cp -r rag-workflow rag-ingestion rag-retrieval \
      rag-eval rag-observe rag-deploy \
      ~/.claude/skills/
```

## Skills

| Skill | Invoke When |
|---|---|
| `rag-workflow` | Starting a new RAG project or unsure of next step |
| `rag-ingestion` | Configuring loaders, chunking strategy, or embedding models |
| `rag-retrieval` | Choosing or tuning retrieval strategy |
| `rag-eval` | Setting up evaluation, metrics, thresholds, or CI gate |
| `rag-observe` | Adding instrumentation or debugging quality regressions |
| `rag-deploy` | Containerizing, provisioning, or deploying to cloud |

## License

Apache 2.0
