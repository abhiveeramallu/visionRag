# VisionRAG-X: Evaluation & Benchmark Guide

> **Benchmarks**: Synthetic Benchmark (`dataset.json`) & Real-Video Benchmark (`real_video_dataset.json`)  
> **Evaluation Suite**: `evaluation/run_eval.py` & `evaluation/run_ablations.py`

---

## 1. Benchmark Datasets

VisionRAG-X evaluates multimodal retrieval and verification on two structured benchmarks:

### 1.1. Synthetic Benchmark (`evaluation/benchmark/dataset.json`)
- **Corpus**: 15 multimodal educational units (formulas, code snippets, OCR text, ASR speech, diagram captions).
- **Queries**: 20 total questions:
  - 18 answerable queries across 5 categories (`code`, `conceptual`, `factual`, `formula`, `timestamp`).
  - 2 unanswerable queries (`q17`, `q18`) designed to test out-of-domain abstention and evidence-boundary verification.
- **Planted Conflicts**: 2 verified cross-modal contradictions between speech commentary and on-screen slides (evaluated across 5 conflict-labelled queries).

### 1.2. Real-Video Lecture Benchmark (`evaluation/benchmark/real_video_dataset.json`)
- **Corpus**: 18 multimodal atoms extracted from real computer science lecture recordings (MIT 6.006 / Algorithms).
- **Queries**: 15 total questions:
  - 13 answerable queries across 5 categories (`code`, `conceptual`, `factual`, `formula`, `visual`).
  - 2 unanswerable queries (`rv_q14`, `rv_q15`) designed to test out-of-domain abstention.
- **Real-World Errata & Conflicts**: Includes 3 conflict-labelled queries (`rv_q04`, `rv_q08`, `rv_q10`) evaluating verbal slip corrections and slide errata (e.g., Page 2 formula corrected on Page 6 erratum sheet).

---

## 2. Evaluation Metrics Definition

### 2.1. Retrieval Metrics (Evaluated on Answerable Subset)
- **Recall@5**: Proportion of ground-truth relevant units retrieved in the top 5 candidates.
- **Precision@5**: Proportion of the top 5 retrieved candidates that are relevant.
- **MRR (Mean Reciprocal Rank)**: Reciprocal rank of the first relevant candidate.
- **NDCG@5**: Normalized Discounted Cumulative Gain accounting for candidate rank positions.

### 2.2. Generation & Verification Metrics
- **Token F1**: Harmonic mean of token-level precision and recall between generated answer and ground-truth answer.
- **Exact Match (EM)**: Binary match after string normalization.
- **Citation Gold F1**: F1 score of retrieved/cited knowledge unit IDs against gold citation unit IDs.
- **Citation Support**: Fraction of generated claims supported by at least one valid retrieved evidence snippet.
- **Conflict F1**: Harmonic mean of precision and recall in identifying cross-modal contradictions.
- **Version Accuracy**: Proportion of queries where the system retrieves the active, corrected version instead of the superseded version.
- **Abstention Accuracy**: Accuracy in rejecting unanswerable or ungrounded queries.
- **Decision Accuracy**: Combined metric over all queries (answering answerable queries and abstaining on unanswerable queries).

---

## 3. Evaluated Systems & Empirical Findings

VisionRAG-X is benchmarked against 5 baselines:

| System | Recall@5 | MRR | Cit Gold F1 | Conflict F1 | Version Acc | Decision Acc |
|---|---|---|---|---|---|---|
| **A. Transcript-Only RAG** | 0.278 | 0.250 | 0.148 | 0.000 | 0.000 | 0.900 |
| **B. Speech + OCR Retrieval** | 0.639 | 0.611 | 0.426 | 0.000 | 0.000 | 0.900 |
| **C. Standard Multimodal (No Conflict/VEKG)** | 1.000 | 0.907 | 0.639 | 0.000 | 0.333 | 0.900 |
| **D. Multimodal + Conflict Detection** | 1.000 | 0.907 | 0.639 | 1.000 | 0.333 | 0.900 |
| **E. Conflict + Knowledge Evolution Graph** | 1.000 | 0.907 | 0.639 | 1.000 | 0.333 | 0.900 |
| **F. Full VisionRAG-X System** | **1.000** | **0.944** | **0.704** | **1.000** | **1.000** | **1.000** |

### Key Observations
1. **Transcript-Only RAG (A)** fails on slide-only equations and diagrams (Recall@5 = 0.278).
2. **Standard Multimodal (C)** achieves strong general recall (1.000) but fails to detect when speech contradicts slides (Conflict F1 = 0.000) and serves outdated errors (Version Accuracy = 0.333).
3. **Full VisionRAG-X (F)** achieves top performance across all dimensions: Conflict F1 = 1.000, Version Accuracy = 1.000, and Decision Accuracy = 1.000.

---

## 4. Ablation Study Matrix (7 Conditions)

| Ablation Condition | Recall@5 | MRR | Cit Gold F1 | Conflict F1 | Version Acc | Impact |
|---|---|---|---|---|---|---|
| **Full VisionRAG-X (Reference)** | **1.000** | **0.944** | **0.704** | **1.000** | **1.000** | Reference standard |
| **Ablation A: No ASR** | 0.722 | 0.750 | 0.500 | 1.000 | 0.000 | Spoken explanations lost |
| **Ablation B: No OCR** | 0.639 | 0.611 | 0.454 | 1.000 | 0.333 | Slide definitions lost |
| **Ablation C: No Vision** | 0.917 | 0.852 | 0.565 | 1.000 | 0.333 | Diagram insights lost |
| **Ablation D: No Conflict Detection** | 1.000 | 0.944 | 0.704 | **0.000** | 1.000 | Blind to contradictions |
| **Ablation E: No VKEG** | 1.000 | 0.907 | 0.639 | 1.000 | **0.333** | Outdated errors surfaced |
| **Ablation F: No Hybrid (Dense-only)**| 0.944 | 0.861 | 0.611 | 1.000 | 0.000 | Symbolic fidelity degrades |
| **Ablation G: No Dynamic Routing** | 1.000 | 0.907 | 0.639 | 1.000 | 0.333 | Suboptimal formula retrieval |

---

## 5. Running Evaluations Locally

You can run evaluations directly via the web UI at `/evaluation` or via the command line:

### 5.1. Run Synthetic Comparative Evaluation
```bash
cd visionrag-x
backend/.venv/bin/python evaluation/run_eval.py
```
Outputs saved to:
- `evaluation/results/evaluation_results.json`
- `evaluation/results/benchmark_report.md`

### 5.2. Run Real-Video Comparative Evaluation
```bash
cd visionrag-x
backend/.venv/bin/python evaluation/run_eval.py \
  --dataset evaluation/benchmark/real_video_dataset.json \
  --output-suffix real_video
```
Outputs saved to:
- `evaluation/results/evaluation_results_real_video.json`
- `evaluation/results/benchmark_report_real_video.md`

### 5.3. Run Ablation Study
```bash
cd visionrag-x
backend/.venv/bin/python evaluation/run_ablations.py
```
Outputs saved to:
- `evaluation/results/ablation_results.json`
- `evaluation/results/ablation_report.md`
