---
name: rag-eval
description: INVOKE THIS SKILL when setting up evaluation, choosing metrics, defining thresholds, building an evalset, or debugging quality regressions. Covers all core RAG metrics, LLM-as-judge patterns, evalset construction, CI gate integration, and the most common eval anti-patterns.
---

<overview>

## RAG Evaluation

Most teams skip evaluation and then wonder why their RAG system hallucinates in production. Evaluation is not optional — it is the only way to know whether your changes made things better or worse.

```
 BUILD PHASE                         DEPLOY PHASE                    PRODUCTION
 ──────────────────────────────────  ──────────────────────────────  ──────────────────────
                                                                     
  Evalset ──► Offline Eval           CI Gate (every PR)              Online Eval (sampling)
  (golden + synthetic)               │                               │
       │                             ├── context_precision > 0.80    ├── sample 10-20% queries
       ▼                             ├── context_recall > 0.80       ├── LLM-as-judge scores
  Baseline metrics                   ├── faithfulness > 0.85         ├── alert on drift > 5%
  (recorded before any change)       └── answer_relevancy > 0.75    └── feed failures into evalset
       │
       ▼
  Regression threshold = baseline − 5%
  Target = baseline + 10%
```

**Two failure modes eval catches:**

| Failure | What it means | Metric that catches it |
|---|---|---|
| Retrieval failure | Right answer not in retrieved docs | Context Recall ↓ |
| Generation failure | Retrieved docs are right, LLM still hallucinated | Faithfulness ↓ |

Always diagnose retrieval and generation separately. A faithfulness score of 0.6 with context recall of 0.9 means your LLM is hallucinating despite good retrieval. The same faithfulness score with context recall of 0.4 means your retrieval is missing the relevant docs.

</overview>

---

<metric-definitions>

## Core Metrics — What Each Measures

### Faithfulness (Groundedness)

**What it measures:** The fraction of claims in the generated answer that are supported by the retrieved context. Detects hallucination.

```
faithfulness = (claims in answer supported by context) / (total claims in answer)
```

**Example:**
```
Answer: "Product X costs $100 and ships in 2 days using drone delivery."
Context: "Product X is priced at $100. Standard shipping takes 2 business days."

Claims:
  ✓ "costs $100"         → supported by "priced at $100"
  ✓ "ships in 2 days"    → supported by "2 business days"
  ✗ "using drone delivery" → not in context (hallucination)

faithfulness = 2/3 = 0.67  ← this system is making up delivery methods
```

**Threshold by risk level:**
| Context | Target | Minimum |
|---|---|---|
| Internal tools, prototype | 0.75 | 0.70 |
| General-purpose Q&A | 0.85 | 0.80 |
| Customer-facing product | 0.90 | 0.85 |
| Finance / healthcare / legal | 0.95 | 0.90 |

---

### Context Precision

**What it measures:** Whether the relevant documents retrieved are ranked higher than irrelevant ones. Penalizes noise at the top of the retrieval list.

```
context_precision@k = Σ(precision@i × relevance_i) / total_relevant_in_top_k
```

**Example:**
```
Retrieved: [Doc1✓, Doc2✗, Doc3✓]   (✓ = relevant, ✗ = not relevant)
Reference: [Doc1, Doc3]

Precision@1 = 1/1 = 1.0  (Doc1 is relevant)
Precision@2 = 1/2 = 0.5  (1 relevant in first 2)
Precision@3 = 2/3 = 0.67 (2 relevant in first 3)

context_precision = (1.0×1 + 0.5×0 + 0.67×1) / 2 = 0.835
```

**Why it matters:** A noisy retrieval list forces the LLM to reason across irrelevant material, increasing hallucination risk and wasting context tokens.

**Production threshold:** > 0.80

---

### Context Recall

**What it measures:** Whether all the information needed to answer the query was retrieved. Penalizes missed relevant documents.

```
context_recall = (claims in reference answer supported by retrieved context) / (total claims in reference)
```

**Example:**
```
Reference answer: "The refund window is 30 days and requires the original receipt."
Claims: ["30-day refund window", "original receipt required"]

Context retrieved: "Returns accepted within 30 days."
  ✓ Claim 1: supported
  ✗ Claim 2: missing from context

context_recall = 1/2 = 0.5  ← half the needed info was not retrieved
```

**Production threshold:** > 0.80 (many teams target 0.90 for comprehensive Q&A)

---

### Answer Relevancy

**What it measures:** Whether the generated answer actually addresses the question asked. Penalizes off-topic, verbose, or tangential answers.

