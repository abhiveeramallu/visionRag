# VisionRAG-X: Final Project Demonstration & Verification Guide

> **System**: VisionRAG-X: A Conflict-Aware Framework for Verified Multimodal Knowledge Retrieval from Educational Videos  
> **Authors**: Abhiram V (Final-Year Research Project)  
> **Date**: 2026-10-27  

---

## 1. System Requirements & Environment Setup

### 1.1. Prerequisites
- **Python**: 3.11+
- **Node.js**: v18+ or v20+
- **PostgreSQL**: Running on port `5432` (database `visionrag_x`)
- **Ollama**: Running on port `11434` with model `llama3.2:3b` pulled:
  ```bash
  ollama pull llama3.2:3b
  ollama run llama3.2:3b
  ```
- **FFmpeg & Tesseract OCR**: Installed and available in `$PATH`.

---

## 2. Service Startup

### Terminal 1: Backend Service
```bash
cd visionrag-x/backend
source .venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
*Health check:* `curl http://localhost:8000/health` \(\rightarrow\) `{"status":"ok"}`

### Terminal 2: Frontend Service
```bash
cd visionrag-x/frontend
npm run dev
```
*Web UI available at:* `http://localhost:5173`

---

## 3. Five-Stage Research Demonstration Walkthrough

### Step 1: Multimodal Knowledge Units & Ingestion (Contribution 1)
1. Open `http://localhost:5173/sources` in the browser.
2. Ingest or select an existing educational video or audio source (e.g. *Backtracking tutorial* or *Masters of Enterprise 01.mp3*).
3. Observe modality-specific extraction completion:
   - Speech Recognition (`ASR`)
   - Text Extraction (`OCR`)
   - Mathematical formula extraction
4. Navigate to **Knowledge Units** (`/knowledge-units`):
   - Filter by source: Notice distinct Knowledge Units generated for speech (`ASR`) and slides (`OCR`) preserving exact timestamps and pages.

---

### Step 2: Cross-Modal Conflict Detection (Contribution 2)
1. Navigate to **AI Chat** (`/chat`).
2. Select the source: `VisionRAG-X_Sample_Course.pdf`.
3. Select Retrieval Strategy: `Keyword Search (BM25)` or `Auto`.
4. Ask:
   ```
   What is the time complexity of merge sort?
   ```
5. **Expected Research Behavior**:
   - The system detects the contradiction between the initial statement ($O(n^2)$) and the corrected equation ($O(n \log n)$).
   - In the chat response, a **Conflict Detected** badge appears.
   - The comparison panel displays the contradictory claims side-by-side with confidence and status.

---

### Step 3: VEKG Versioned Lineage Resolution (Contribution 3)
1. In **AI Chat** with `VisionRAG-X_Sample_Course.pdf` selected.
2. Open the **Retrieval & Verification Trace** toggle below the assistant answer.
3. Observe the **VEKG Lineage Resolution** section:
   - Lineage resolver identifies that the earlier claim was superseded by an erratum on Page 6.
   - The answer generation pipeline automatically substitutes the outdated unit with the active correction.
4. Navigate to **Knowledge Graph** (`/knowledge-graph`) to view the interactive graph of concepts and `EDGE_CORRECTS` / `EDGE_SUPERSEDES` links.

---

### Step 4: Multi-Strategy Dynamic Query Routing (Contribution 4)
Test the five distinct retrieval strategies using the **Strategy Selector** bar:
1. **Timestamp Search**:
   - Select `Backtracking tutorial` video.
   - Select Strategy: `Timestamp / Temporal`.
   - Ask: `What is discussed at 01:30 in the video?`
   - Observe: Retrieves the exact unit at 01:30–01:45 where leaf nodes are discussed.
2. **Formula / Keyword Search (BM25)**:
   - Select Strategy: `Keyword Search (BM25)`.
   - Ask: `What is O(n log n)?`
   - Observe: Mathematical variables (`n`, `O(n log n)`) are preserved and boosted (+3.0).
3. **Knowledge Graph (VEKG) Search**:
   - Select `OSI Model Explained` video.
   - Select Strategy: `Knowledge Graph (VEKG)`.
   - Ask: `Explain the 7 layers of the OSI model.`
   - Observe: Traverses connected layer units across the multigraph.
4. **Global Knowledge Base (Cross-Source Search)**:
   - In the Active Source Scope dropdown, select: `🌐 All Sources (Global Knowledge Base)`.
   - Ask: `What algorithms and data structures are covered in the materials?`
   - Observe: Synthesizes evidence retrieved across multiple separate sources, with explicit `Source: <title>` provenance cards.

---

### Step 5: Citation Verification, Media Seeking & Safe Abstention (Contribution 5)
1. **Media Seeking**:
   - In the chat response, click any timestamp citation (e.g. `[01:30–01:45]`).
   - The synchronized media player jumps directly to that timestamp.
2. **Calibrated Abstention (Anti-Hallucination Gate)**:
   - Select `Backtracking tutorial`.
   - Ask an ungrounded question:
     ```
     What is quantum entanglement spin teleportation?
     ```
   - **Expected Research Behavior**:
     - Sufficiency gate evaluates term overlap against retrieved evidence.
     - System abstains with zero hallucinations:
       > *"The provided educational sources do not establish this answer; insufficient evidence."*
     - Abstention badge displayed in trace with `Confidence: 0.0`.

---

## 4. Evaluation Benchmark Demonstration
To display empirical benchmark comparisons in the UI or CLI:
```bash
cd visionrag-x
backend/.venv/bin/python3 evaluation/run_eval.py
```
View the generated comparative results table in `evaluation/results/benchmark_report.md` or directly on the **Evaluation** page in the frontend (`/evaluation`).
