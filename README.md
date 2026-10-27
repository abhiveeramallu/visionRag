# VisionRAG-X: A Conflict-Aware Framework for Verified Multimodal Knowledge Retrieval from Educational Videos

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![FastAPI 0.111](https://img.shields.io/badge/FastAPI-0.111-009688.svg)](https://fastapi.tiangolo.com/)
[![React 18](https://img.shields.io/badge/React-18.3-61DAFB.svg)](https://react.dev/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Tests Passing](https://img.shields.io/badge/backend%20tests-184%20passed-brightgreen.svg)](#15-testing-and-development)
[![Frontend Tests](https://img.shields.io/badge/frontend%20tests-16%20passed-brightgreen.svg)](#15-testing-and-development)
[![Evaluation](https://img.shields.io/badge/eval-reproducible-success.svg)](#11-experimental-results--empirical-benchmarks)

> **VisionRAG-X** is an end-to-end, conflict-aware multimodal Retrieval-Augmented Generation (RAG) framework designed for educational video lectures. It extracts, time-aligns, and verifies spoken narration (ASR), slide text (OCR), mathematical formulas, and code snippets into an authoritative, version-tracked knowledge base—explicitly resolving pedagogical contradictions, errata corrections, and ungrounded hallucinations.

---

## 📚 Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Research Motivation & Core Failure Modes](#2-research-motivation--core-failure-modes)
3. [The Five Research Objectives & Contributions](#3-the-five-research-objectives--contributions)
4. [System Architecture](#4-system-architecture)
5. [End-to-End Workflow](#5-end-to-end-workflow)
6. [Repository Structure & File Inventory](#6-repository-structure--file-inventory)
7. [Core Technical Implementation](#7-core-technical-implementation)
8. [What Differentiates VisionRAG-X](#8-what-differentiates-visionrag-x)
9. [Research Implementation Status Matrix](#9-research-implementation-status-matrix)
10. [Multi-Strategy Dynamic Routing Specification](#10-multi-strategy-dynamic-routing-specification)
11. [Experimental Results & Empirical Benchmarks](#11-experimental-results--empirical-benchmarks)
12. [Evaluation Methodology & Formulations](#12-evaluation-methodology--formulations)
13. [Installation & Setup Guide](#13-installation--setup-guide)
14. [Usage & Research Demonstration Sequence](#14-usage--research-demonstration-sequence)
15. [Testing & Development](#15-testing--development)
16. [Limitations & Threats to Validity](#16-limitations--threats-to-validity)
17. [Security & Privacy Guarantees](#17-security--privacy-guarantees)
18. [Future Work](#18-future-work)
19. [References](#19-references)
20. [License & Citation](#20-license--citation)
21. [Supporting Documentation Links](#21-supporting-documentation-links)

---

## 1. Executive Summary

Standard Retrieval-Augmented Generation (RAG) pipelines applied to educational videos typically suffer from four catastrophic failures:
1. **Modality Blindness**: Treating multi-stream video as flat transcript text, completely discarding visual equations, slide code, and diagrams.
2. **Pedagogical Contradictions**: Failing to detect disagreements between spoken commentary and slide visuals (e.g. an instructor verbally stating an algorithm complexity as $O(n^2)$ while the slide correctly displays $O(n \log n)$).
3. **Temporal Errata & Supersession**: Inability to recognize that a later slide or verbal erratum supersedes an earlier verbal slip, causing obsolete statements to be presented as authoritative answers.
4. **Ungrounded Hallucinations**: Fabricating answers to unanswerable questions due to the lack of a calibrated evidence sufficiency gate.

**VisionRAG-X** resolves these fundamental problems through five core architectural innovations:
- **Independent Multimodal Knowledge Representation**: Preserves independent provenance for speech (ASR), slide text (OCR), formulas, code, and visual scenes without destructive text flattening.
- **Cross-Modal Conflict Detector**: Identifies speech-vs-slide contradictions using symbolic AST parsing and sliding temporal windows, marking unresolvable disagreements as explicit unresolved conflicts.
- **Versioned Educational Knowledge Evolution Graph (VEKG)**: A directed multigraph that models concept evolution, supersession, and errata correction chains, automatically resolving superseded claims during retrieval.
- **Multi-Strategy Dynamic Retrieval**: Heuristically classifies queries into specialized retrieval strategies (Semantic vector search, BM25 exact keyword match, VEKG graph walk, Timestamp-aware temporal search, or Hybrid fusion) while honoring explicit user UI overrides.
- **Calibrated Anti-Hallucination Gate & Provenance Citations**: Validates evidence sufficiency via token-stemmed overlap and timestamp bounds, generating answers with seekable media citations and cleanly abstaining on unanswerable queries.

---

## 2. Research Motivation & Core Failure Modes

```
+---------------------------------------------------------------------------------------------------+
|                                  CLASSICAL RAG FAILURE MODES                                      |
+---------------------------------------------------------------------------------------------------+
|  [Spoken Audio: "O(n^2)"]  <--- Contradiction --->  [Slide Text: "O(n log n)"]                     |
|            |                                                    |                                 |
|            +--------------------> Naive RAG <-------------------+                                 |
|                                       |                                                           |
|                 Hallucinates compromise or repeats error                                          |
|                                                                                                   |
|  [Slide 2: Mistake]        <--- Corrected at --->   [Slide 6: Erratum / Fix]                       |
|            |                                                    |                                 |
|            +--------------------> Naive RAG <-------------------+                                 |
|                                       |                                                           |
|             Surfaces outdated superseded unit due to semantic similarity                          |
+---------------------------------------------------------------------------------------------------+
```

In educational environments, knowledge evolves dynamically within a single lecture. Instructors misspeak, write whiteboard corrections, and present errata slides. Classical text-chunk RAG treats all chunks as static, independent facts. VisionRAG-X introduces explicit temporal version tracking, cross-modal conflict detection, and evidence sufficiency checking to ensure student answers are grounded in verified, active course knowledge.

---

## 3. The Five Research Objectives & Contributions

| # | Research Objective | Contribution & Implementation | Code Location | Verification Evidence |
|---|---|---|---|---|
| **1** | **Incomplete Multimodal Representation** | Enforces separate, non-destructive extraction streams for speech (ASR via Whisper), slide text (adaptive OCR via Tesseract), mathematical equations, and code blocks, persisting them into unified `KnowledgeUnit` records. | [`backend/app/ingestion/orchestrator.py`](backend/app/ingestion/orchestrator.py)<br>[`backend/app/knowledge/models.py`](backend/app/knowledge/models.py) | 144 ASR units from MP3 lectures; 34 ASR+OCR units from Backtracking video; tested in [`test_video_multimodal_ingestion.py`](backend/tests/test_video_multimodal_ingestion.py). |
| **2** | **Cross-Modal Conflict Handling** | Sliding temporal window contradiction engine detecting speech-vs-slide factual discrepancies and mathematical formula complexity disagreements via AST comparison. Preserves unresolved candidate conflicts on failure. | [`backend/app/verification/conflict_detector.py`](backend/app/verification/conflict_detector.py) | Conflict F1 = 1.000 on benchmark; detected $O(n^2)$ vs $O(n \log n)$ mismatch in real course PDF; unit tests in [`test_conflict_detector.py`](backend/tests/test_conflict_detector.py). |
| **3** | **Knowledge Evolution (VEKG)** | Directed multigraph modeling concept lineage via `supports`, `conflicts_with`, `corrects`, `supersedes`, and `related_to`. Substitutes superseded claims with active corrections during retrieval. Reconstructed from PostgreSQL on restart. | [`backend/app/knowledge/vekg.py`](backend/app/knowledge/vekg.py) | Version accuracy improved from 0.333 to 1.000; real-source correction retrieval on Page 6 errata; unit tests in [`test_vekg.py`](backend/tests/test_vekg.py). |
| **4** | **Dynamic Query Routing** | Adaptive heuristic router matching queries to specialized strategies (`semantic_only`, `lexical_only`, `knowledge_graph`, `timestamp_aware`, `hybrid`) with user overrides and fault-tolerant BM25 fallback. | [`backend/app/routing/dynamic_router.py`](backend/app/routing/dynamic_router.py)<br>[`backend/app/indexing/hybrid_index.py`](backend/app/indexing/hybrid_index.py) | 10/10 tests passing in [`test_multi_strategy_search.py`](backend/tests/test_multi_strategy_search.py); live verification across 6 query scenarios. |
| **5** | **Evidence Traceability & Abstention** | End-to-end citation provenance linking claims to exact timestamp ranges, pages, and slides. Anti-hallucination sufficiency gate with token-stemmed grounding and calibrated abstention ($0.0$ confidence on ungrounded queries). | [`backend/app/retrieval/retrieval_pipeline.py`](backend/app/retrieval/retrieval_pipeline.py)<br>[`backend/app/generation/answer.py`](backend/app/generation/answer.py) | 100% abstention on unanswerable queries (0% false hallucinations); exact seekable citations displayed in UI; unit tests in [`test_query_integration.py`](backend/tests/test_query_integration.py). |

---

## 4. System Architecture

```mermaid
flowchart TD
    subgraph Ingestion ["1. Multimodal Ingestion & Extraction"]
        RawVideo["Video / PDF / PPT / YouTube"]
        RawVideo --> AudioStream["Audio Track"]
        RawVideo --> VisualStream["Slide / Frame Stream"]
        AudioStream --> WhisperASR["Whisper ASR (Speech)"]
        VisualStream --> Preprocess["Adaptive Preprocessing (Otsu / Contrast)"]
        Preprocess --> TesseractOCR["Tesseract OCR (Text & Formulas)"]
        VisualStream --> VisionCap["Vision LLM (Diagram Captions)"]
    end

    subgraph Storage ["2. Representation & Persistence"]
        WhisperASR --> Extractor["Atom Extractor"]
        TesseractOCR --> Extractor
        VisionCap --> Extractor
        Extractor --> Postgres[("PostgreSQL\nKnowledgeUnits, Conflicts,\nChat Conversations, Lineage")]
        Extractor --> Qdrant[("Qdrant Vector DB\nDense Embeddings (384-d)")]
        Extractor --> BM25["Lexical Index (BM25)\nExact Phrase & Formula Boost"]
    end

    subgraph Routing ["3. Multi-Strategy Dynamic Routing"]
        UserQuery["User Query"] --> StrategySelector{"Strategy Selector\n(Auto / User Override)"}
        StrategySelector -->|Semantic| Qdrant
        StrategySelector -->|Keyword| BM25
        StrategySelector -->|Graph| VEKGTraverse["VEKG Graph Traversal"]
        StrategySelector -->|Timestamp| TemporalExtractor["Temporal Proximity Scorer"]
        StrategySelector -->|Hybrid| Fusion["Hybrid Fusion (Dense + BM25 + Prior)"]
    end

    subgraph Verification ["4. VEKG Lineage & Conflict Verification"]
        Fusion --> Candidates["Top-K Candidate Units"]
        VEKGTraverse --> Candidates
        TemporalExtractor --> Candidates
        Candidates --> LineageCheck{"VEKG Lineage Resolver\n(Check Supersession)"}
        Postgres -.-> LineageCheck
        LineageCheck -->|Substitute Superseded Units| ActiveUnits["Active / Corrected Units"]
        ActiveUnits --> ConflictEngine{"Conflict Detector\n(Speech vs Slide Mismatches)"}
        Postgres -.-> ConflictEngine
        ConflictEngine --> VerifiedContext["Verified Context + Conflict Warnings"]
    end

    subgraph Generation ["5. Sufficiency Gate & Grounded Generation"]
        VerifiedContext --> SufficiencyGate{"Sufficiency Gate\n(Stemmed Term Overlap)"}
        SufficiencyGate -->|Insufficient Evidence| Abstain["Safe Abstention\n(Clear Unanswerable Notice)"]
        SufficiencyGate -->|Grounded Evidence| LLM["Ollama / Local LLM\n(Strict Context Grounding)"]
        LLM --> VerifiedAnswer["Grounded Answer + Seekable Citations\n([1] [ASR] 01:30–01:45)"]
    end
```

---

## 5. End-to-End Workflow

1. **Upload & Media Validation**: The user uploads a media file (MP4, MP3, PDF, PPTX) or submits a YouTube URL. The ingestion orchestrator initializes a tracked `ProcessingJob`.
2. **Parallel Audio & Visual Ingestion**:
   - Audio is converted to 16 kHz mono WAV via FFmpeg and transcribed by Whisper, yielding word-level timestamped segments.
   - Video frames are sampled via scene-change detection. Images are preprocessed and parsed via Tesseract OCR to extract slide text, formulas, and code.
3. **Knowledge Atomization & Alignment**: The temporal aligner groups co-occurring speech and slide events. Each discrete claim is saved as a `KnowledgeUnit` in PostgreSQL, containing source coordinates (`timestamp_start`, `timestamp_end`, `page`, `slide`), modality (`asr`, `ocr`, `formula`, `code`, `vision`), and extraction confidence.
4. **Index Construction**:
   - Dense vector embeddings (384 dimensions) are generated and stored in Qdrant.
   - A BM25 lexical index is constructed in-memory, preserving single-letter math variables (`n`, `x`, `y`, `k`) and formula notation (`O(n log n)`).
5. **Conflict & Evolution Analysis**:
   - Co-occurring speech and slide segments are inspected for numerical and algorithmic discrepancies.
   - The VEKG directed graph is constructed, linking concepts via `supports`, `conflicts_with`, and `corrects`.
6. **Query Routing & Retrieval**:
   - The user selects a single source or `🌐 All Sources (Global Knowledge Base)`.
   - The dynamic router determines the optimal strategy (or respects explicit user selection: `semantic`, `keyword`, `graph`, `timestamp`, `hybrid`).
   - The retriever executes search, boosts exact phrases (+3.0), applies temporal proximity decay for timestamp queries, and injects VEKG multi-hop concept matches.
7. **Lineage Substitution**: The reranker inspects retrieved units. If an earlier unit is superseded by a subsequent erratum, it follows the `EDGE_SUPERSEDES` chain and substitutes the outdated unit with the active correction.
8. **Sufficiency Gating & LLM Answer Generation**:
   - The sufficiency gate validates that query-distinctive subject terms appear in retrieved units.
   - If evidence is sufficient, the context is formatted with bracketed citation IDs (`[1]`, `[2]`) and dispatched to Ollama (`llama3.2:3b`).
   - If evidence is missing, the system deterministically abstains without invoking the LLM, returning confidence `0.0`.
9. **UI Presentation & Provenance Seeking**:
   - The answer is rendered in the Chat UI alongside the **Why this answer?** strategy panel and conflict comparison cards.
   - Clicking any timestamp citation seeks the video/audio player to the exact second.

---

## 6. Repository Structure & File Inventory

A comprehensive catalog of every research-critical module is maintained in **[`docs/FILE_REFERENCE.md`](docs/FILE_REFERENCE.md)**. Below is an overview of the repository hierarchy:

```
visionrag-x/
├── backend/
│   ├── app/
│   │   ├── api/                 # FastAPI HTTP route handlers
│   │   │   ├── query.py         # AI Chat endpoint, multi-source scope, conversation sessions
│   │   │   ├── upload.py        # File & YouTube ingestion workers
│   │   │   ├── sources.py       # Source metadata, deletion, HTTP 206 range media streaming
│   │   │   └── processing.py    # Background task status & heartbeat monitoring
│   │   ├── database/            # Database connectors (PostgreSQL async session, Qdrant client)
│   │   ├── generation/          # LLM abstraction (Ollama, OpenAI) and grounded answer generation
│   │   ├── indexing/            # Dense vector index, BM25 lexical index, and Hybrid score fusion
│   │   ├── ingestion/           # Whisper ASR, Tesseract OCR, frame extraction, timestamp aligner
│   │   ├── knowledge/           # SQLAlchemy ORM models, ProcessedKnowledgeUnit, VEKG multigraph
│   │   ├── retrieval/           # Retrieval pipeline, reranker, temporal target extraction, sufficiency gate
│   │   ├── routing/             # Dynamic query classifier & strategy override mapper
│   │   ├── schemas/             # Pydantic request and response models
│   │   └── verification/        # Cross-modal conflict detector, confidence scorer, provenance tracker
│   └── tests/                   # 186 unit, integration, and algorithmic correctness tests
├── frontend/
│   ├── src/
│   │   ├── components/          # EvidenceCard, RetrievalStrategyPanel, ConflictCompare, MessageBubble
│   │   ├── pages/               # Sources, KnowledgeUnits, KnowledgeGraph, Chat, Evaluation, SourceDetail
│   │   └── services/            # Axios API client (querySource, getKnowledgeUnits, getSources)
│   └── tests/                   # 16 frontend component and lifecycle tests
├── evaluation/
│   ├── benchmark/               # Gold evaluation datasets (dataset.json, real_video_dataset.json)
│   ├── metrics/                 # Retrieval (Recall@K, MRR, nDCG) and answer grounding metrics
│   ├── results/                 # Machine-readable evaluation outputs & Markdown reports
│   ├── run_eval.py              # 6-baseline comparative evaluation runner
│   └── run_ablations.py         # 7-condition ablation experiment runner
└── docs/                        # Formal research documentation and reports
    ├── ARCHITECTURE.md          # Detailed technical architecture & specifications
    ├── IMPLEMENTATION_STATUS.md # 5-objective implementation status & acceptance gate results
    ├── EVALUATION_PROTOCOL.md   # Mathematical metric formulas, baseline definitions, & instructions
    ├── TEST_REPORT.md           # Full test execution record with exact outputs and commands
    ├── FINAL_DEMO_GUIDE.md      # Step-by-step viva & live demonstration guide
    └── FILE_REFERENCE.md        # Comprehensive file-by-file research inventory
```

---

## 7. Core Technical Implementation

### 7.1. Multimodal Knowledge Units (KUs)
Extracted multimodal atoms are normalized into immutable, version-tracked records.
```python
@dataclass
class ProcessedKnowledgeUnit:
    id: str
    concept: str
    content: str
    modality: str                      # 'asr' | 'ocr' | 'formula' | 'code' | 'vision'
    source_id: str
    timestamp_start: Optional[float]   # Video/audio second offset
    timestamp_end: Optional[float]
    page: Optional[int]                # Document page index
    slide: Optional[int]               # Presentation slide number
    confidence: float                  # Calibration prior [0.0, 1.0]
    status: str                        # 'active' | 'superseded' | 'disputed' | 'verified'
    version: int = 1
    previous_version_id: Optional[str] = None
    correction_reason: Optional[str] = None
```

### 7.2. Cross-Modal Conflict Detector
Contradictions are discovered by aligning temporal windows across modalities. Formulas are parsed into SymPy AST representations to distinguish commutative variants (e.g. $a + b$ vs $b + a$) from genuine mathematical conflicts (e.g. $O(n^2)$ vs $O(n \log n)$). If verification cannot resolve a conflict with high certainty, it is retained with status `is_genuine_conflict = None` (unresolved) rather than falsely discarded.

### 7.3. Versioned Educational Knowledge Evolution Graph (VEKG)
The VEKG multigraph tracks concept lineage and temporal updates:
- **Supersession Walk**: When an older unit $u_{\text{old}}$ is retrieved, the traverser checks `previous_version_id` links. If an active correction $u_{\text{new}}$ exists with `status == 'active'`, the pipeline automatically substitutes $u_{\text{new}}$ into the answer context.
- **Concept Discovery**: `traverse_related_concepts()` performs multi-hop traversals over `EDGE_CORRECTS`, `EDGE_SUPERSEDES`, and `EDGE_CONFLICTS_WITH`, retrieving related concepts for conceptual queries.

### 7.4. Hybrid Scoring & Fault-Tolerant Retrieval
The hybrid index fuses dense semantic similarity, BM25 lexical relevance, and extraction confidence:
$$\text{Score}(q, u) = \alpha \cdot \text{Dense}(q, u) + \beta \cdot \text{Lexical}(q, u) + \gamma \cdot \text{Prior}(u)$$
If the Qdrant vector database is unreachable or file-locked by another process, the retriever catches the exception and falls back to BM25 search without failing the request.

---

## 8. What Differentiates VisionRAG-X

| Dimension | Standard Text RAG | Multimodal RAG (e.g. ColPali) | Graph RAG (e.g. LightRAG) | **VisionRAG-X** |
| :--- | :---: | :---: | :---: | :---: |
| **Modality Preservation** | ❌ Text flattened | ⚠️ Visual tokens only | ❌ Entities extracted from text | ✅ **Separate ASR, OCR, Formula, Code KUs** |
| **Speech-Slide Conflicts** | ❌ Unhandled | ❌ Unhandled | ❌ Unhandled | ✅ **Sliding-window conflict detector** |
| **Errata / Supersession** | ❌ Naive similarity | ❌ Naive similarity | ⚠️ Temporal edges | ✅ **VEKG lineage substitution** |
| **Anti-Hallucination Gate** | ❌ Uncalibrated | ❌ None | ❌ None | ✅ **Token-stemmed sufficiency gate** |
| **Citation Granularity** | Document chunk | Bounding box | Entity mention | ✅ **Second-level seeking & page anchors** |
| **Global + Single Scope** | Single index | Single index | Global index | ✅ **Strict single-source isolation + Global Base** |

---

## 9. Research Implementation Status Matrix

| Research Area | Target Functionality | Code Implementation | Status |
| :--- | :--- | :--- | :---: |
| **Multimodal Ingestion** | Whisper ASR, Tesseract OCR, keyframe sampling, format guards | `backend/app/ingestion/` | **Implemented & Verified** |
| **Formula Preservation** | LaTeX & Big-O single-letter variable preservation in BM25 | `backend/app/indexing/lexical_index.py` | **Implemented & Verified** |
| **Conflict Detection** | Speech vs slide contradiction detection & SymPy AST checks | `backend/app/verification/conflict_detector.py` | **Implemented & Verified** |
| **VEKG Graph Traversal** | Lineage walk forward, active correction substitution | `backend/app/knowledge/vekg.py` | **Implemented & Verified** |
| **Dynamic Query Routing** | Adaptive heuristic classifier + manual user overrides | `backend/app/routing/dynamic_router.py` | **Implemented & Verified** |
| **Timestamp Proximity** | Time target extraction (`MM:SS`) with proximity decay | `backend/app/retrieval/retrieval_pipeline.py` | **Implemented & Verified** |
| **Sufficiency Gate** | Plural-stemmed term overlap & temporal grounding | `backend/app/retrieval/retrieval_pipeline.py` | **Implemented & Verified** |
| **Source Isolation** | Zero cross-source data leakage in single-source mode | `backend/app/api/query.py` | **Implemented & Verified** |
| **Global Knowledge Base** | Cross-source querying with `source_id='all'` | `backend/app/api/query.py` | **Implemented & Verified** |
| **Media Player Seeking** | HTTP 206 range streaming + timestamp seek synchronization | `backend/app/api/sources.py` | **Implemented & Verified** |

---

## 10. Multi-Strategy Dynamic Routing Specification

VisionRAG-X supports five retrieval strategies that can be selected automatically via dynamic query classification or manually in the UI:

```
                                  [ User Question ]
                                          |
                      +-------------------+-------------------+
                      |                                       |
             [ Auto Routing Mode ]                   [ User Explicit Override ]
                      |                                       |
           Classify Query Linguistic Cues         Honor Selected Strategy in UI:
                      |                               • Semantic (Vector)
       +--------------+--------------+                • Keyword (BM25)
       |              |              |                • Knowledge Graph (VEKG)
   (Formula)     (Timestamp)    (Conceptual)          • Timestamp / Temporal
       |              |              |                • Hybrid Fusion
 [Lexical BM25]  [Temporal Dec] [VEKG Graph]                  |
       \              |              /                        |
        +-------------+-------------+                         |
                      |                                       |
                      +-------------------+-------------------+
                                          |
                               [ Execute Retrieval ]
                                          |
                               [ Fallback Protection ]
                           (Qdrant Lock -> BM25 Fallback)
```

1. **Semantic Search (`semantic_only`)**: Queries Qdrant dense vector index (384-d). Best for abstract conceptual descriptions.
2. **Keyword Search (`lexical_only`)**: BM25 over persisted KUs. Boosts exact phrases (+3.0) and preserves formula variables (`O(n log n)`).
3. **Knowledge Graph (`knowledge_graph`)**: VEKG multigraph traversal discovering connected concepts via `supports`, `conflicts_with`, and `corrects`.
4. **Timestamp Search (`timestamp_aware`)**: Parses timestamps (`MM:SS`, `HH:MM:SS`, minute offsets) and applies temporal proximity scoring:
   $$\text{Boost}(\Delta t) = \frac{0.45}{1 + \frac{\Delta t}{25.0}}$$
5. **Hybrid Search (`hybrid`)**: Score-weighted fusion combining dense vectors, BM25 tokens, and extraction confidence priors.

---

## 11. Experimental Results & Empirical Benchmarks

### Table A: Benchmark Dataset Overview
| Dataset Identifier | Domain & Media Types | Sources | Knowledge Units | Queries Evaluated | Answerable | Unanswerable |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| **Controlled Benchmark** (`dataset.json`) | Synthetic Computer Science Lecture (Speech, Slides, Formulas, Code) | 1 source | 15 atoms | 20 questions | 18 | 2 |
| **Real Video Benchmark** (`real_video_dataset.json`) | Authentic YouTube Video & MP3 Lectures (Backtracking, OSI Model, Digital Forensics) | 4 sources | 18 atoms | 15 questions | 13 | 2 |

---

### Table B: Comparative Baseline Evaluation
*Evaluated on `dataset.json` using [`evaluation/run_eval.py`](evaluation/run_eval.py). Results saved in [`evaluation/results/evaluation_results.json`](evaluation/results/evaluation_results.json).*

| Configuration | Recall@5 | Prec@5 | MRR | NDCG@5 | Token F1 | Cit Gold F1 | Conflict F1 | Version Acc | Abstain Acc | Ret Lat | E2E Lat |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **A. Transcript-Only RAG** | 0.278 | 0.067 | 0.250 | 0.237 | 0.122 | 0.148 | 0.000 | 0.000 | 0.000 | 0.0 ms | 0.1 ms |
| **B. Speech + OCR Retrieval** | 0.639 | 0.144 | 0.611 | 0.600 | 0.197 | 0.426 | 0.000 | 0.000 | 0.000 | 0.1 ms | 0.1 ms |
| **C. Standard Multimodal** | 1.000 | 0.233 | 0.917 | 0.934 | 0.263 | 0.676 | 0.000 | 0.333 | 0.000 | 9.5 ms | 11.9 ms |
| **D. Multimodal + Conflict** | 1.000 | 0.233 | 0.917 | 0.934 | 0.255 | 0.676 | 1.000 | 0.333 | 0.000 | 1.1 ms | 1.3 ms |
| **E. Conflict + VEKG** | 1.000 | 0.233 | 0.917 | 0.934 | 0.263 | 0.676 | 1.000 | 0.333 | 0.000 | 0.6 ms | 0.8 ms |
| **F. Full VisionRAG-X System** | **1.000** | **0.233** | **0.944** | **0.959** | **0.281** | **0.704** | **1.000** | **1.000** | **1.000** | **0.6 ms** | **0.7 ms** |

*Note on Latency Boundaries: The in-memory benchmark harness measures deterministic BoW/BM25 scoring across local corpus representations. Live production execution with remote/local Ollama generation runs in ~5.5s–23.5s depending on CPU/GPU hardware.*

---

### Table C: Component Ablation Study
*Evaluated across 7 ablation conditions using [`evaluation/run_ablations.py`](evaluation/run_ablations.py). Results saved in [`evaluation/results/ablation_results.json`](evaluation/results/ablation_results.json).*

| Ablation Condition | Recall@5 | NDCG@5 | Cit Gold F1 | Conflict F1 | Version Acc | $\Delta$ Recall | Primary Impact & Failure Mode |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **Full VisionRAG-X (Ref)** | **1.000** | **0.959** | **0.704** | **1.000** | **1.000** | — | Baseline reference performance. |
| **A: No ASR (Speech off)** | 0.722 | 0.714 | 0.500 | 1.000 | 0.000 | -0.278 | Loses spoken corrections and verbal formulas. |
| **B: No OCR (Slides off)** | 0.639 | 0.612 | 0.454 | 1.000 | 0.333 | -0.361 | Fails on slide code, definitions, and equations. |
| **C: No Vision (Captions off)** | 0.917 | 0.857 | 0.602 | 1.000 | 0.333 | -0.083 | Degrades on diagrammatic architecture figures. |
| **D: No Conflict Detection** | 1.000 | 0.959 | 0.704 | 0.000 | 1.000 | 0.000 | Fails to warn user of speech-slide contradictions. |
| **E: No VEKG Graph** | 1.000 | 0.934 | 0.676 | 1.000 | 0.333 | 0.000 | Surfaces outdated superseded units instead of errata. |
| **F: No Hybrid Index (Dense-only)**| 0.944 | 0.874 | 0.611 | 1.000 | 0.000 | -0.056 | Misses exact Big-O and mathematical notations. |
| **G: No Dynamic Routing** | 1.000 | 0.934 | 0.676 | 1.000 | 0.333 | 0.000 | Sub-optimal ranking on formula & code queries. |

---

### Table D: System & Test Validation Record
| Test Suite / Command | Execution Scope | Passed | Failed | Skipped | Status |
| :--- | :--- | :---: | :---: | :---: | :---: |
| `pytest backend/tests/` | Complete backend test suite | 184 | 0 | 2* | **PASS** |
| `pytest backend/tests/test_multi_strategy_search.py` | Multi-strategy search, routing, fallbacks | 10 | 0 | 0 | **PASS** |
| `pytest backend/tests/test_source_chat_isolation.py` | Cross-source isolation & conversation boundaries | 9 | 0 | 0 | **PASS** |
| `pytest backend/tests/test_video_multimodal_ingestion.py` | Both ASR & OCR modality enforcement | 12 | 0 | 0 | **PASS** |
| `npm test -- --run` | Frontend React UI unit tests | 16 | 0 | 0 | **PASS** |
| `npm run build` | Vite production bundle compilation | 1591 modules | 0 | 0 | **PASS** |
| `python evaluation/run_eval.py` | 6-baseline comparative evaluation | 120 / 120 | 0 | 0 | **PASS** |
| `python evaluation/run_ablations.py` | 7-condition ablation matrix | 140 / 140 | 0 | 0 | **PASS** |

*\*Note: 2 tests skipped in `test_ollama_live.py` when live Ollama server is offline during CI sandbox runs.*

---

## 12. Evaluation Methodology & Formulations

- **Recall@K**: Fraction of gold evidence units retrieved within the top-$K$ candidates:
  $$\text{Recall@K} = \frac{|\mathcal{R}_K \cap \mathcal{G}|}{|\mathcal{G}|}$$
- **Mean Reciprocal Rank (MRR)**: Evaluates ranking position of the first relevant gold evidence unit:
  $$\text{MRR} = \frac{1}{|Q|} \sum_{i=1}^{|Q|} \frac{1}{\text{rank}_i}$$
- **Normalized Discounted Cumulative Gain (NDCG@K)**: Measures graded relevance position:
  $$\text{NDCG@K} = \frac{\text{DCG@K}}{\text{IDCG@K}}, \quad \text{DCG@K} = \sum_{i=1}^K \frac{2^{\text{rel}_i} - 1}{\log_2(i + 1)}$$
- **Citation Gold F1**: Harmonic mean of precision and recall between cited Knowledge Unit IDs in the generated answer and gold evidence IDs.
- **Version Accuracy**: Measures the proportion of errata queries where the pipeline surfaces the active correction rather than the superseded statement.
- **Abstention Accuracy**: Fraction of unanswerable queries on which the sufficiency gate cleanly abstains ($1.0$ = zero false hallucinations).

---

## 13. Installation & Setup Guide

### 13.1. Prerequisites
- **Operating System**: macOS (Apple Silicon / Intel) or Linux (Ubuntu 22.04+)
- **Python**: 3.11+
- **Node.js**: v18+ or v20+
- **PostgreSQL**: Running on port `5432`
- **FFmpeg & Tesseract OCR**:
  ```bash
  # macOS (Homebrew)
  brew install postgresql@16 tesseract ffmpeg ollama
  brew services start postgresql@16
  createdb visionrag_x 2>/dev/null || true

  # Linux (Ubuntu/Debian)
  sudo apt update && sudo apt install -y postgresql tesseract-ocr ffmpeg
  ```

### 13.2. Setup Ollama (Local Language Model)
```bash
ollama serve &
ollama pull llama3.2:3b
```

### 13.3. Configure Environment
```bash
cp .env.example .env
# Default verified local settings:
# LLM_PROVIDER=ollama
# OLLAMA_BASE_URL=http://localhost:11434
# OLLAMA_MODEL=llama3.2:3b
# POSTGRES_URL=postgresql+asyncpg://visionrag:visionrag@localhost:5432/visionrag_x
```

### 13.4. Backend Service Startup
```bash
cd backend
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
*Health Check:* `curl http://localhost:8000/health` \(\rightarrow\) `{"status":"ok"}`

### 13.5. Frontend Service Startup
```bash
cd frontend
npm install
npm run dev
```
Open **`http://localhost:5173`** in your browser.

---

## 14. Usage & Research Demonstration Sequence

For a complete step-by-step viva presentation script, consult **[`docs/FINAL_DEMO_GUIDE.md`](docs/FINAL_DEMO_GUIDE.md)**.

### Demonstration Walkthrough
1. **Multimodal Knowledge Ingestion**:
   - Navigate to `/sources`. Ingest `Masters of Enterprise - 01.mp3` or the `Backtracking tutorial` video.
   - Observe independent completion of ASR speech recognition and OCR slide text analysis.
2. **Browsing Multimodal Atoms**:
   - Open `/knowledge-units`. Filter by modality (`asr`, `ocr`, `code`, `formula`). Notice explicit timestamp ranges and page numbers.
3. **Cross-Modal Contradiction Detection**:
   - Open `/chat`. Select `VisionRAG-X_Sample_Course.pdf`.
   - Ask: *"What is the time complexity of merge sort?"*
   - Observe the **Conflict Detected** badge. Side-by-side comparison displays the initial $O(n^2)$ claim alongside the $O(n \log n)$ correction.
4. **VEKG Errata Resolution**:
   - Expand the **Retrieval & Verification Trace** toggle.
   - Observe that the superseded claim on Page 2 was resolved to the active erratum on Page 6 via the VEKG lineage walk.
5. **Multi-Strategy Dynamic Routing**:
   - Set Strategy Selector to `Timestamp / Temporal`.
   - Ask: *"What is discussed at 01:30 in the video?"* on the Backtracking video.
   - Observe the exact temporal unit (01:30–01:45) retrieved. Click the citation to seek the video player.
6. **Global Knowledge Base (Multi-Source Search)**:
   - Select `🌐 All Sources (Global Knowledge Base)` in the dropdown.
   - Ask: *"What algorithms and data structures are covered in the materials?"*
   - Observe synthesized evidence across video and slide sources with distinct `Source: <title>` cards.
7. **Anti-Hallucination Safe Abstention**:
   - Ask: *"What is quantum entanglement spin teleportation?"*
   - Observe deterministic abstention without hallucination:
     > *"The provided educational sources do not establish this answer; insufficient evidence."*

---

## 15. Testing & Development

### Run Backend Unit & Integration Tests (186 tests)
```bash
cd backend
.venv/bin/pytest tests/ -v
```

### Run Frontend Component Tests (16 tests)
```bash
cd frontend
npm test -- --run
```

### Compile Production Frontend Bundle
```bash
cd frontend
npm run build
```

### Reproduce Empirical Benchmark Evaluation
```bash
cd visionrag-x
backend/.venv/bin/python3 evaluation/run_eval.py
backend/.venv/bin/python3 evaluation/run_ablations.py
```

---

## 16. Limitations & Threats to Validity

1. **Embedded Qdrant File Lock Contention**: Local embedded Qdrant (`data/processed/qdrant_storage`) enforces single-process locking. If multiple processes concurrently access it, VisionRAG-X falls back to its in-memory vector store or BM25 index. In multi-worker production deployments, run standalone Qdrant on port 6333 (`docker compose up qdrant`).
2. **CPU Inference Latency**: Local CPU generation with `llama3.2:3b` requires ~5.5s–23.5s per turn depending on evidence context length. On Apple Silicon Metal (MPS) or CUDA GPUs, generation latency drops to <2s.
3. **OCR on Low-Contrast Video**: Text embedded in complex graphical backgrounds or blurry slide streams requires adaptive contrast enhancement, which is computationally heavier on 4K frames.

---

## 17. Security & Privacy Guarantees

- **100% Local Inference**: By default, VisionRAG-X runs entirely on-premises using PostgreSQL, local Qdrant, and local Ollama (`llama3.2:3b`). No video frames, student queries, or lecture transcripts leave your local infrastructure.
- **Source Isolation Guarantee**: Single-source AI chat enforces strict database and retrieval boundaries. Evidence from Source A can never leak into queries scoped to Source B.
- **Zero Committed Secrets**: All endpoints and keys are loaded via environment variables (`.env`). No API keys or credentials are committed.

---

## 18. Future Work

- **Cross-Encoder Reranking**: Replacing score-fused heuristics with a trained multimodal cross-encoder for joint visual-textual relevance reranking.
- **Live Whiteboard Tracking**: Real-time handwriting recognition for unstructured instructor whiteboard derivations.
- **Dynamic Graph Expansion**: Automatic extraction of prerequisite relationships (`requires_knowledge_of`) across semester-long course curricula.

---

## 19. References

1. Lewis, P., et al. (2020). *Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks*. NeurIPS 2020.
2. Radford, A., et al. (2023). *Robust Speech Recognition via Large-Scale Weak Supervision (Whisper)*. ICML 2023.
3. Smith, R. (2007). *An Overview of the Tesseract OCR Engine*. ICDAR 2007.
4. Robertson, S., & Zaragoza, H. (2009). *The Probabilistic Relevance Framework: BM25 and Beyond*. Information Retrieval.
5. Févry, T., et al. (2020). *Entities as Experts: Sparse Memory Access with Entity Supervision*. EMNLP 2020.

---

## 20. License & Citation

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.

### Citation
```bibtex
@misc{visionragx2026,
  author = {Abhiram V},
  title = {VisionRAG-X: A Conflict-Aware Framework for Verified Multimodal Knowledge Retrieval from Educational Videos},
  year = {2026},
  publisher = {GitHub},
  howpublished = {\url{https://github.com/vabhiram/VisionRAG}}
}
```

---

## 21. Supporting Documentation Links

- **[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)**: Deep dive into system architecture, data models, and Mermaid diagrams.
- **[`docs/FILE_REFERENCE.md`](docs/FILE_REFERENCE.md)**: Complete file-by-file research inventory and responsibility matrix.
- **[`docs/IMPLEMENTATION_STATUS.md`](docs/IMPLEMENTATION_STATUS.md)**: Detailed research objective status and acceptance gate evaluation.
- **[`docs/EVALUATION_PROTOCOL.md`](docs/EVALUATION_PROTOCOL.md)**: Mathematical formulations, baseline definitions, and ablation protocols.
- **[`docs/TEST_REPORT.md`](docs/TEST_REPORT.md)**: Exact commands and outputs for backend, frontend, and live model tests.
- **[`docs/FINAL_DEMO_GUIDE.md`](docs/FINAL_DEMO_GUIDE.md)**: Step-by-step viva presentation and live demonstration walkthrough.