```
answer_relevancy = avg cosine_similarity(generated_question_i, original_question)
                   where generated_question_i is a question reverse-engineered from the answer
```

RAGAS generates N synthetic questions from the answer and checks if they match the original question. An answer that drifts off-topic generates different questions.

**Production threshold:** > 0.75

---

### Answer Correctness (Reference-based)

**What it measures:** Factual correctness of the answer against a known ground truth. Requires a reference answer.

```
answer_correctness = F1(claims_in_answer, claims_in_reference)
                   = harmonic_mean(precision, recall)
```

Use when you have a golden dataset with known correct answers. Do not use for open-ended questions without a single correct answer.

---

### When NOT to use BLEU / ROUGE

| Metric | Use case | RAG verdict |
|---|---|---|
| BLEU | Machine translation, n-gram overlap | Not for RAG — too strict on wording |
| ROUGE-L | Summarization tasks only | Limited use; misses semantic meaning |
| BERTScore | Semantic similarity with embeddings | Acceptable supplement but not primary |
| Exact match | Structured output (JSON, SQL, IDs) | Use only when output format is fixed |

For RAG: use faithfulness + context precision/recall + answer relevancy + LLM-as-judge.

</metric-definitions>

---

<metric-selection>

## Which Metrics to Run — Decision Table

| Goal | Primary metrics | Secondary metrics |
|---|---|---|
| Debug hallucinations | Faithfulness | Context Recall |
| Debug missed answers | Context Recall | Context Precision |
| Debug off-topic answers | Answer Relevancy | Faithfulness |
| Debug noisy retrieval | Context Precision | Context Recall |
| Full CI gate | All 4 core metrics | — |
| Quick sanity check | Faithfulness + Context Recall | — |
| Comparing two configs | All 4 core + delta | Statistical significance |
| Regulated domain | All 4 core + Answer Correctness | Human review on 10% |

**Minimum viable eval:** Faithfulness + Context Recall. These two together tell you whether your retrieval found the right content and whether your LLM stayed within it.

</metric-selection>

---

<evalset-construction>

## Evalset Construction

Your eval set is only as good as its questions. Most teams build one from scratch once and never update it — this is a mistake. Your eval set should evolve with your corpus and your users.

### Method 1: Golden Set (Manual)

**Minimum size:** 50 samples. For statistically confident regression detection (80% pass rate, 5% margin, 95% confidence): 246 samples.

**Process:**
1. Select 50–100 document chunks across all major topics in your corpus
2. For each chunk, a domain expert writes 1–2 questions only answerable from that chunk
3. Expert writes the ideal answer with citations to specific chunk text
4. Store as `(question, reference_answer, reference_chunk_ids)` triples
5. Verify: the answer should not be answerable from general knowledge alone

**Good vs bad evalset questions:**
| Type | Good | Bad |
|---|---|---|
| Factual | "What is the penalty fee for late payment per the service agreement?" | "What is a penalty fee?" |
| Procedural | "What are the steps to reset a locked account?" | "How do I reset things?" |
| Comparative | "What distinguishes the Pro plan from the Enterprise plan?" | "What plans exist?" |
| Edge case | "What happens if a refund request is submitted on day 31?" | "Can I get a refund?" |

**What makes it bad:**
- Answerable without your docs (general knowledge)
- Ambiguous with multiple valid answers
- Trivial (mentioned once, no reasoning required)
- Duplicate or near-duplicate
- Outdated after corpus update

---

### Method 2: LLM-Generated Synthetic Evalset

Fast to build but requires curation. Use a different LLM than your generation LLM.

```python
from openai import OpenAI
import json

client = OpenAI()

def generate_eval_pairs(chunk_text: str, source: str, n: int = 3) -> list[dict]:
    """Generate n QA pairs from a document chunk."""
    response = client.chat.completions.create(
        model="gpt-4o",  # use a strong model here; eval quality depends on it
        messages=[
            {
                "role": "system",
                "content": (
                    "You are building evaluation data for a RAG system. "
                    "Generate questions that:\n"
                    "1. Are ONLY answerable from the provided text — not general knowledge\n"
                    "2. Require understanding the text, not just keyword matching\n"
                    "3. Have a single clear correct answer\n"
                    "4. Cover different aspects (factual, procedural, comparative)\n\n"
                    "Return a JSON array of objects with keys: question, answer, difficulty (easy/medium/hard)"
                ),
            },
            {
                "role": "user",
                "content": f"Generate {n} QA pairs from this text:\n\n{chunk_text}",
            },
        ],
        response_format={"type": "json_object"},
    )
    pairs = json.loads(response.choices[0].message.content)
    # Attach source metadata
    for p in pairs.get("questions", []):
        p["source_chunk"] = source
    return pairs.get("questions", [])


# Build evalset from your document chunks
evalset = []
for chunk in document_chunks:
    pairs = generate_eval_pairs(chunk.page_content, chunk.metadata["source"])
    evalset.extend(pairs)

# Save as JSONL
with open("evalset.jsonl", "w") as f:
    for item in evalset:
        f.write(json.dumps(item) + "\n")
```

