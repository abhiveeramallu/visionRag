# VisionRAG-X: Evaluation Protocol & Empirical Benchmark Specification

> **Framework**: VisionRAG-X: A Conflict-Aware Framework for Verified Multimodal Knowledge Retrieval from Educational Videos  
> **Last Verified**: 2026-10-27  

---

## 1. Evaluation Datasets

### 1.1. Benchmark Dataset (`evaluation/benchmark/dataset.json`)
The primary comparative evaluation benchmark comprises 20 gold-annotated questions mapped against 15 versioned educational knowledge units spanning multiple modalities:

- **Total Atoms**: 15 units
  - `ASR` (Spoken commentary): 5 units
  - `OCR` (Slide bullet points & definitions): 5 units
  - `Formula` (Mathematical derivations & complexity bounds): 2 units
  - `Code` (Implementation functions & algorithms): 2 units
  - `Vision` (Diagram and architectural descriptions): 1 unit
- **Contradictions / Conflicts**: 2 cross-modal pairs (speech vs slide $O(n \log n)$ vs $O(n^2)$; parameter setting discrepancy)
- **Lineage Chains**: 2 superseded-to-active correction chains
- **Question Population**: 20 questions
  - Answerable queries: 18 questions across 5 categories (`conceptual`, `formula`, `code`, `factual`, `timestamp`)
  - Unanswerable queries: 2 control questions designed to test system abstention fidelity

### 1.2. Real Video Dataset (`evaluation/benchmark/real_video_dataset.json`)
Derived from real-world educational YouTube videos and MP3 lectures ingested into VisionRAG-X:
- **Sources**:
  - `d79fb75e-eb67-4dae-9ea5-05a2e7a64453`: *Backtracking tutorial* (34 KUs: 24 ASR, 10 OCR)
  - `5fd05f6f-2f73-439b-bfeb-2d28e9e4427d`: *OSI 7 Layers Model* (120 KUs: 85 ASR, 35 OCR)
  - `f7e46f40-f334-4e72-83a3-36e522b7ed20`: *Masters of Enterprise 01* (144 ASR KUs)
  - `6343a096-09b7-460c-86a1-cc05cd6838d1`: *VisionRAG-X Sample Course* (6 PDF KUs with errata)

---

## 2. Evaluation Metrics & Mathematical Formulations

### 2.1. Retrieval Metrics
- **Recall@K**: Proportion of gold evidence units retrieved in top-$K$:
  $$\text{Recall@K} = \frac{|\mathcal{R}_K \cap \mathcal{G}|}{|\mathcal{G}|}$$
- **Precision@K**: Proportion of top-$K$ retrieved units that are gold evidence:
  $$\text{Precision@K} = \frac{|\mathcal{R}_K \cap \mathcal{G}|}{K}$$
- **Mean Reciprocal Rank (MRR)**: Reciprocal rank of the first relevant gold unit:
  $$\text{MRR} = \frac{1}{|Q|} \sum_{i=1}^{|Q|} \frac{1}{\text{rank}_i}$$
- **NDCG@K**: Normalized Discounted Cumulative Gain over graded relevance:
  $$\text{NDCG@K} = \frac{\text{DCG@K}}{\text{IDCG@K}}, \quad \text{DCG@K} = \sum_{i=1}^K \frac{2^{\text{rel}_i} - 1}{\log_2(i + 1)}$$

### 2.2. Answer Grounding & Citation Metrics
- **Citation Gold F1**: Harmonic mean of precision and recall between cited unit IDs and gold evidence IDs.
- **Citation Support Rate**: Fraction of generated claims supported by verified retrieved context ($1.0$ = no ungrounded claims).
- **Token F1**: Bag-of-words token overlap between generated answer and gold reference explanation.

### 2.3. Conflict & Version Integrity Metrics
- **Conflict F1**: Detection performance on true cross-modal contradictions.
- **Version Accuracy**: Proportion of queries referencing corrected concepts where the system surfaces the active correction rather than the superseded claim.
- **Abstention Accuracy**: Accuracy on unanswerable queries (correctly returning abstention without fabricating an answer).
- **False Abstention Rate**: Fraction of answerable queries mistakenly rejected by the sufficiency gate ($0.00$ = optimal).

---

