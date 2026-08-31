# VisionRAG-X Evaluation Framework

> ⚠️ **Status: Experimental** — All metric implementations are provided as tools for research and community review. No results against a standard benchmark have been validated at this time.

This directory contains the evaluation infrastructure for VisionRAG-X. It is structured to support:

1. **Retrieval quality measurement** — How well does the system surface relevant chunks?
2. **Answer quality measurement** — How accurate, faithful, and well-cited are the generated answers?
3. **Baseline comparisons** — Structured configs for four reference systems.
4. **Ablation studies** — Seven component-level experiments (A–G).

---

## Directory Structure

```
evaluation/
├── README.md                    # This file
├── metrics/
│   ├── retrieval_metrics.py     # Recall@K, Precision@K, MRR, NDCG@K, MAP
│   └── answer_metrics.py        # Exact match, Token F1, Citation accuracy, Hallucination heuristic
├── baselines/
│   └── baseline_configs.yaml   # 4 baseline system configurations
├── experiments/
│   └── ablation_config.yaml    # 7 ablation study configurations (A–G)
└── results/
    └── .gitkeep                # Results directory (gitignored, not committed)
```

---

## Quick Start

```bash
# Install evaluation dependencies (from project root)
cd backend
source .venv/bin/activate
pip install numpy scikit-learn nltk rouge-score

# Run retrieval metrics on a sample result file
python -c "
from evaluation.metrics.retrieval_metrics import batch_recall_at_k, batch_ndcg_at_k

# Example: list of (retrieved_ids, relevant_ids) per query
queries = [
    (['c1', 'c2', 'c3', 'c4', 'c5'], ['c1', 'c3']),
    (['c2', 'c5', 'c1', 'c4', 'c3'], ['c2', 'c4']),
]
retrieved = [q[0] for q in queries]
relevant  = [q[1] for q in queries]

print('Recall@5:', batch_recall_at_k(retrieved, relevant, k=5))
print('NDCG@5:  ', batch_ndcg_at_k(retrieved, relevant, k=5))
"
```

---

## Retrieval Metrics (`metrics/retrieval_metrics.py`)

| Function | Signature | Description |
|---|---|---|
| `recall_at_k` | `(retrieved_ids, relevant_ids, k) → float` | Fraction of relevant docs in top-K retrieved |
| `precision_at_k` | `(retrieved_ids, relevant_ids, k) → float` | Fraction of top-K that are relevant |
| `mrr` | `(retrieved_ids, relevant_ids) → float` | Reciprocal rank of first relevant result |
| `ndcg_at_k` | `(retrieved_ids, relevant_ids, k) → float` | Normalised Discounted Cumulative Gain |
| `average_precision` | `(retrieved_ids, relevant_ids) → float` | Area under the precision-recall curve |
| `batch_recall_at_k` | `(list_retrieved, list_relevant, k) → float` | Mean Recall@K across a query set |
| `batch_precision_at_k` | `(list_retrieved, list_relevant, k) → float` | Mean Precision@K across a query set |
| `batch_mrr` | `(list_retrieved, list_relevant) → float` | Mean MRR across a query set |
| `batch_ndcg_at_k` | `(list_retrieved, list_relevant, k) → float` | Mean NDCG@K across a query set |

---

## Answer Quality Metrics (`metrics/answer_metrics.py`)

| Function | Signature | Description | Status |
|---|---|---|---|
| `exact_match` | `(prediction, ground_truth) → float` | Binary match after normalisation | NOT YET VALIDATED |
| `token_f1` | `(prediction, ground_truth) → float` | Token-overlap F1 | NOT YET VALIDATED |
| `citation_accuracy` | `(answer_citations, retrieved_evidence) → float` | Citation source match rate | NOT YET VALIDATED |
| `hallucination_rate_heuristic` | `(answer, retrieved_context) → float` | N-gram coverage heuristic | NOT YET VALIDATED |

---

## Baselines (`baselines/baseline_configs.yaml`)

Four baselines are defined, from the simplest (ASR-only) to the full system:

1. **asr_only** — Text-only RAG on Whisper transcripts
2. **asr_ocr** — Adds OCR text; still no vision captioning or graph
3. **standard_multimodal** — Full multimodal indexing without VKEG, conflict detection, or dynamic routing
4. **visionrag_x** — Full system (all components enabled)

---

## Ablation Studies (`experiments/ablation_config.yaml`)

| Study | Component Disabled | Hypothesised Effect |
|---|---|---|
| A | ASR | Severe degradation on audio-centric queries |
| B | OCR | Degradation on document-heavy content |
| C | Vision | Minimal on text queries; large on diagram queries |
| D | Conflict Detection | Less trustworthy answers when sources conflict |
| E | VKEG | Degradation on multi-hop entity queries |
| F | Hybrid Indexing | Recall drop on keyword-heavy queries |
| G | Dynamic Routing | Increased latency and retrieval noise |

---

## Contribution Guidelines

- All metrics must include a clear **NOT YET VALIDATED** note until results are published.
- Results files in `evaluation/results/` are gitignored — do not commit raw results.
- When reporting numbers, always include the full baseline config name and ablation ID.
- Keep metric implementations dependency-light (numpy, standard library) where possible.