**Recommended ratio:** 60% synthetic + 40% manually curated golden.

---

### Method 3: Production Sampling

After launch, collect real user queries and label them:

```python
# Collect failed queries (user clicked "thumbs down" or rephrased immediately)
# Label: ideal answer + relevant chunk IDs
# Include in evalset — these are your hardest cases

# JSONL format:
{
    "question": "actual user query",
    "reference_answer": "what the ideal answer should have been",
    "reference_chunk_ids": ["chunk_001", "chunk_047"],
    "category": "retrieval_failure",  # or "hallucination", "off_topic", "good"
    "source": "production_sample"
}
```

**Evalset JSONL schema** (what evaluation frameworks expect):
```jsonl
{"question": "What is the cancellation fee?", "reference_answer": "The cancellation fee is $25 if cancelled within 48 hours.", "reference_chunk_ids": ["policy_v2_chunk_12"]}
{"question": "How long does standard shipping take?", "reference_answer": "Standard shipping takes 5-7 business days.", "reference_chunk_ids": ["shipping_policy_chunk_3"]}
```

</evalset-construction>

---

<llm-as-judge>

## LLM-as-Judge

When ground truth is not available (most production RAG), use an LLM to score your pipeline.

**Critical rule:** Never use the same LLM as judge that you use for generation. Self-enhancement bias: a model scores its own outputs 10–25% higher than an independent judge would.

| Generation LLM | Recommended Judge |
|---|---|
| GPT-4o | Claude 3.5 Sonnet or Gemini 1.5 Pro |
| Claude | GPT-4o |
| Gemini | Claude or GPT-4o |
| Any open-source | GPT-4o (most reliable judge) |

---

### Faithfulness Judge Prompt

```python
FAITHFULNESS_PROMPT = """You are evaluating whether a generated answer is faithful to the provided context.

CONTEXT:
{context}

GENERATED ANSWER:
{answer}

TASK:
1. Extract every factual claim from the generated answer.
2. For each claim, determine if it is directly supported by the context.
3. A claim is supported only if the context contains the same information (paraphrasing counts, invention does not).
4. Do not use outside knowledge — only the provided context.

Return JSON:
{{
  "claims": [
    {{"claim": "...", "supported": true, "evidence": "exact quote from context or null"}},
    ...
  ],
  "faithfulness_score": <float 0-1>,
  "hallucinated_claims": ["...", "..."]
}}

faithfulness_score = supported_claims / total_claims
"""
```

```python
import json
from openai import OpenAI

judge_client = OpenAI()  # different client/model than your generation client

def score_faithfulness(context: str, answer: str) -> dict:
    response = judge_client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "user", "content": FAITHFULNESS_PROMPT.format(
                context=context, answer=answer
            )},
        ],
        response_format={"type": "json_object"},
        temperature=0,  # deterministic scoring
    )
    return json.loads(response.choices[0].message.content)

result = score_faithfulness(
    context="Refunds must be requested within 30 days. Original receipt required.",
    answer="You can get a refund within 30 days by emailing support@company.com.",
)
print(result["faithfulness_score"])  # 0.5 — email claim unsupported
print(result["hallucinated_claims"])  # ["email support@company.com"]
```

---

### Answer Relevancy Judge Prompt

```python
RELEVANCY_PROMPT = """You are evaluating whether a generated answer directly addresses the question.

QUESTION:
{question}

GENERATED ANSWER:
{answer}

EVALUATE:
1. Does the answer directly address what was asked?
2. Is it on-topic throughout, or does it drift?
3. Are there key aspects of the question left unanswered?

Return JSON:
{{
  "relevancy_score": <float 0-1>,
  "addressed_aspects": ["..."],
  "missing_aspects": ["..."],
  "reasoning": "..."
}}

Scoring rubric:
1.0 = Fully addresses the question, no off-topic content
0.75 = Mostly addresses the question, minor gaps or tangents
0.5 = Partially addresses the question, significant gaps
0.25 = Tangentially related but mostly misses the point
0.0 = Completely off-topic
"""
```