## 3. Comparative Baseline Configurations

1. **Baseline A (Transcript-Only RAG)**: Standard dense retriever over speech transcripts alone. Ignores slides, equations, and code.
2. **Baseline B (Speech + OCR Retrieval)**: Ingests both audio and slide text into a single flat vector index. No conflict or evolution awareness.
3. **Baseline C (Standard Multimodal)**: Multimodal ingestion (ASR, OCR, vision, formula, code) with hybrid retrieval, but without conflict detection or VEKG lineage traversal.
4. **Baseline D (Multimodal + Conflict Detection)**: Standard multimodal retrieval augmented with sliding-window speech-vs-slide conflict detection.
5. **Baseline E (Conflict + Knowledge Evolution Graph)**: Adds the VEKG multigraph to trace concept evolution, but without dynamic routing.
6. **Baseline F (Full VisionRAG-X System)**: Unified pipeline combining dynamic query routing, VEKG lineage resolution, cross-modal conflict verification, and sufficiency-gated abstention.

---

## 4. Benchmark Results Summary

### Comparative Performance Table
| Configuration | Recall@5 | MRR | NDCG@5 | Cit Gold F1 | Conflict F1 | Version Acc | Abstain Acc | E2E Latency |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **A. Transcript-Only RAG** | 0.278 | 0.250 | 0.237 | 0.148 | 0.000 | 0.000 | 0.000 | 0.1 ms |
| **B. Speech + OCR Retrieval** | 0.639 | 0.611 | 0.600 | 0.426 | 0.000 | 0.000 | 0.000 | 0.1 ms |
| **C. Standard Multimodal** | 1.000 | 0.917 | 0.934 | 0.676 | 0.000 | 0.333 | 0.000 | 11.9 ms |
| **D. Multimodal + Conflict** | 1.000 | 0.917 | 0.934 | 0.676 | 1.000 | 0.333 | 0.000 | 1.3 ms |
| **E. Conflict + VEKG** | 1.000 | 0.917 | 0.934 | 0.676 | 1.000 | 0.333 | 0.000 | 0.8 ms |
| **F. Full VisionRAG-X System** | **1.000** | **0.944** | **0.959** | **0.704** | **1.000** | **1.000** | **1.000** | **0.7 ms** |

---

## 5. Ablation Studies Summary

| Ablation Condition | Recall@5 | NDCG@5 | Cit Gold F1 | Conflict F1 | Version Acc | Primary Failure Mode |
| :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| **Full VisionRAG-X (Ref)** | **1.000** | **0.959** | **0.704** | **1.000** | **1.000** | Optimal performance across all dimensions. |
| **A: No ASR** | 0.722 | 0.714 | 0.500 | 1.000 | 0.000 | Loses spoken corrections and verbal explanations. |
| **B: No OCR** | 0.639 | 0.612 | 0.454 | 1.000 | 0.333 | Fails on slide formulas, code snippets, and diagrams. |
| **C: No Vision** | 0.917 | 0.857 | 0.602 | 1.000 | 0.333 | Degrades on diagrammatic trajectories and charts. |
| **D: No Conflict Detection** | 1.000 | 0.959 | 0.704 | 0.000 | 1.000 | Silently presents contradicting claims as equally valid. |
| **E: No VEKG Graph** | 1.000 | 0.934 | 0.676 | 1.000 | 0.333 | Outdated/superseded claims pollute answer context. |
| **F: No Hybrid Indexing (Dense-only)** | 0.944 | 0.874 | 0.611 | 1.000 | 0.000 | Fails on exact algorithmic variables and math symbols. |
| **G: No Dynamic Routing (Uniform)** | 1.000 | 0.934 | 0.676 | 1.000 | 0.333 | Sub-optimal precision on domain-specific formula queries. |

---

## 6. How to Reproduce Benchmark Results

To re-run the complete evaluation pipeline and re-generate `evaluation/results/evaluation_results.json` and `evaluation/results/benchmark_report.md`:

```bash
cd visionrag-x
backend/.venv/bin/python3 evaluation/run_eval.py
```

To re-run the 7-condition ablation study and update `evaluation/results/ablation_report.md`:

```bash
cd visionrag-x
backend/.venv/bin/python3 evaluation/run_ablations.py
```
