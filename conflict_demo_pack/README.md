# VisionRAG-X Conflict Demo Pack

> **System**: VisionRAG-X: A Conflict-Aware Framework for Verified Multimodal Knowledge Retrieval from Educational Videos  
> **Package**: Conflict Demo Pack (Synthetic Fixtures & Scenarios)  
> **Version**: 1.0.0  
> **Source Scope ID**: `demo_conflict_source_001`  
> **Status**: Verified & Integrated  

---

## 1. Overview & Purpose

The **VisionRAG-X Conflict Demo Pack** provides a controlled, deterministic multimodal knowledge fixture designed to rigorously evaluate and demonstrate the five core research contributions of the VisionRAG-X framework:
1. **Multimodal Knowledge Units (KUs)** extracted from speech (ASR), slides (OCR), formulas, code, and visual figures.
2. **Deterministic Cross-Modal Conflict Detection** between spoken narration and on-screen visuals.
3. **Verified Knowledge Evolution Graph (VEKG)** lineage resolution of instructor speech slips corrected later in time.
4. **Multi-Strategy Dynamic Query Routing** targeting code, mathematical formulas, conceptual explanations, and temporal lookups.
5. **Grounded Sufficiency Gating** for polite epistemic abstention on unanswerable out-of-domain queries.

This demo pack runs under a dedicated, isolated scope (`demo_conflict_source_001`), completely separated from real production sources, ensuring zero data leakage and repeatable cleanup.

---

## 2. Pack File Structure & Manifest

```
conflict_demo_pack/
├── manifest.json            # Master package manifest with metadata, statistics, and mappings
├── knowledge_units.json     # 15 multimodal Knowledge Units (ku_01 to ku_15)
├── conflicts.json           # Ground-truth cross-modal conflict annotations
├── vekg_edges.json          # Expected VEKG lineage, conflict, and conceptual relationship edges
├── demo_test_plan.json      # Structured specifications for the 8 core demo scenarios
└── README.md                # This comprehensive documentation and execution guide
```

---

## 3. Schema Mapping & Persistence Layer

The synthetic entities map 1:1 onto the VisionRAG-X SQLAlchemy database models and vector/lexical indexes:

| Demo Pack Entity | Target Application Model | Description |
|---|---|---|
| `manifest.source` | `Source` (`models.Source`) | Scoped container with `id="demo_conflict_source_001"`, title, and type `"video"`. |
| `knowledge_units.json` | `KnowledgeUnit` (`models.KnowledgeUnit`) | 15 versioned atoms with `concept`, `content`, `modality`, timestamps, `confidence`, `status`, `version`, `previous_version_id`. |
| `knowledge_units.json` | `Evidence` (`models.Evidence`) | Raw backing text segment records linked via `knowledge_unit_id`. |
| `conflicts.json` | `Conflict` (`models.Conflict`) | Identified contradictions (`conflict_type`, `modalities`, `claims`, `severity`, `resolved`, `resolution`). |
| `vekg_edges.json` | `VEKG` (`app.knowledge.vekg.VEKG`) | In-memory Directed Multigraph edges (`corrects`, `supersedes`, `conflicts_with`, `related_to`). |
| Search Indexes | `HybridIndex` (`VectorIndex` + `LexicalIndex`) | Dense vectors (BGE) + Lexical inverted index (BM25) with exact formula preservation. |

---

## 4. Expected Conflict Labels & VEKG Edge Expectations

### 4.1. Ground-Truth Conflict Labels

#### Conflict 1: `c_merge_sort` (Complexity Disagreement)
- **Concept**: Merge Sort Time Complexity
- **Participating Units**: `ku_01` (Slide OCR), `ku_02` (Initial Speech Slip), `ku_03` (Verbal Erratum)
- **Modalities**: `["asr", "ocr"]`
- **Claims**:
  - `ASR`: `"O(n^2) [asr]"` (verbal slip at 10.0s–14.0s)
  - `OCR`: `"O(n log n) [ocr]"` (slide text at 12.0s–18.0s)
- **Severity**: `high` (algorithmic complexity disagreement)
- **Resolution**: `Resolved` — Instructor explicitly issued a verbal correction at 45.0s (`ku_03`), confirming $O(n \log n)$.

#### Conflict 2: `c_kinetic_energy` (Formula Contradiction)
- **Concept**: Kinetic Energy Formula
- **Participating Units**: `ku_08` (Formula Slide), `ku_09` (Spoken Narration)
- **Modalities**: `["formula", "asr"]`
- **Claims**:
  - `Formula`: `"KE = 0.5 * m * v^2 [formula]"`
  - `ASR`: `"KE = m * v^2 [asr]"` (omits $\frac{1}{2}$ factor)
- **Severity**: `high` (governing physical equation contradiction)
- **Resolution**: `Resolved` — Slide formula is authoritative; spoken omission of the 0.5 factor is a verbal error.

### 4.2. VEKG Edge Expectations

| Edge ID | Source Node | Target Node | Relation Type | Expected Behavior |
|---|---|---|---|---|
| `edge_corr_merge_sort` | `ku_03` | `ku_02` | `corrects` | Lineage edge indicating version 2 corrects version 1 slip. |
| `edge_super_merge_sort` | `ku_03` | `ku_02` | `supersedes` | Traversal suppresses `ku_02` and promotes `ku_03` as active answer. |
| `edge_conf_kinetic` | `ku_08` | `ku_09` | `conflicts_with` | Bidirectional conflict edge alerting chat UI to contradictory claims. |
| `edge_conf_merge` | `ku_01` | `ku_02` | `conflicts_with` | Cross-modal clash between slide text and uncorrected speech. |
| `edge_rel_binsearch` | `ku_04` | `ku_05` | `related_to` | Semantic link connecting algorithm code to complexity derivation. |
| `edge_rel_grad_desc` | `ku_10` | `ku_11` | `related_to` | Visual optimization diagram linked to mathematical update rule. |
| `edge_rel_graph` | `ku_12` | `ku_13` | `related_to` | Duality between Queue-based BFS and Stack-based DFS. |