---

### Chain-of-Thought Judge (for complex domains)

```python
COT_FAITHFULNESS_PROMPT = """CONTEXT:
{context}

ANSWER:
{answer}

Step 1 — List every distinct factual claim in the answer.
Step 2 — For each claim, copy the exact supporting phrase from the context, or write NULL if not found.
Step 3 — Count: total_claims, supported_claims.
Step 4 — faithfulness = supported_claims / total_claims

Show your work for each step. End with:
SCORE: <float 0-1>
UNSUPPORTED: [list of hallucinated claims]
"""
```

Chain-of-thought prompting reduces judge errors on complex answers by ~15–20%. Use it when your answers are long (>3 sentences) or the domain requires precise verification.

---

### Calibrating Your LLM Judge

Before trusting automated scores, validate against human reviewers:

1. Sample 100–300 (question, context, answer) triples
2. Have 2+ human reviewers score faithfulness and relevancy (same rubric as judge)
3. Compute agreement:
   - Spearman correlation ≥ 0.7 → judge is reliable
   - Spearman < 0.5 → refine judge prompt or switch judge model
4. Recheck after switching judge models or prompt changes

```python
from scipy.stats import spearmanr

human_scores = [0.9, 0.4, 0.8, 0.6, ...]   # from human reviewers
judge_scores = [0.88, 0.45, 0.77, 0.62, ...] # from LLM judge

correlation, p_value = spearmanr(human_scores, judge_scores)
print(f"Spearman r={correlation:.2f}, p={p_value:.4f}")
# Target: r >= 0.70
```

</llm-as-judge>

---

<eval-tools>

## Evaluation Framework Selection

| Framework | Best for | Metrics | CI/CD | Tracing | Notes |
|---|---|---|---|---|---|
| **RAGAS** | RAG-specific eval, fast setup | 5–7 core RAG metrics | Good | No | Reference-free; most RAG-specific; lightweight |
| **DeepEval** | Broad LLM eval + CI gates | 14+ metrics | Excellent (pytest) | No | Debuggable judges; best for automated CI |
| **TruLens** | Span-level diagnosis | 6–8 metrics | Good | Yes (OpenTelemetry) | Best discrimination ratio (4.2:1); pair with tracing |
| **Arize Phoenix** | Observability-first | Traces + metrics | Fair | Excellent | Best when you care about span-level debugging |
| **ARES** | Automated evalset generation | Auto-generated | Fair | No | Fine-tunes lightweight judges; reduces human annotation |
| **UpTrain** | Comprehensive but less accurate | 10+ metrics | Fair | Basic | Lowest ranking accuracy (27.6%); use others first |

**Recommendation for most teams:** RAGAS for metric computation + DeepEval for CI gate integration. Add TruLens or Arize Phoenix if you need span-level tracing (covered in `rag-observe`).

</eval-tools>

---

<ex-eval-run>

## Example: Running RAGAS Evaluation

```python
from ragas import evaluate
from ragas.metrics import (
    faithfulness,
    answer_relevancy,
    context_precision,
    context_recall,
)
from datasets import Dataset

# Your RAG pipeline output (collect this for each eval query)
eval_data = {
    "question": [
        "What is the cancellation fee?",
        "How long does standard shipping take?",
    ],
    "answer": [
        "The cancellation fee is $25 if cancelled within 48 hours.",
        "Standard shipping takes 5-7 business days.",
    ],
    "contexts": [
        # List of retrieved chunk texts per question
        ["Cancellations within 48 hours incur a $25 fee. After 48 hours, no fee applies."],
        ["Standard shipping: 5-7 business days. Express: 1-2 business days."],
    ],
    "ground_truth": [
        "The cancellation fee is $25 for cancellations within 48 hours.",
        "Standard shipping takes 5-7 business days.",
    ],
}

dataset = Dataset.from_dict(eval_data)

results = evaluate(
    dataset,
    metrics=[faithfulness, answer_relevancy, context_precision, context_recall],
    llm=...,          # pass your judge LLM (different from generation LLM)
    embeddings=...,   # for answer_relevancy cosine similarity
)

print(results)
# {'faithfulness': 0.94, 'answer_relevancy': 0.88, 'context_precision': 0.91, 'context_recall': 0.83}
```

