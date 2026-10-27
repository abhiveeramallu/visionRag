# VisionRAG-X: Local Demonstration & Viva Guide

> **Project**: VisionRAG-X: A Conflict-Aware Framework for Verified Multimodal Knowledge Retrieval from Educational Videos  
> **Environment**: Native Local Setup (No Docker required)

---

## 1. Prerequisites & Environment Setup

VisionRAG-X runs directly on macOS/Linux using native Python virtual environments and Node.js.

### 1.1. System Requirements
- **Python**: 3.11+
- **Node.js**: 18+ (with npm)
- **PostgreSQL**: Running locally on `localhost:5432` with database `visionrag_x`
- **Tesseract OCR**: `brew install tesseract`
- **FFmpeg**: `brew install ffmpeg`
- **Ollama**: `brew install ollama` (with model `llama3.2:3b`)

### 1.2. Database & Local LLM Verification
Ensure PostgreSQL and Ollama are active:
```bash
brew services start postgresql@16
createdb visionrag_x 2>/dev/null || true

# Start Ollama service and ensure llama3.2:3b is pulled
ollama serve &
ollama pull llama3.2:3b
curl -s http://localhost:11434/api/tags
```

---

## 2. Launching the Application

### 2.1. Backend Service (FastAPI + Uvicorn)
Open a terminal in the repository root:
```bash
cd visionrag-x/backend
source .venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
Verify backend health:
```bash
curl http://localhost:8000/health
# Expected: {"status":"healthy","database":"connected","qdrant":"connected",...}
```

### 2.2. Frontend Service (Vite + React)
Open a second terminal:
```bash
cd visionrag-x/frontend
npm run dev
```
Open your browser to: **`http://localhost:5173`**

---

## 3. Walkthrough of the 5 Core Research Sections

The application navigation is organized strictly into 5 research-focused sections:

### Section 1: Home / Sources (`/` and `/sources`)
- **Action**: Upload a lecture PDF (e.g., `sample_lecture.pdf`) or paste a YouTube lecture URL.
- **Under the Hood**:
  - The backend creates a `ProcessingJob`.
  - Audio extraction running via Whisper generates speech segments.
  - Slide rendering + adaptive contrast Tesseract OCR extracts on-screen text and formulas.
  - Knowledge units and evidence items are written transactionally to PostgreSQL and Qdrant.
- **Viva Point**: Notice how extraction progress is streamed live through `/api/status/{source_id}`.

### Section 2: Knowledge Units (`/knowledge-units`)
- **Action**: Browse and filter extracted multimodal atoms.
  - Filter by **Modality**: `Formula`, `OCR`, `ASR`, `Code`, or `Diagram`.
  - Filter by **Status**: `Verified`, `Active`, `Superseded`, or `Disputed`.
  - Real-time search: Type "Merge Sort" or "gradient descent" in the search box.
- **Inspection**: Click any unit to inspect its full provenance pane:
  - Exact stored content and confidence score.
  - Supporting raw evidence segments with extraction modality.
  - **Version Lineage**: View earlier superseded versions and the instructor's correction reason.
  - **Cross-Modal Conflicts**: Direct alert if this unit contradicts another modality.

### Section 3: Knowledge Graph / VEKG (`/knowledge-graph`)
- **Action**: Explore the interactive graph of concepts and temporal relationships.
- **Nodes**: Display concepts, modalities, and confidence scores.
- **Edges**:
  - **Corrects / Supersedes** (Emerald/Amber arrows): Connects corrected knowledge units to outdated versions (e.g. Page 6 erratum correcting Page 2 formula).
  - **Conflicts With** (Rose dashed lines): Connects co-occurring claims that directly contradict each other across speech and slides.
  - **Related Concept**: Conceptual associations across document pages or lecture timestamps.
- **Viva Point**: This graph is not a generic mockup; every node and edge is queried from stored `KnowledgeUnit` and `Conflict` records.

