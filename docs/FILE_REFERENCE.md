# VisionRAG-X: Research Codebase & File Reference

> **Repository**: `visionrag-x`  
> **Framework**: VisionRAG-X: A Conflict-Aware Framework for Verified Multimodal Knowledge Retrieval from Educational Videos  
> **Last Verified**: 2026-10-27  

This document catalogs every research-critical file in the VisionRAG-X codebase, detailing its architectural responsibility, research role, and key exported symbols.

---

## 1. Backend Core Architecture (`backend/app/`)

### 1.1. Ingestion & Multimodal Extraction (`backend/app/ingestion/`)
- **[`orchestrator.py`](file:///Users/vabhiram/Documents/VisionRAG/visionrag-x/backend/app/ingestion/orchestrator.py)**: Central coordinator executing the 9-stage multimodal extraction pipeline (Source received \(\rightarrow\) Audio extraction \(\rightarrow\) Frame extraction \(\rightarrow\) Speech recognition \(\rightarrow\) OCR analysis \(\rightarrow\) Visual analysis \(\rightarrow\) Verification \(\rightarrow\) VEKG construction \(\rightarrow\) Indexing). Enforces both ASR and OCR for video.
- **[`audio.py`](file:///Users/vabhiram/Documents/VisionRAG/visionrag-x/backend/app/ingestion/audio.py)**: Audio track extraction via FFmpeg (16 kHz mono WAV conversion) and speech-to-text segmentation via OpenAI Whisper (`whisper-base`).
- **[`ocr.py`](file:///Users/vabhiram/Documents/VisionRAG/visionrag-x/backend/app/ingestion/ocr.py)**: Adaptive slide text extraction using Tesseract OCR with Otsu binarization and contrast enhancement. Bounded concurrency (max 4 workers) to prevent CPU lockup.
- **[`video.py`](file:///Users/vabhiram/Documents/VisionRAG/visionrag-x/backend/app/ingestion/video.py)**: Keyframe extraction using scene-change detection (`select='gt(scene,0.3)'`) with fallback to fixed 5-second sampling.
- **[`vision.py`](file:///Users/vabhiram/Documents/VisionRAG/visionrag-x/backend/app/ingestion/vision.py)**: Vision-Language Model interface for diagram and architectural figure captioning.
- **[`youtube.py`](file:///Users/vabhiram/Documents/VisionRAG/visionrag-x/backend/app/ingestion/youtube.py)**: YouTube lecture ingest via `yt-dlp` with format selection and URL sanitization.
- **[`timestamp_aligner.py`](file:///Users/vabhiram/Documents/VisionRAG/visionrag-x/backend/app/ingestion/timestamp_aligner.py)**: Temporal window alignment fusing asynchronous ASR segments, OCR frame timestamps, and slide intervals into aligned multimodal windows.

### 1.2. Knowledge Representation & Graph (`backend/app/knowledge/`)
- **[`models.py`](file:///Users/vabhiram/Documents/VisionRAG/visionrag-x/backend/app/knowledge/models.py)**: SQLAlchemy ORM models for PostgreSQL: `Source`, `KnowledgeUnit`, `Conflict`, `ChatConversation`, `ChatMessage`, `ProcessingJob`, and `EvaluationRun`.
- **[`knowledge_units.py`](file:///Users/vabhiram/Documents/VisionRAG/visionrag-x/backend/app/knowledge/knowledge_units.py)**: `ProcessedKnowledgeUnit` dataclass representing discrete multimodal knowledge atoms with confidence, modality, temporal/page coordinates, and version lineage (`previous_version_id`).
- **[`vekg.py`](file:///Users/vabhiram/Documents/VisionRAG/visionrag-x/backend/app/knowledge/vekg.py)**: Versioned Educational Knowledge Evolution Graph (VEKG) implemented using NetworkX directed multigraph. Connects concepts via `EDGE_SUPPORTS`, `EDGE_CONFLICTS_WITH`, `EDGE_CORRECTS`, `EDGE_SUPERSEDES`, and `EDGE_RELATED_TO`. Implements `traverse_related_concepts()` for multi-hop graph retrieval and lineage replacement.

### 1.3. Verification & Conflict Detection (`backend/app/verification/`)
- **[`conflict_detector.py`](file:///Users/vabhiram/Documents/VisionRAG/visionrag-x/backend/app/verification/conflict_detector.py)**: Cross-modal contradiction engine. Detects numerical mismatches, algebraic formula discrepancies (via SymPy AST parsing), and speech-vs-slide contradictions. Preserves unresolved candidate conflicts on verifier failure.
- **[`provenance.py`](file:///Users/vabhiram/Documents/VisionRAG/visionrag-x/backend/app/verification/provenance.py)**: Provenance tracker maintaining end-to-end evidence chains from raw source extraction coordinates to chat citation rendering.
- **[`confidence_scorer.py`](file:///Users/vabhiram/Documents/VisionRAG/visionrag-x/backend/app/verification/confidence_scorer.py)**: Calibrated composite confidence scoring based on extraction quality, recurrence, and cross-modal agreement.

### 1.4. Indexing & Storage (`backend/app/indexing/`)
- **[`vector_index.py`](file:///Users/vabhiram/Documents/VisionRAG/visionrag-x/backend/app/indexing/vector_index.py)**: Dense vector indexing via Qdrant and SentenceTransformers (`all-MiniLM-L6-v2`, 384 dimensions).
- **[`lexical_index.py`](file:///Users/vabhiram/Documents/VisionRAG/visionrag-x/backend/app/indexing/lexical_index.py)**: BM25 lexical index preserving single-character mathematical variables (`n`, `x`, `y`, `k`, `o`) and mathematical Big-O notations (`O(n log n)`), with exact multi-word phrase boosts (+3.0) and concept keyword boosts (+1.5).
- **[`hybrid_index.py`](file:///Users/vabhiram/Documents/VisionRAG/visionrag-x/backend/app/indexing/hybrid_index.py)**: Score-fused retrieval combining dense vector similarity, BM25 lexical scores, and extraction prior confidence:
  $$\text{Score}(q, u) = \alpha \cdot \text{Dense}(q, u) + \beta \cdot \text{Lexical}(q, u) + \gamma \cdot \text{Prior}(u)$$
  Features automatic fallback to BM25 if Qdrant is unreachable or file-locked.

### 1.5. Dynamic Routing & Retrieval Pipeline (`backend/app/routing/`, `backend/app/retrieval/`)
- **[`dynamic_router.py`](file:///Users/vabhiram/Documents/VisionRAG/visionrag-x/backend/app/routing/dynamic_router.py)**: Adaptive query classifier categorizing questions into `FORMULA`, `CODE`, `CONCEPTUAL`, `FACTUAL`, `TIMESTAMP`, and `DEFINITION`. Supports explicit user strategy overrides (`semantic`, `keyword`, `graph`, `timestamp`, `hybrid`).
- **[`retrieval_pipeline.py`](file:///Users/vabhiram/Documents/VisionRAG/visionrag-x/backend/app/retrieval/retrieval_pipeline.py)**: Main retrieval orchestrator. Implements `_extract_temporal_targets()`, temporal proximity decay scoring, VEKG lineage substitution of superseded claims, and the subject-aware anti-hallucination sufficiency gate (`check_evidence_sufficiency()`).

### 1.6. Generation & Answer Synthesis (`backend/app/generation/`)
- **[`llm.py`](file:///Users/vabhiram/Documents/VisionRAG/visionrag-x/backend/app/generation/llm.py)**: Multi-provider LLM abstraction supporting native local Ollama (`llama3.2:3b`), OpenAI, Gemini, and OpenAI-compatible endpoints with configurable timeouts, retries, and friendly student error messaging.
- **[`answer.py`](file:///Users/vabhiram/Documents/VisionRAG/visionrag-x/backend/app/generation/answer.py)**: Grounded answer generator formatting prompt contexts strictly from retrieved evidence and formatting verified citations (`[1] [ASR] 01:30–01:45`).

### 1.7. API Endpoints (`backend/app/api/`)
- **[`query.py`](file:///Users/vabhiram/Documents/VisionRAG/visionrag-x/backend/app/api/query.py)**: AI Chat query endpoint (`/api/query`), conversation session management, suggested questions, and Global Knowledge Base (`source_id='all'`).
- **[`upload.py`](file:///Users/vabhiram/Documents/VisionRAG/visionrag-x/backend/app/api/upload.py)**: File upload (`/api/upload`) and YouTube ingestion (`/api/youtube`) triggering background Celery/thread tasks.
- **[`sources.py`](file:///Users/vabhiram/Documents/VisionRAG/visionrag-x/backend/app/api/sources.py)**: Source CRUD endpoints, media streaming with HTTP 206 range requests for seeking (`/api/sources/{id}/media`), and source deletion with index cleanup.

---

## 2. Evaluation Suite (`evaluation/`)

- **[`benchmark/dataset.json`](file:///Users/vabhiram/Documents/VisionRAG/visionrag-x/evaluation/benchmark/dataset.json)**: Controlled synthetic benchmark containing 20 gold questions, 15 multimodal atoms, 2 contradictions, and 2 lineage chains.
- **[`benchmark/real_video_dataset.json`](file:///Users/vabhiram/Documents/VisionRAG/visionrag-x/evaluation/benchmark/real_video_dataset.json)**: Real educational video benchmark comprising 15 questions and 18 atoms across Backtracking, OSI Model, and academic lectures.
- **[`run_eval.py`](file:///Users/vabhiram/Documents/VisionRAG/visionrag-x/evaluation/run_eval.py)**: Comparative evaluation runner testing configurations A through F, generating machine-readable JSON results and Markdown reports.
- **[`run_ablations.py`](file:///Users/vabhiram/Documents/VisionRAG/visionrag-x/evaluation/run_ablations.py)**: Ablation study runner executing 7 ablation conditions (No ASR, No OCR, No Vision, No Conflict Detection, No VEKG, No Hybrid Index, No Dynamic Routing).
- **[`metrics/retrieval_metrics.py`](file:///Users/vabhiram/Documents/VisionRAG/visionrag-x/evaluation/metrics/retrieval_metrics.py)**: Mathematical formulations for Recall@K, Precision@K, MRR, and NDCG@K.
- **[`metrics/answer_metrics.py`](file:///Users/vabhiram/Documents/VisionRAG/visionrag-x/evaluation/metrics/answer_metrics.py)**: Citation Grounding, Gold Citation F1, Support Rate, Token F1, and Abstention fidelity metrics.

---

## 3. Frontend Architecture (`frontend/src/`)

- **[`pages/Chat.jsx`](file:///Users/vabhiram/Documents/VisionRAG/visionrag-x/frontend/src/pages/Chat.jsx)**: Main AI Chat page with source-isolated session management, Active Source Scope dropdown (including `🌐 All Sources`), interactive Strategy Selector, Modality Filter, and collapsible Retrieval & Verification Trace.
- **[`pages/KnowledgeUnits.jsx`](file:///Users/vabhiram/Documents/VisionRAG/visionrag-x/frontend/src/pages/KnowledgeUnits.jsx)**: Multimodal atom browser with source filtering, modality filters (`asr`, `ocr`, `code`, `formula`, `vision`), and unit deep-dive modal.
- **[`pages/KnowledgeGraph.jsx`](file:///Users/vabhiram/Documents/VisionRAG/visionrag-x/frontend/src/pages/KnowledgeGraph.jsx)**: Interactive 2D NetworkX graph visualization of concept nodes, contradiction links, and errata correction edges.
- **[`pages/Sources.jsx`](file:///Users/vabhiram/Documents/VisionRAG/visionrag-x/frontend/src/pages/Sources.jsx)**: Source management and upload screen showing per-modality ingestion progress.
- **[`pages/SourceDetail.jsx`](file:///Users/vabhiram/Documents/VisionRAG/visionrag-x/frontend/src/pages/SourceDetail.jsx)**: Source metadata and integrated media player with video/audio seeking and PDF preview.
- **[`pages/Evaluation.jsx`](file:///Users/vabhiram/Documents/VisionRAG/visionrag-x/frontend/src/pages/Evaluation.jsx)**: Real-time dashboard displaying empirical comparative baselines, ablation studies, and live test execution logs.
- **[`components/RetrievalStrategyPanel.jsx`](file:///Users/vabhiram/Documents/VisionRAG/visionrag-x/frontend/src/components/RetrievalStrategyPanel.jsx)**: "Why this answer?" component visualizing the active retrieval routes used for each turn.
- **[`components/EvidenceCard.jsx`](file:///Users/vabhiram/Documents/VisionRAG/visionrag-x/frontend/src/components/EvidenceCard.jsx)**: Provenance evidence card displaying modality badges, timestamp/page anchors, source title cards, and confidence meters.
- **[`components/ConflictCompare.jsx`](file:///Users/vabhiram/Documents/VisionRAG/visionrag-x/frontend/src/components/ConflictCompare.jsx)**: Side-by-side contradiction card comparing conflicting claims with resolution status.