```python
# Collecting eval data from your pipeline (instrument your retriever + generator)
def run_eval_query(question: str, retriever, llm_chain) -> dict:
    # Step 1: retrieve
    docs = retriever.invoke(question)
    contexts = [doc.page_content for doc in docs]

    # Step 2: generate
    answer = llm_chain.invoke({"question": question, "context": "\n\n".join(contexts)})

    return {
        "question": question,
        "answer": answer,
        "contexts": contexts,
        # Include ground_truth if you have a golden set
    }

eval_rows = [run_eval_query(q, retriever, chain) for q in eval_questions]
```

</ex-eval-run>

---

<ex-deepeval-ci>

## Example: DeepEval CI Gate (pytest)

```python
# tests/test_rag_quality.py
import pytest
from deepeval import assert_test
from deepeval.metrics import (
    FaithfulnessMetric,
    AnswerRelevancyMetric,
    ContextualPrecisionMetric,
    ContextualRecallMetric,
)
from deepeval.test_case import LLMTestCase

# Load your golden dataset
import json
with open("evalset.jsonl") as f:
    eval_cases = [json.loads(line) for line in f]


@pytest.fixture(scope="module")
def rag_pipeline():
    # Initialize your retriever + chain
    from your_rag_module import build_pipeline
    return build_pipeline()


@pytest.mark.parametrize("eval_case", eval_cases[:50])  # first 50 for CI speed
def test_rag_faithfulness(eval_case, rag_pipeline):
    result = rag_pipeline.run(eval_case["question"])

    test_case = LLMTestCase(
        input=eval_case["question"],
        actual_output=result["answer"],
        retrieval_context=result["contexts"],
        expected_output=eval_case.get("reference_answer"),
    )

    assert_test(test_case, [
        FaithfulnessMetric(threshold=0.85, model="gpt-4o"),
        AnswerRelevancyMetric(threshold=0.75, model="gpt-4o"),
        ContextualPrecisionMetric(threshold=0.80, model="gpt-4o"),
        ContextualRecallMetric(threshold=0.80, model="gpt-4o"),
    ])
```

```yaml
# .github/workflows/eval-gate.yml
name: RAG Eval Gate

on: [pull_request]

jobs:
  eval:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install dependencies
        run: pip install deepeval ragas pytest

      - name: Run eval gate
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
        run: |
          pytest tests/test_rag_quality.py -v --tb=short
          # CI fails if any metric < threshold
```

</ex-deepeval-ci>

---

<ex-eval-compare>

## Example: Comparing Two Configurations (A/B Eval)

Always change ONE variable at a time. Changing multiple things makes it impossible to attribute the delta.

```python
import json
from ragas import evaluate
from ragas.metrics import faithfulness, context_recall, context_precision, answer_relevancy
from datasets import Dataset

def run_config(config_name: str, pipeline, eval_questions: list) -> dict:
    """Run all eval queries against a pipeline and return metric scores."""
    rows = []
    for item in eval_questions:
        result = pipeline.run(item["question"])
        rows.append({
            "question": item["question"],
            "answer": result["answer"],
            "contexts": result["contexts"],
            "ground_truth": item.get("reference_answer", ""),
        })

    dataset = Dataset.from_dict({k: [r[k] for r in rows] for k in rows[0]})
    scores = evaluate(dataset, metrics=[faithfulness, context_recall, context_precision, answer_relevancy])
    return {"config": config_name, **scores}


# Load golden dataset
with open("evalset.jsonl") as f:
    eval_questions = [json.loads(line) for line in f]

# Compare
baseline = run_config("baseline_bge_m3_k10", baseline_pipeline, eval_questions)
candidate = run_config("new_cohere_embed_v4_k20", new_pipeline, eval_questions)

# Print delta
print(f"\n{'Metric':<25} {'Baseline':>10} {'Candidate':>10} {'Delta':>10}")
print("-" * 55)
for metric in ["faithfulness", "context_recall", "context_precision", "answer_relevancy"]:
    b = baseline[metric]
    c = candidate[metric]
    delta = c - b
    flag = " ✓" if delta > 0.02 else (" ✗" if delta < -0.02 else " ~")
    print(f"{metric:<25} {b:>10.3f} {c:>10.3f} {delta:>+10.3f}{flag}")

# Save baseline for future regression checks
with open("baseline_scores.json", "w") as f:
    json.dump(baseline, f, indent=2)
```

**Reading the output:**
- Delta > +0.02 → meaningful improvement
- Delta between -0.02 and +0.02 → neutral, investigate further  
- Delta < -0.02 → regression, block the change

</ex-eval-compare>

---

<threshold-calibration>

## Threshold Calibration Protocol

