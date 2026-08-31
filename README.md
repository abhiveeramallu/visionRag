# VisionRAG-X 🎓🔍

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688.svg)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-18-61DAFB.svg)](https://react.dev/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED.svg)](docker-compose.yml)
[![Status: Experimental](https://img.shields.io/badge/Status-Experimental-orange.svg)](#research-novelty--experimental-contributions)

> **A multimodal educational Retrieval-Augmented Generation system that fuses spoken transcripts, visual frames, and document text into a unified, conflict-aware knowledge base.**

---

## Motivation

Modern educational content spans multiple modalities: lecture videos, slides, PDFs, and supplementary readings. Existing RAG pipelines treat these as isolated text documents, discarding rich visual context and ignoring temporal relationships between speech and visuals. When different sources contradict each other — a slide showing an outdated formula while the transcript uses a newer one — learners receive answers that silently blend conflicting information.

**VisionRAG-X** addresses this gap by building a tightly coupled multimodal index where every retrieved chunk carries its modality, timestamp, and source provenance. The system actively detects cross-source conflicts, routes queries to the most informative modality, and cites evidence with precise temporal anchors so learners can verify answers directly in the source material.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        VisionRAG-X  System                              │
│                                                                         │
│  ┌────────────┐   ┌──────────────────────────────────────────────────┐  │
│  │  Sources   │   │              Ingestion Pipeline                  │  │
│  │            │   │                                                  │  │
│  │ YouTube URL│──▶│ yt-dlp ──▶ Whisper ASR ──▶ ASR Chunks           │  │
│  │ Video File │──▶│ FFmpeg ──▶ Frame Extractor ──▶ Vision Encoder    │  │
│  │ PDF / Doc  │──▶│ pdfplumber ──▶ OCR (EasyOCR) ──▶ Text Chunks    │  │
│  └────────────┘   └──────────────────┬───────────────────────────────┘  │
│                                      │                                  │
│                          ┌───────────▼───────────┐                      │
│                          │  Multimodal Embedder  │                      │
│                          │  (BGE + CLIP + BM25)  │                      │
│                          └───────────┬───────────┘                      │
│                                      │                                  │
│          ┌───────────────────────────▼──────────────────────────────┐   │
│          │                    Hybrid Index                          │   │
│          │                                                          │   │
│          │   Qdrant (dense + sparse vectors)  │  PostgreSQL (meta)  │   │
│          └───────────────────────────┬──────────────────────────────┘   │
│                                      │                                  │
│          ┌───────────────────────────▼──────────────────────────────┐   │
│          │               Query-Time Pipeline                        │   │
│          │                                                          │   │
│          │  Query  ──▶  Dynamic Router  ──▶  Hybrid Retriever       │   │
│          │              (text/visual/mixed)   (α·dense + β·sparse   │   │
│          │                                     + γ·visual)          │   │
│          │                    │                                     │   │
│          │                    ▼                                     │   │
│          │          Conflict Detector  ──▶  Conflict Report         │   │
│          │                    │                                     │   │
│          │                    ▼                                     │   │
│          │             LLM Generator  ──▶  Answer + Citations       │   │
│          └──────────────────────────────────────────────────────────┘   │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                   React Frontend                                │   │
│  │  Chat UI │ Document Explorer │ Conflict Inspector │ Eval Panel  │   │
│  └─────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Research Novelty — Experimental Contributions

> ⚠️ **EXPERIMENTAL**: The following contributions are research hypotheses under active development. No results have been validated on a standardised benchmark. Claims below represent design intent, not measured outcomes.

| # | Contribution | Description |
|---|---|---|
| 1 | **Temporal-Visual Alignment (TVA)** | Associates each ASR segment with the video frame closest in time, creating bi-modal chunks that carry both spoken and visual context. |
| 2 | **Visual Knowledge Entity Graph (VKEG)** | Experimental entity graph built from OCR and frame captions; edges encode co-occurrence and temporal adjacency across modalities. |
| 3 | **Cross-Source Conflict Detection** | Cosine-distance + semantic-entailment heuristic that flags contradictions between, e.g., slide text and transcript for the same concept. |
| 4 | **Dynamic Query Router** | Lightweight classifier that routes queries to the most relevant modality subset before retrieval, reducing noise. |
| 5 | **Hybrid α-β-γ Retrieval** | Weighted fusion of dense (semantic), sparse (BM25), and visual (CLIP) scores; weights are configurable and ablation-studied. |
| 6 | **Provenance-Anchored Citations** | Every answer chunk is cited with source filename, modality, and timestamp (for video) so learners can seek directly to the source. |

---

## Features

- 🎥 **YouTube & local video ingestion** — automatic download, transcription (Whisper), and frame extraction (FFmpeg)
- 📄 **PDF / document ingestion** — text extraction (pdfplumber) + OCR fallback (EasyOCR)
- 🔍 **Hybrid retrieval** — dense (BGE embeddings), sparse (BM25), and visual (CLIP) fusion
- ⚡ **Conflict detection** — surfaces contradictions between sources in real-time
- 🕹️ **Dynamic modality routing** — intelligently selects which index layers to query
- 🧠 **Multi-provider LLM support** — OpenAI GPT-4o, Gemini 1.5 Pro, or local Ollama models
- 📌 **Timestamped citations** — answers link back to exact video timestamps and page numbers
- 🧪 **Built-in evaluation framework** — recall@k, MRR, NDCG, token-F1, hallucination heuristics
- 🐳 **One-command Docker setup** — full stack in containers

---

## Project Structure

```
visionrag-x/
├── backend/                    # FastAPI backend
│   ├── app/
│   │   ├── api/                # Route handlers
│   │   │   ├── documents.py
│   │   │   ├── query.py
│   │   │   └── health.py
│   │   ├── core/               # Config, DB, settings
│   │   │   ├── config.py
│   │   │   └── database.py
│   │   ├── ingestion/          # Ingestion pipeline
│   │   │   ├── video_ingester.py
│   │   │   ├── pdf_ingester.py
│   │   │   ├── frame_extractor.py
│   │   │   ├── asr_transcriber.py
│   │   │   └── ocr_processor.py
│   │   ├── embeddings/         # Embedding models
│   │   │   ├── text_embedder.py
│   │   │   └── visual_embedder.py
│   │   ├── retrieval/          # Retrieval logic
│   │   │   ├── hybrid_retriever.py
│   │   │   ├── query_router.py
│   │   │   └── reranker.py
│   │   ├── conflict/           # Conflict detection
│   │   │   └── detector.py
│   │   ├── generation/         # LLM generation
│   │   │   ├── llm_client.py
│   │   │   └── prompt_builder.py
│   │   ├── models/             # SQLAlchemy ORM models
│   │   │   └── document.py
│   │   └── main.py
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/                   # React + TypeScript frontend
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   ├── hooks/
│   │   └── main.tsx
│   ├── Dockerfile
│   └── package.json
├── evaluation/                 # Evaluation framework
│   ├── README.md
│   ├── metrics/
│   │   ├── retrieval_metrics.py
│   │   └── answer_metrics.py
│   ├── baselines/
│   │   └── baseline_configs.yaml
│   ├── experiments/
│   │   └── ablation_config.yaml
│   └── results/
│       └── .gitkeep
├── data/
│   ├── uploads/.gitkeep
│   ├── frames/.gitkeep
│   ├── transcripts/.gitkeep
│   └── processed/.gitkeep
├── docs/
│   └── architecture.md
├── .env.example
├── .gitignore
├── docker-compose.yml
├── LICENSE
└── README.md
```

---

## Prerequisites

| Dependency | Version | Purpose |
|---|---|---|
| Python | 3.11+ | Backend runtime |
| FFmpeg | 6+ | Video frame extraction & audio conversion |
| Node.js | 18+ | Frontend build |
| Docker + Compose | Latest | Containerised deployment |
| Git | Any | Version control |

**macOS (Homebrew):**
```bash
brew install python@3.11 ffmpeg node docker
```

**Ubuntu / Debian:**
```bash
sudo apt update && sudo apt install -y python3.11 python3.11-venv ffmpeg nodejs docker.io
```

---

## Local Installation

### 1. Clone the repository

```bash
git clone https://github.com/your-org/visionrag-x.git
cd visionrag-x
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env and add your API keys
```

### 3. Backend setup

```bash
cd backend
python3.11 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Frontend setup

```bash
cd ../frontend
npm install
```

### 5. Start infrastructure (Postgres + Qdrant)

```bash
# From project root
docker compose up postgres qdrant -d
```

### 6. Run database migrations

```bash
cd backend
source .venv/bin/activate
alembic upgrade head
```

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `LLM_PROVIDER` | `openai` | LLM backend: `openai`, `gemini`, `local` |
| `OPENAI_API_KEY` | — | OpenAI API key |
| `OPENAI_MODEL` | `gpt-4o` | OpenAI chat model |
| `GEMINI_API_KEY` | — | Google Gemini API key |
| `EMBEDDING_MODEL` | `BAAI/bge-base-en-v1.5` | HuggingFace embedding model |
| `QDRANT_URL` | `http://localhost:6333` | Qdrant endpoint |
| `QDRANT_COLLECTION` | `visionrag_x` | Qdrant collection name |
| `POSTGRES_URL` | `postgresql+asyncpg://...` | Async PostgreSQL URL |
| `FRAME_INTERVAL` | `2` | Seconds between extracted frames |
| `WHISPER_MODEL` | `base` | Whisper model size |
| `RETRIEVAL_ALPHA` | `0.6` | Dense retrieval weight |
| `RETRIEVAL_BETA` | `0.3` | Sparse (BM25) retrieval weight |
| `RETRIEVAL_GAMMA` | `0.1` | Visual retrieval weight |
| `CONFLICT_DETECTION_ENABLED` | `true` | Enable conflict detection |
| `CONFLICT_SEVERITY_THRESHOLD` | `0.5` | Conflict severity cutoff |
| `APP_PORT` | `8000` | Backend HTTP port |
| `DEBUG` | `false` | Enable debug logging |

---

## Running Locally

### Backend

```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Frontend

```bash
cd frontend
npm run dev
# Vite dev server starts at http://localhost:5173
```

Open your browser at **http://localhost:5173** (dev) or **http://localhost:3000** (Docker).

---

## Docker Setup

```bash
# Build and start all services
docker compose up --build

# Run in detached mode
docker compose up --build -d

# View logs
docker compose logs -f backend

# Stop everything
docker compose down

# Full reset (removes volumes)
docker compose down -v
```

Services:

| Service | URL |
|---|---|
| Backend API | http://localhost:8000 |
| API Docs (Swagger) | http://localhost:8000/docs |
| Frontend | http://localhost:3000 |
| Qdrant Dashboard | http://localhost:6333/dashboard |
| PostgreSQL | localhost:5432 |

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/health` | Health check |
| `POST` | `/api/documents/upload` | Upload PDF or video file |
| `POST` | `/api/documents/youtube` | Ingest YouTube URL |
| `GET` | `/api/documents` | List all documents |
| `GET` | `/api/documents/{id}` | Get document metadata |
| `DELETE` | `/api/documents/{id}` | Delete document and chunks |
| `POST` | `/api/query` | Submit a query, receive answer + citations |
| `GET` | `/api/query/history` | Retrieve query history |
| `GET` | `/api/conflicts` | List detected conflicts |
| `GET` | `/api/conflicts/{id}` | Get conflict detail |
| `GET` | `/api/eval/metrics` | Retrieval metric summary |

---

## Example Workflows

### Ingest a YouTube Lecture

```bash
curl -X POST http://localhost:8000/api/documents/youtube \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.youtube.com/watch?v=<VIDEO_ID>", "title": "MIT 6.006 Lecture 1"}'
```

Response:
```json
{
  "document_id": "doc_abc123",
  "status": "processing",
  "estimated_duration_seconds": 120
}
```

### Ingest a PDF

```bash
curl -X POST http://localhost:8000/api/documents/upload \
  -F "file=@lecture_notes.pdf" \
  -F "title=Lecture Notes Week 1"
```

### Ask a Question

```bash
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"query": "What is the time complexity of merge sort?", "top_k": 5}'
```

Response:
```json
{
  "answer": "Merge sort has a time complexity of O(n log n) in all cases — best, average, and worst. This is because the array is recursively divided into halves (log n levels) and each level requires O(n) work to merge.",
  "citations": [
    {
      "source": "MIT 6.006 Lecture 1",
      "modality": "asr",
      "timestamp": "00:14:32",
      "text": "...so dividing n elements log n times gives us our O(n log n) bound..."
    },
    {
      "source": "Lecture Notes Week 1",
      "modality": "text",
      "page": 7,
      "text": "Merge Sort: T(n) = 2T(n/2) + O(n) → O(n log n) by the Master Theorem."
    }
  ],
  "conflicts": [],
  "retrieval_scores": {"dense": 0.87, "sparse": 0.71, "visual": 0.12}
}
```

---

## Evaluation Methodology

VisionRAG-X ships with an evaluation framework under `evaluation/`. The framework is designed to support reproducible comparison of the full system against simpler baselines and ablations.

### Retrieval Metrics

| Metric | Formula | Notes |
|---|---|---|
| Recall@K | \|relevant ∩ retrieved[:K]\| / \|relevant\| | Standard corpus recall |
| Precision@K | \|relevant ∩ retrieved[:K]\| / K | Precision of top-K |
| MRR | 1/rank of first relevant | Mean reciprocal rank |
| NDCG@K | DCG@K / IDCG@K | Normalised discounted CG |
| MAP | Mean of AP across queries | Average precision |

### Answer Quality Metrics

| Metric | Description | Status |
|---|---|---|
| Exact Match | Binary match after normalisation | Implemented (NOT YET VALIDATED) |
| Token F1 | Token-overlap F1 between prediction and GT | Implemented (NOT YET VALIDATED) |
| Citation Accuracy | Fraction of cited sources matching retrieved evidence | Implemented (NOT YET VALIDATED) |
| Hallucination Rate (heuristic) | N-gram coverage of answer against retrieved context | Implemented (NOT YET VALIDATED) |

> ⚠️ **Research Integrity Note**: No benchmark results are reported in this README because no controlled evaluation has been completed. All metric implementations are available in `evaluation/metrics/` for community review.

---

## Baselines

Four baselines are defined in `evaluation/baselines/baseline_configs.yaml`:

| Baseline | Components | Purpose |
|---|---|---|
| `asr_only` | Whisper ASR → text-only RAG | Lower bound: ignores visuals and documents |
| `asr_ocr` | ASR + OCR text | Ablates vision captioning and graph |
| `standard_multimodal` | ASR + OCR + Vision | Ablates VKEG, conflict detection, and dynamic routing |
| `visionrag_x` | Full system | All components enabled |

---

## Ablation Studies

Seven ablation configurations (A–G) are defined in `evaluation/experiments/ablation_config.yaml`:

| Study | Disabled Component | Hypothesis |
|---|---|---|
| A | `asr` | System degrades severely on audio-centric queries |
| B | `ocr` | Degrades on document-heavy content |
| C | `vision` | Minimal effect on text queries; large effect on diagram queries |
| D | `conflict_detection` | Answers become less trustworthy when sources conflict |
| E | `vkeg` | Degrades on multi-hop entity-centric queries |
| F | `hybrid_indexing` | Dense-only retrieval drops recall on keyword queries |
| G | `dynamic_routing` | Increased latency and noise from querying all modalities |

---

## Research Integrity

This repository does **not** report fabricated or estimated results. All metric implementations are provided as tools for the community to run evaluations on their own datasets. We welcome reproducibility contributions via pull requests.

---

## Future Work

- [ ] Streaming answer generation with Server-Sent Events
- [ ] Support for PowerPoint / Keynote ingestion
- [ ] Fine-tuned cross-modal reranker
- [ ] Real-time collaborative annotation of conflicts
- [ ] Automated test dataset generation from lecture transcripts
- [ ] Benchmark on MMQA, WebQA, and a purpose-built educational QA dataset
- [ ] Memory-efficient chunk streaming for very long videos (> 3 hours)
- [ ] Plugin system for custom embedding models
- [ ] Multi-tenant support with per-user collections

---

## License

[MIT](LICENSE) © 2025 VisionRAG-X Authors
