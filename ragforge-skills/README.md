# ragforge-skills

RAG development skills for coding agents. Teaches Claude Code, Gemini CLI, Cursor, and Codex best-practice patterns for every phase of the RAG lifecycle.

## Install

```bash
# npm / npx
npx skills add ragforge/skills

# pip / uvx
uvx ragforge setup
```

## Manual install (Claude Code)

```bash
cp -r ragforge-workflow ragforge-ingestion ragforge-retrieval \
      ragforge-eval ragforge-observe ragforge-deploy \
      ~/.claude/skills/
```

## Skills

| Skill | Invoke When |
|---|---|
| `ragforge-workflow` | Starting a new RAG project or unsure of the next step |
| `ragforge-ingestion` | Configuring loaders, chunking strategy, or embedding models |
| `ragforge-retrieval` | Choosing or tuning retrieval strategy |
| `ragforge-eval` | Setting up evaluation, metrics, thresholds, or CI gate |
| `ragforge-observe` | Adding instrumentation or debugging quality regressions |
| `ragforge-deploy` | Containerizing, provisioning, or deploying to cloud |

## License

Apache 2.0