Never set thresholds by intuition. Here is the calibration algorithm:

```
Step 1 — Establish baseline
  Run eval on your golden dataset BEFORE making any changes.
  baseline = {
    "faithfulness": 0.87,
    "context_precision": 0.82,
    "context_recall": 0.84,
    "answer_relevancy": 0.79
  }

Step 2 — Set regression threshold (CI gate lower bound)
  regression_threshold = baseline_score − 0.05
  (5% margin tolerates noise without masking real regressions)

  ci_thresholds = {
    "faithfulness": 0.82,          # 0.87 - 0.05
    "context_precision": 0.77,     # 0.82 - 0.05
    "context_recall": 0.79,        # 0.84 - 0.05
    "answer_relevancy": 0.74       # 0.79 - 0.05
  }

Step 3 — Set target (what improvement looks like)
  target = baseline_score + 0.10
  (10% improvement over baseline is meaningful progress)

Step 4 — Tighten thresholds as the system improves
  After baseline improves by 5%+, reduce margin from 5% to 3%.
  Example after 3 months: faithfulness baseline rises to 0.92
  → new CI threshold = 0.92 - 0.03 = 0.89
```

**Absolute minimums** (should never fall below these regardless of baseline):
| Metric | Absolute floor |
|---|---|
| Faithfulness | 0.70 |
| Context Precision | 0.65 |
| Context Recall | 0.65 |
| Answer Relevancy | 0.65 |

If your baseline is below these, **do not deploy**. Fix the pipeline first.

</threshold-calibration>

---

<ex-online-eval>

## Example: Online Evaluation (Production Sampling)

```python
import random
from openai import OpenAI
import json
from datetime import datetime

judge = OpenAI()

def should_evaluate(sampling_rate: float = 0.15) -> bool:
    return random.random() < sampling_rate

def online_eval(question: str, answer: str, contexts: list[str]) -> dict | None:
    """Attach to your production RAG handler. Returns None if not sampled."""
    if not should_evaluate(sampling_rate=0.15):  # evaluate 15% of queries
        return None

    context_text = "\n\n".join(contexts)

    response = judge.chat.completions.create(
        model="gpt-4o-mini",  # cheaper model for high-volume online eval
        messages=[
            {
                "role": "user",
                "content": f"""Score faithfulness 0-1 and answer_relevancy 0-1.

Context: {context_text[:3000]}  

Answer: {answer}

Question: {question}

Return JSON: {{"faithfulness": float, "answer_relevancy": float, "issues": []}}""",
            }
        ],
        response_format={"type": "json_object"},
        temperature=0,
    )

    scores = json.loads(response.choices[0].message.content)
    scores["timestamp"] = datetime.utcnow().isoformat()
    scores["question_hash"] = hash(question)

    # Push to your metrics store (Prometheus, Datadog, InfluxDB, etc.)
    push_metrics(scores)

    # Save low-quality interactions to evalset for improvement
    if scores["faithfulness"] < 0.75 or scores["answer_relevancy"] < 0.65:
        save_to_failure_log(question, answer, contexts, scores)

    return scores
```

```python
# Prometheus metrics example
from prometheus_client import Histogram, Counter

faithfulness_hist = Histogram("rag_faithfulness", "Faithfulness score distribution", buckets=[0.5, 0.6, 0.7, 0.8, 0.85, 0.9, 0.95, 1.0])
eval_counter = Counter("rag_evaluations_total", "Number of evaluated queries")

def push_metrics(scores: dict):
    faithfulness_hist.observe(scores["faithfulness"])
    eval_counter.inc()
```

**Alerting rule:** If rolling 1-hour average faithfulness drops > 5% below your CI gate threshold, page on-call.

</ex-online-eval>

---

<root-cause-diagnosis>

## Root Cause Diagnosis

When eval scores degrade, use this decision tree before changing anything:

```
Overall quality is poor
         │
         ├── Context Recall LOW (< 0.70)
         │        │
         │        └──► RETRIEVAL PROBLEM
         │             Missing relevant documents. Fix:
         │             - Increase k
         │             - Switch to hybrid retrieval
         │             - Re-chunk (smaller chunks)
         │             - Check embedding model matches query type
         │
         ├── Context Recall HIGH, Faithfulness LOW
         │        │
         │        └──► GENERATION PROBLEM
         │             Retrieval found the right docs; LLM is still hallucinating. Fix:
         │             - Tighten system prompt (explicit "only use provided context")
         │             - Reduce LLM temperature
         │             - Add negative instruction: "If unsure, say 'I don't know'"
         │             - Reduce k (too much context confuses the model)
         │
         ├── Context Precision LOW, Context Recall HIGH
         │        │
         │        └──► RANKING PROBLEM
         │             Right docs retrieved but buried under irrelevant ones. Fix:
         │             - Add a reranker
         │             - Add metadata pre-filters
         │             - Tune hybrid alpha toward BM25 (more exact matching)
         │
         └── Answer Relevancy LOW
                  │
                  └──► QUERY / PROMPT PROBLEM
                       Answer drifts off-topic. Fix:
                       - Add query rewriting before retrieval
                       - Tighten answer generation prompt ("answer only what was asked")
                       - Check if query is ambiguous (add clarification step)
```