### Section 4: AI Chat (`/chat`)
- **Action**: Query the knowledge base with grounded, source-isolated questions:
  1. **Source Selection & Session Isolation**:
     - At the top of the AI Chat interface, use the **Source Selector dropdown** to pick any completed lecture source.
     - Notice that switching between sources immediately unloads the previous conversation and loads the persistent history for the selected source with zero message leakage.
     - Direct URL navigation (`http://localhost:5173/chat?source_id=<id>`) or refreshing the page preserves the selected source and chat session.
     - Click **"+ New Chat"** to archive the active session and start a clean isolated thread for the current source.
     - Click **"Chat"** directly from any completed source card on the Home page or the "Open Full AI Chat" button in the Source Detail view.
  2. **Context-Aware Suggested Questions**:
     - When a source is selected, notice the dynamic chips under the header: "Suggested questions for this source". These are generated directly from the top concepts extracted and indexed for that source.
     - Click any chip to populate the query input automatically.
  3. *Answerable factual query*: "What is the worst-case time complexity of merge sort?"
  4. *Conflict-aware query*: "What was stated about binary search vs merge sort complexity?"
  5. *Unanswerable query (Abstention test)*: "What is quantum phase estimation?"
- **Inspect the "Retrieval and Verification Trace"**:
  - Under each response, expand the trace card to view:
    - **Source Scoping**: Explicit confirmation of candidate retrieval bounded to `source_id`.
    - **Query Routing**: Pedagogical classification (`formula`, `code`, `conceptual`) and retrieval weights.
    - **Candidate counts**: Dense vs lexical matches within the target source.
    - **VEKG Lineage Resolution**: Confirms whether a superseded unit was replaced by its verified correction within the source.
    - **Evidence Sufficiency Gate**: Confirms grounding overlap verification, or explains why the pipeline abstained.
    - **Latency**: Sub-millisecond local in-memory scoring latency.

### Section 5: Evaluation & Benchmarks (`/evaluation`)
- **Action**: Inspect empirical results and execute live evaluations:
  - **Comparative Table (6 Systems)**: Compare Transcript-Only RAG, Speech+OCR, Standard Multimodal, Conflict-Aware, VEKG, and Full VisionRAG-X.
  - **Ablation Matrix (7 Conditions)**: Inspect the degradation when disabling ASR, OCR, Vision captions, Conflict detection, VEKG, or Dynamic Routing.
  - **Per-Query Explorer**: Inspect all 20 synthetic queries and 15 real-video queries, complete with gold unit IDs and ground truth answers.
  - **Live Evaluation Runner**: Click "Run Synthetic (20 Q)", "Run Real-Video (15 Q)", or "Run Ablation (7 Cond)". Real stdout logs stream into the terminal drawer, and tables refresh automatically!

---

## 4. Key Viva Questions & Model Answers

### Q1: What makes VisionRAG-X different from standard multimodal RAG?
**Answer**: Standard multimodal RAG retrieves chunks using naive vector similarity and concatenates them into the LLM context. When instructors correct verbal slips or slides contradict speech, standard RAG feeds contradictory claims to the LLM, leading to hallucinations. VisionRAG-X actively detects cross-modal contradictions, maintains version lineage in a VEKG to substitute superseded claims with verified corrections, and applies an evidence sufficiency gate to abstain safely on ungrounded queries.

### Q2: How does the VEKG prevent outdated errors from polluting answers?
**Answer**: When an erratum or correction is ingested, it is stored with `previous_version_id` pointing to the older unit, marking the older unit as `superseded`. During retrieval, the VEKG traverser inspects candidate units; if a retrieved unit has been superseded, the graph traversal follows the forward lineage pointer and substitutes the candidate with its active, verified replacement before generation.

### Q3: What is the semantic difference between a resolved conflict and an unresolved candidate?
**Answer**: In Section 4.1 of our architecture, when the LLM verification component is unavailable, times out, or encounters a network error, candidate conflicts are preserved with `is_genuine_conflict = None` (`unresolved`). They are not falsely marked as confirmed non-conflicts (`False`). This ensures conservative transparency during partial system failures.