---

## 5. Eight Core Demonstration Scenarios

### Scenario 1: Cross-Modal Disagreement Detection
- **Query**: *"What is the formula for kinetic energy of a moving object?"*
- **Tested Mechanism**: `ConflictDetector.detect_all()` & `filter_relevant_conflicts()`.
- **Expected Outcome**:
  - System identifies `c_kinetic_energy`.
  - Chat response flags contradiction between slide ($0.5mv^2$) and narration ($mv^2$).
  - Slide equation is verified as authoritative.

### Scenario 2: Correction and Supersession via VEKG
- **Query**: *"What is the time complexity of merge sort in the worst case?"*
- **Tested Mechanism**: VEKG lineage resolution and active status filtering.
- **Expected Outcome**:
  - `ku_02` ($O(n^2)$) is marked `superseded` and suppressed from primary answer generation.
  - Active verified unit `ku_03` ($O(n \log n)$) is retrieved.
  - Answer reports $O(n \log n)$ citing timestamp 45.0s–52.0s without adopting the slip.

### Scenario 3: Non-Conflicting / Complementary Multimodal Evidence
- **Queries**:
  - *"Which data structure is used by Breadth First Search?"* $\rightarrow$ Queue (`ku_12`, ASR)
  - *"What data structure does Depth First Search utilize?"* $\rightarrow$ Stack (`ku_13`, OCR)
  - *"What is Newton's Second Law of Motion formula?"* $\rightarrow$ $F = ma$ (`ku_07`, OCR)
- **Tested Mechanism**: Conflict avoidance on complementary multi-source knowledge.
- **Expected Outcome**: Zero false-positive conflict alarms; clean retrieval and generation.

### Scenario 4: Formula & Code Retrieval Specialization
- **Queries**:
  - *"Show me the Python code implementation for binary search."*
  - *"What is the parameter update equation in gradient descent?"*
- **Tested Mechanism**: BM25 exact symbol retention (`arr`, `low`, `high`, $\theta$, $\alpha$).
- **Expected Outcome**:
  - Code snippet in `ku_04` returned intact with indentation and syntax.
  - Parameter update $\theta := \theta - \alpha \nabla J(\theta)$ retrieved cleanly without math tokenization degradation.

### Scenario 5: Timestamp Provenance & Seekable Anchors
- **Query**: *"At what timestamp does the instructor correct the mistake regarding merge sort?"*
- **Tested Mechanism**: Timestamp alignment and provenance interval tracking.
- **Expected Outcome**:
  - Citation anchored to `[ASR] 45.0s–52.0s`.
  - Chat UI renders clickable seekable timestamp link jumping to 45.0s.

### Scenario 6: Unanswerable-Query Epistemic Abstention
- **Queries**:
  - *"What is the time complexity of quantum Fourier transform in Shor's algorithm?"*
  - *"How many protons are present in a caffeine molecule?"*
- **Tested Mechanism**: Evidence Sufficiency Gate (`check_evidence_sufficiency()`).
- **Expected Outcome**:
  - Zero keyword / semantic topic match in lecture knowledge units.
  - System returns `abstained: true` with refusal: *"The provided educational material does not contain information about..."*

### Scenario 7: Persistence After Service Restart
- **Tested Mechanism**: DB persistence and in-memory VEKG graph hydration (`vekg.reconstruct_from_units()`).
- **Expected Outcome**:
  - Full restoration of 15 nodes, version pointers, and graph relations from PostgreSQL upon reload.

### Scenario 8: Source Isolation & Non-Interference
- **Tested Mechanism**: Source-scoped retrieval routing.
- **Expected Outcome**:
  - Queries with `source_id="demo_conflict_source_001"` retrieve ONLY demo units.
  - Production user sources (`source_id != demo_conflict_source_001`) retrieve ZERO demo units.

---

## 6. Fixture Loader & CLI Usage

VisionRAG-X includes an automated fixture loader (`app.demo.conflict_demo_loader`).

### 6.1. Load Fixtures into Database & Index
```bash
cd visionrag-x/backend
source .venv/bin/activate
python -m app.demo.conflict_demo_loader --load
```
*Output:*
```
[INFO] Source 'demo_conflict_source_001' loaded successfully.
[INFO] 15 Knowledge Units and 15 Evidence items persisted.
[INFO] 2 Conflicts persisted.
[INFO] In-memory VEKG reconstructed with 15 nodes and 7 edges.
[INFO] Demo pack is ready for demonstration.
```

### 6.2. Verify Current Status
```bash
python -m app.demo.conflict_demo_loader --status
```

### 6.3. Clean Teardown / Unload
```bash
python -m app.demo.conflict_demo_loader --unload
```
*Output:*
```
[INFO] Cleaned up all records for demo_conflict_source_001. Production sources untouched.
```

---

## 7. Running Automated Regression Tests

The automated test suite verifies all 8 scenarios deterministically:

```bash
cd visionrag-x/backend
source .venv/bin/activate
pytest tests/test_conflict_demo_pack.py -v
```

All 8 scenarios must report **`PASS`**.