**Isolate components:** Change retriever only → re-run eval → measure delta. Change LLM only → re-run eval → measure delta. Never change both at the same time.

</root-cause-diagnosis>

---

<boundaries>

## Boundaries

**This skill CAN help you:**
- Choose which metrics to run for your specific debugging goal
- Build a golden evalset from scratch or synthetically
- Write and calibrate LLM-as-judge prompts for faithfulness and relevancy
- Set CI gate thresholds from your baseline using the calibration protocol
- Diagnose whether a quality problem is retrieval or generation
- Run RAGAS or DeepEval evaluations and interpret the output
- Set up online production sampling with alerting

**This skill CANNOT:**
- Replace human review for high-stakes regulated outputs — automate to a threshold, then sample-review
- Tell you the optimal threshold for your domain without your baseline data
- Fix retrieval problems — see `rag-retrieval`
- Fix ingestion problems — see `rag-ingestion`
- Set up full observability spans and traces — see `rag-observe`

</boundaries>

---

<fix-circular-eval>

## Fix: Circular Evaluation

**WRONG** — same model scores its own outputs:
```python
# Using GPT-4o for generation AND as the faithfulness judge
llm = ChatOpenAI(model="gpt-4o")
answer = llm.invoke(prompt)  # GPT-4o generates the answer

judge = ChatOpenAI(model="gpt-4o")  # same model judges it
score = evaluate_faithfulness(answer, context, llm=judge)
# Result: GPT-4o scores itself 25% higher than an independent judge would
```

**CORRECT** — different model for generation and evaluation:
```python
# Generation: GPT-4o
gen_llm = ChatOpenAI(model="gpt-4o")
answer = gen_llm.invoke(prompt)

# Evaluation: Claude (independent judge)
from anthropic import Anthropic
judge_client = Anthropic()
score = evaluate_faithfulness_with_claude(answer, context, judge_client)
```

**Why:** Self-enhancement bias is documented across all major LLMs. GPT-4 gives itself a +10% win rate; Claude-v1 gives itself +25%. Your eval scores will be inflated and won't detect real regressions.

</fix-circular-eval>

---

<fix-missing-baseline>

## Fix: No Baseline Before Making Changes

**WRONG** — changing the pipeline without a recorded baseline:
```python
# System is "working" but no metrics recorded
# Developer upgrades embedding model from text-embedding-3-small to text-embedding-3-large
# Deploys. Answers get worse. No way to know what changed.
```

**CORRECT** — record baseline before every significant change:
```python
# BEFORE making any change:
baseline = evaluate(pipeline_v1, eval_dataset, metrics=all_metrics)
with open("baselines/v1_2024_12_01.json", "w") as f:
    json.dump({"version": "v1", "date": "2024-12-01", "scores": baseline}, f)

# Make the change, re-evaluate:
candidate = evaluate(pipeline_v2, eval_dataset, metrics=all_metrics)

# Compare delta:
for metric, score in candidate.items():
    delta = score - baseline[metric]
    print(f"{metric}: {baseline[metric]:.3f} → {score:.3f} ({delta:+.3f})")
```

**Why:** Without a baseline, you cannot tell if a change improved or degraded the system. Baselines also become your CI gate thresholds — you cannot set them without them.

</fix-missing-baseline>

---

<fix-small-evalset>

## Fix: Evalset Too Small

**WRONG** — evaluating on 5–10 questions:
```python
eval_questions = [
    "What is your return policy?",
    "How do I reset my password?",
    "What are your business hours?",
]
# 3 questions. Changing one retrieval setting could swing scores by 33%.
# Noise masks real regressions.
```

