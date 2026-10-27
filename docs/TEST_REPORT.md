# VisionRAG-X: Final Test Execution Report & Verification Record

> **Test Date**: 2026-10-27  
> **Environment**: macOS (Darwin 24.3.0), Python 3.11.14, Node.js v20.12.0  
> **Backend Test Framework**: Pytest 8.2.2 with asyncio 0.23.7  
> **Frontend Test Framework**: Node.js Native Test Runner with React 18 & Vite 5.4.21  

---

## 1. Test Summary Overview

| Test Suite | Total Tests | Passed | Failed | Skipped | Pass Rate | Execution Time |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Backend Unit & Integration Tests** | 186 | 184 | 0 | 2* | **100%** | 11.35s |
| **Multi-Strategy Search Tests** | 10 | 10 | 0 | 0 | **100%** | 1.56s |
| **Source Isolation & VEKG Regressions** | 25 | 25 | 0 | 0 | **100%** | 1.62s |
| **Audio & Video Multimodal Ingestion** | 40 | 40 | 0 | 0 | **100%** | 8.92s |
| **Media Serving & Sources API** | 28 | 28 | 0 | 0 | **100%** | 1.80s |
| **Frontend Component & UI Tests** | 16 | 16 | 0 | 0 | **100%** | 0.36s |
| **Production Frontend Build** | 1591 modules | Success | 0 | 0 | **100%** | 1.67s |
| **Comparative Benchmark Evaluation** | 120 evaluations | 120 | 0 | 0 | **100%** | 0.45s |
| **Ablation Evaluation Matrix** | 140 evaluations | 140 | 0 | 0 | **100%** | 0.52s |

*\*Note: 2 tests skipped in `test_ollama_live.py` when live Ollama server is not running on localhost:11434 during sandbox test runs.*

---

## 2. Test Execution Commands & Outputs

### 2.1. Backend Full Test Suite
**Command:**
```bash
cd visionrag-x/backend && .venv/bin/pytest -v
```
**Output Summary:**
```
============================= test session starts ==============================
platform darwin -- Python 3.11.14, pytest-8.2.2, pluggy-1.6.0
collected 186 items

tests/test_api.py::test_root_endpoint PASSED                             [  0%]
tests/test_api.py::test_health_endpoint_returns_200 PASSED               [  1%]
...
tests/test_multi_strategy_search.py::test_dynamic_router_heuristic_routing PASSED [ 85%]
tests/test_multi_strategy_search.py::test_dynamic_router_explicit_overrides PASSED [ 86%]
tests/test_multi_strategy_search.py::test_lexical_index_tokenization_and_formula_preservation PASSED [ 87%]
tests/test_multi_strategy_search.py::test_vekg_concept_and_correction_traversal PASSED [ 88%]
tests/test_multi_strategy_search.py::test_temporal_target_extraction PASSED [ 88%]
tests/test_multi_strategy_search.py::test_retriever_timestamp_proximity_boost PASSED [ 89%]
tests/test_multi_strategy_search.py::test_hybrid_index_graceful_bm25_fallback PASSED [ 90%]
tests/test_multi_strategy_search.py::test_source_isolation_in_retrieval_pipeline PASSED [ 90%]
tests/test_multi_strategy_search.py::test_api_multi_source_query PASSED  [ 91%]
tests/test_multi_strategy_search.py::test_api_virtual_endpoints_for_all_sources PASSED [ 92%]
...
tests/test_youtube_ingestion.py::test_startup_cleans_abandoned_processing_jobs PASSED [ 99%]
tests/test_youtube_ingestion.py::test_retry_endpoint_cleans_previous_records_and_requeues PASSED [100%]

================== 184 passed, 2 skipped, 1 warning in 11.35s ==================
```

---

### 2.2. Frontend Unit Tests
**Command:**
```bash
cd visionrag-x/frontend && npm test -- --run
```
**Output Summary:**
```
> visionrag-x-frontend@0.1.0 test
> node --test tests/**/*.test.cjs --run

▶ VisionRAG-X AI Chat Response & Confidence Presentation (7 tests) ✔
▶ ProcessingStatus Component Lifecycle & Recovery UI (5 tests) ✔
▶ Sidebar Sources Discoverability & Rendering (3 tests) ✔
▶ SourceDetail Multimodal Media Previews & Evidence Discovery (1 test) ✔
ℹ tests 16
ℹ suites 4
ℹ pass 16
ℹ fail 0
ℹ duration_ms 360.585917
```

---

### 2.3. Frontend Production Build
**Command:**
```bash
cd visionrag-x/frontend && npm run build
```
**Output Summary:**
```
> visionrag-x-frontend@0.1.0 build
> vite build

vite v5.4.21 building for production...
✓ 1591 modules transformed.
dist/index.html                   0.56 kB │ gzip:   0.35 kB
dist/assets/index-PqhL0gGH.css   52.31 kB │ gzip:   8.66 kB
dist/assets/index-Bo6KTcBN.js   393.28 kB │ gzip: 110.44 kB
✓ built in 1.67s
```

---

### 2.4. Live Real-Source Query Verification

The live query verification was executed against the real PostgreSQL database and local Ollama model (`llama3.2:3b`):

1. **Conceptual Query (Backtracking Video `d79fb75e`)**:
   - Query: *"What is the concept of backtracking and how does it work?"*
   - Strategy: `semantic_only` | Latency: 23.4s | Abstained: `False` | Confidence: 0.756
   - Result: Correctly answers using ASR timestamped evidence (01:45–02:00).
2. **Technical Formula Query (Sample Course PDF `6343a096`)**:
   - Query: *"What is the time complexity of merge sort O(n log n)?"*
   - Strategy: `lexical_only` | Latency: 12.4s | Abstained: `False` | Confidence: 0.733
   - Result: Correctly identifies Page 6 correction from $O(n^2)$ to $O(n \log n)$ with citation to errata.
3. **VEKG Concept Query (OSI Model Video `5fd05f6f`)**:
   - Query: *"Explain the 7 layers of the OSI model."*
   - Strategy: `knowledge_graph` | Latency: 13.5s | Abstained: `False` | Confidence: 0.812
   - Result: Retrieves layers from physical to application with exact timestamps (15:15–15:30).
4. **Timestamp-Aware Query (Backtracking Video `d79fb75e`)**:
   - Query: *"What is discussed at 01:30 in the video?"*
   - Strategy: `timestamp_aware` | Latency: 5.5s | Abstained: `False` | Confidence: 0.719
   - Result: Accurately identifies the speaker's comment on leaf nodes at 01:30–01:45.
5. **Unanswerable Query (Quantum entanglement in Backtracking video)**:
   - Query: *"What is quantum entanglement spin teleportation?"*
   - Strategy: `semantic_only` | Latency: 109 ms | Abstained: `True` | Confidence: 0.0
   - Result: Cleanly abstains without fabricating missing content.
6. **Global Multi-Source Query (`source_id='all'`)**:
   - Query: *"What algorithms and data structures are covered in the materials?"*
   - Strategy: `hybrid` | Latency: 7.7s | Abstained: `False` | Confidence: 0.814
   - Result: Synthesizes evidence across video and slide sources with distinct source titles.