**CORRECT** — minimum 50 questions; 100+ for reliable regression detection:
```python
# Build at least 50 questions that cover:
# - All major topic areas in your corpus
# - Different question types (factual, procedural, comparative, edge case)
# - Multiple difficulty levels
# - Known failure modes from production logs

# Quick synthetic expansion using your chunks:
evalset = []
for chunk in random.sample(all_chunks, 100):  # sample 100 chunks
    pairs = generate_eval_pairs(chunk.page_content, n=1)
    evalset.extend(pairs)

# Now you have ~100 diverse questions
```

**Why:** With 10 questions, a 1-question difference in correct answers is a 10% swing in your metric. You need 50+ samples for scores to be stable enough to detect a 5% regression.

</fix-small-evalset>

---

<fix-retrieval-generation-conflation>

## Fix: Not Separating Retrieval from Generation Failures

**WRONG** — only looking at end-to-end answer quality:
```python
# faithfulness score dropped from 0.85 to 0.70
# "The LLM must be hallucinating more"
# Developer tweaks system prompt for an hour
# Problem: retrieval recall also dropped — the right chunks aren't being fetched
```

**CORRECT** — always measure retrieval and generation separately:
```python
from ragas.metrics import faithfulness, context_recall, context_precision, answer_relevancy

results = evaluate(dataset, metrics=[
    context_recall,     # ← retrieval: did we get the right docs?
    context_precision,  # ← retrieval: are top results relevant?
    faithfulness,       # ← generation: did LLM stay in context?
    answer_relevancy,   # ← generation: did LLM answer the question?
])

# Diagnosis:
if results["context_recall"] < 0.75:
    print("RETRIEVAL PROBLEM — fix retrieval first before touching the LLM")
elif results["faithfulness"] < 0.80:
    print("GENERATION PROBLEM — retrieval is fine, LLM is hallucinating")
```

**Why:** Retrieval failures and generation failures look identical at the output level — a wrong answer. Measuring them separately tells you where to look. Tweaking the LLM prompt when the problem is retrieval wastes time and does not fix anything.

</fix-retrieval-generation-conflation>

---

<fix-no-ci-gate>

## Fix: Deploying Without a Quality Gate

**WRONG** — shipping RAG changes without automated eval:
```python
# "I tested it manually with 5 questions and it looked good"
# New embedding model deployed. Context recall dropped from 0.84 to 0.61 on edge cases.
# Users complain for 3 days before rollback.
```

**CORRECT** — block every deployment behind an eval gate:
```yaml
# .github/workflows/eval-gate.yml
name: RAG Eval Gate
on: [pull_request]
jobs:
  eval:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: pip install deepeval pytest
      - run: pytest tests/test_rag_quality.py -v
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
# PR is blocked if any metric falls below its threshold
```

```python
# tests/test_rag_quality.py
from deepeval.metrics import FaithfulnessMetric, ContextualRecallMetric

THRESHOLDS = {
    "faithfulness": 0.82,       # baseline(0.87) - 0.05
    "context_recall": 0.79,     # baseline(0.84) - 0.05
    "context_precision": 0.77,  # baseline(0.82) - 0.05
    "answer_relevancy": 0.74,   # baseline(0.79) - 0.05
}
```

**Why:** Manual testing cannot cover your full evalset systematically. Regressions are subtle — a change that improves faithfulness can silently drop context recall. Automated gates catch this before users see it.

</fix-no-ci-gate>

---

<fix-wrong-metrics>

## Fix: Using BLEU/ROUGE for RAG Answers

**WRONG** — applying translation metrics to open-ended RAG:
```python
from nltk.translate.bleu_score import sentence_bleu

reference = ["The refund policy allows 30 days from purchase."]
hypothesis = "You have 30 days to return your purchase for a full refund."

score = sentence_bleu(reference, hypothesis.split())
print(score)  # 0.12 — "wrong" despite being a correct paraphrase
```

**CORRECT** — use semantic metrics for open-ended answers:
```python
# Option 1: RAGAS faithfulness + answer_relevancy (best for RAG)
# Option 2: BERTScore for semantic similarity to reference
from bert_score import score as bert_score

P, R, F1 = bert_score(
    cands=["You have 30 days to return your purchase for a full refund."],
    refs=["The refund policy allows 30 days from purchase."],
    lang="en",
)
print(f"BERTScore F1: {F1.mean():.3f}")  # 0.91 — correctly recognizes paraphrase

# Option 3: LLM-as-judge for nuanced evaluation (most flexible)
```

**Why:** BLEU and ROUGE measure n-gram overlap. RAG answers are paraphrases of source text — identical meaning, different words. These metrics penalize correct paraphrasing and reward verbatim copying, which is the opposite of what you want.

</fix-wrong-metrics>

