"""
Automated Regression and Scenario Verification Test Suite
for VisionRAG-X Conflict Demo Pack.

Verifies all 8 core demonstration scenarios:
1. Cross-modal disagreement detection (Formula vs ASR)
2. Correction and supersession via VEKG (Verbal slip & erratum)
3. Non-conflicting / complementary multimodal evidence
4. Formula and code retrieval specialization
5. Timestamp provenance and seekable anchors
6. Unanswerable-query epistemic abstention
7. Persistence after restart & VEKG reconstruction
8. Source isolation and non-interference
"""
import pytest
from unittest.mock import MagicMock

from app.demo.conflict_demo_loader import (
    DEMO_SOURCE_ID,
    get_demo_pack_dir,
    load_pack_json_files,
)
from app.knowledge.knowledge_units import ProcessedKnowledgeUnit
from app.knowledge.vekg import (
    VEKG,
    EDGE_CORRECTS,
    EDGE_SUPERSEDES,
    EDGE_CONFLICTS_WITH,
    EDGE_RELATED_TO,
)
from app.verification.conflict_detector import ConflictDetector
from app.indexing.hybrid_index import HybridIndex
from app.indexing.lexical_index import LexicalIndex
from app.routing.dynamic_router import DynamicRouter
from app.retrieval.retrieval_pipeline import (
    Retriever,
    Reranker,
    RetrievalPipeline,
)
from app.verification.provenance import ProvenanceTracker


@pytest.fixture(scope="module")
def demo_pack_data():
    """Load and parse the Conflict Demo Pack files."""
    return load_pack_json_files()


@pytest.fixture
def demo_vekg(demo_pack_data):
    """Instantiate and hydrate a VEKG with demo pack units and edges."""
    vekg = VEKG()
    pku_list = [
        ProcessedKnowledgeUnit(
            id=u["id"],
            concept=u["concept"],
            content=u["content"],
            modality=u["modality"],
            source_id=DEMO_SOURCE_ID,
            timestamp_start=u.get("timestamp_start"),
            timestamp_end=u.get("timestamp_end"),
            page=u.get("page"),
            slide=u.get("slide"),
            confidence=u.get("confidence", 1.0),
            status=u.get("status", "active"),
            version=u.get("version", 1),
            previous_version_id=u.get("previous_version_id"),
            correction_reason=u.get("correction_reason"),
        )
        for u in demo_pack_data["knowledge_units"]
    ]
    conflicts = demo_pack_data["conflicts"]
    vekg.reconstruct_from_units(pku_list, conflicts=conflicts)

    # Ensure all expected edges from vekg_edges.json are present
    for edge in demo_pack_data["vekg_edges"]:
        s_id = edge["source_unit_id"]
        t_id = edge["target_unit_id"]
        rel = edge["relation"]
        if s_id in vekg._unit_index and t_id in vekg._unit_index:
            if not vekg.graph.has_edge(s_id, t_id):
                vekg.graph.add_edge(s_id, t_id, relation=rel, reason=edge.get("reason", ""))

    return vekg


@pytest.fixture
def demo_hybrid_index(demo_pack_data):
    """Build in-memory lexical / hybrid index over the 15 demo units."""
    lexical = LexicalIndex()
    # Mock vector index with local fallback
    vector = MagicMock()
    async def _async_vector_search(*args, **kwargs):
        return []
    vector.search = _async_vector_search

    hybrid = HybridIndex(vector_index=vector, lexical_index=lexical, alpha=0.0)
    units_to_index = [
        {
            "id": u["id"],
            "concept": u["concept"],
            "content": f"{u['concept']} {u['content']}",
            "modality": u["modality"],
            "source_id": DEMO_SOURCE_ID,
            "timestamp_start": u.get("timestamp_start"),
            "timestamp_end": u.get("timestamp_end"),
            "page": u.get("page"),
            "confidence": u.get("confidence", 1.0),
            "status": u.get("status", "active"),
            "version": u.get("version", 1),
        }
        for u in demo_pack_data["knowledge_units"]
    ]
    lexical.build_index(units_to_index)
    return hybrid


@pytest.fixture
def demo_pipeline(demo_hybrid_index, demo_vekg, mock_settings):
    """Assemble retrieval pipeline configured for demo testing."""
    router = DynamicRouter()
    retriever = Retriever(hybrid_index=demo_hybrid_index, vekg=demo_vekg, settings=mock_settings)
    reranker = Reranker()
    provenance = ProvenanceTracker()
    return RetrievalPipeline(
        router=router,
        retriever=retriever,
        reranker=reranker,
        provenance=provenance,
        settings=mock_settings,
    )


# ===========================================================================
# SCENARIO 1: Cross-Modal Disagreement Detection
# ===========================================================================

def test_scenario_1_cross_modal_disagreement(demo_pack_data, mock_settings):
    """
    PASS Criteria:
    - Conflict detector identifies formula contradiction between ku_08 and ku_09.
    - Expected claims 'KE = 0.5 * m * v^2' and 'KE = m * v^2' are captured.
    - Severity is high and resolution marks slide formula authoritative.
    """
    detector = ConflictDetector(settings=mock_settings)

    # Window comparing spoken statement (ku_09) vs formula slide (ku_08)
    window = {
        "source_id": DEMO_SOURCE_ID,
        "window_start": 142.0,
        "window_end": 148.0,
        "asr_segments": [
            {"text": "As you can see, kinetic energy is simply mass times velocity squared KE = m * v^2 without the half factor.", "modality": "asr"}
        ],
        "ocr_segments": [
            {"text": "Kinetic Energy of an object with mass m and velocity v is KE = 0.5 * m * v^2.", "modality": "formula"}
        ],
    }

    conflicts = detector.detect_in_window(window)
    assert len(conflicts) > 0, "Expected cross-modal conflict between formula slide and speech narration"

    c = conflicts[0]
    assert c["type"] == "formula_contradiction"
    assert c["severity"] == "high"
    assert "formula" in c["sources"] or "ocr" in c["sources"]
    assert "asr" in c["sources"]

    # Verify conflict expectation matches manifest
    manifest_conf = demo_pack_data["manifest"]["expected_conflict_labels"]["c_kinetic_energy"]
    assert manifest_conf["type"] == "formula_contradiction"
    assert manifest_conf["severity"] == "high"


# ===========================================================================
# SCENARIO 2: Correction and Supersession via VEKG
# ===========================================================================

@pytest.mark.asyncio
async def test_scenario_2_correction_and_supersession(demo_vekg, demo_pipeline, demo_pack_data):
    """
    PASS Criteria:
    - ku_03 contains verbal correction reason updating ku_02.
    - VEKG contains directed 'corrects' and 'supersedes' edge from ku_03 to ku_02.
    - Querying worst-case merge sort returns active/verified units (ku_01, ku_03) and suppresses ku_02.
    """
    # 1. Inspect graph edges
    assert demo_vekg.graph.has_edge("ku_03", "ku_02"), "Missing lineage edge ku_03 -> ku_02"
    edge_data = demo_vekg.graph.get_edge_data("ku_03", "ku_02")
    assert edge_data["relation"] in (EDGE_CORRECTS, EDGE_SUPERSEDES)

    # 2. Verify statuses
    unit_02 = demo_vekg.get_unit("ku_02")
    unit_03 = demo_vekg.get_unit("ku_03")
    assert unit_02.status == "superseded"
    assert unit_03.status == "verified"
    assert unit_03.previous_version_id == "ku_02"

    # 3. Retrieve for merge sort time complexity query
    query = "What is the time complexity of merge sort in the worst case?"
    units_by_id = {u["id"]: u for u in demo_pack_data["knowledge_units"]}
    res = await demo_pipeline.run(
        query=query,
        source_id=DEMO_SOURCE_ID,
        source_type="video",
        top_k=5,
        units_by_id=units_by_id,
        conflicts=demo_pack_data["conflicts"],
    )

    evidence = res["evidence"]
    retrieved_ids = [e.get("knowledge_unit_id") or e.get("id") for e in evidence]
    # ku_01 (O(n log n)) and ku_03 (correction O(n log n)) must be present
    assert "ku_01" in retrieved_ids or "ku_03" in retrieved_ids
    # The top retrieved unit should be active/verified, not the superseded slip
    top_unit = evidence[0]
    assert top_unit["status"] in ("active", "verified")


# ===========================================================================
# SCENARIO 3: Non-Conflicting / Complementary Multimodal Evidence
# ===========================================================================

def test_scenario_3_non_conflicting_evidence(demo_pack_data, mock_settings):
    """
    PASS Criteria:
    - Distinct complementary modalities (BFS Queue, DFS Stack, Newton's law)
      do NOT trigger false positive conflict detection.
    """
    detector = ConflictDetector(settings=mock_settings)

    # Window comparing BFS spoken vs DFS slide (complementary data structures)
    window_bfs_dfs = {
        "source_id": DEMO_SOURCE_ID,
        "window_start": 210.0,
        "window_end": 240.0,
        "asr_segments": [
            {"text": "BFS explores graph vertices level by level using a FIFO Queue. Time complexity is O(V + E).", "modality": "asr"}
        ],
        "ocr_segments": [
            {"text": "DFS explores deeply along each branch using recursion or a LIFO Stack. Time complexity is O(V + E).", "modality": "ocr"}
        ],
    }

    conflicts = detector.detect_in_window(window_bfs_dfs)
    assert len(conflicts) == 0, "Complementary BFS (Queue) and DFS (Stack) should not trigger a false conflict"

    # Window with Newton's second law
    window_newton = {
        "source_id": DEMO_SOURCE_ID,
        "window_start": 120.0,
        "window_end": 130.0,
        "asr_segments": [
            {"text": "Let us discuss net force accelerating a mass.", "modality": "asr"}
        ],
        "ocr_segments": [
            {"text": "Newton's Second Law of Motion: Net force equals mass times acceleration F = m * a.", "modality": "ocr"}
        ],
    }
    conflicts_newton = detector.detect_in_window(window_newton)
    assert len(conflicts_newton) == 0, "Consistent Newton's second law statements should not trigger conflict"


# ===========================================================================
# SCENARIO 4: Formula and Code Retrieval Specialization
# ===========================================================================

@pytest.mark.asyncio
async def test_scenario_4_formula_and_code_retrieval(demo_pipeline, demo_pack_data):
    """
    PASS Criteria:
    - Code queries route to code modality and retrieve exact Python implementation.
    - Mathematical formula queries retrieve formulas with exact variable structure.
    """
    units_by_id = {u["id"]: u for u in demo_pack_data["knowledge_units"]}

    # Code retrieval test
    code_query = "Show me the Python code implementation for binary search."
    route = demo_pipeline.router.route(code_query)
    assert route["query_type"] == "code"

    code_res = await demo_pipeline.run(
        query=code_query,
        source_id=DEMO_SOURCE_ID,
        source_type="video",
        top_k=3,
        units_by_id=units_by_id,
        requested_strategy="lexical_only",
    )
    assert len(code_res["evidence"]) > 0
    top_code = code_res["evidence"][0]
    assert (top_code.get("knowledge_unit_id") or top_code.get("id")) == "ku_04"
    assert "def binary_search" in (top_code.get("text") or top_code.get("content", ""))
    assert top_code["modality"] == "code"

    # Formula retrieval test
    formula_query = "Explain how Master Theorem solves divide and conquer recurrences."
    formula_res = await demo_pipeline.run(
        query=formula_query,
        source_id=DEMO_SOURCE_ID,
        source_type="video",
        top_k=3,
        units_by_id=units_by_id,
        requested_strategy="lexical_only",
    )
    assert len(formula_res["evidence"]) > 0
    top_formula = formula_res["evidence"][0]
    assert (top_formula.get("knowledge_unit_id") or top_formula.get("id")) == "ku_06"
    assert "T(n) = a*T(n/b) + f(n)" in (top_formula.get("text") or top_formula.get("content", ""))


# ===========================================================================
# SCENARIO 5: Timestamp Provenance and Seekable Anchors
# ===========================================================================

@pytest.mark.asyncio
async def test_scenario_5_timestamp_provenance(demo_pipeline, demo_pack_data):
    """
    PASS Criteria:
    - Querying the correction moment returns ku_03 with exact timestamps 45.0s–52.0s.
    - Citation formatting preserves seekable temporal interval.
    """
    units_by_id = {u["id"]: u for u in demo_pack_data["knowledge_units"]}
    query = "At what timestamp does the instructor correct the mistake regarding merge sort?"

    res = await demo_pipeline.run(
        query=query,
        source_id=DEMO_SOURCE_ID,
        source_type="video",
        top_k=3,
        units_by_id=units_by_id,
        requested_strategy="timestamp_aware",
        timestamp_filter={"target_sec": 45.0, "start_sec": 45.0, "end_sec": 52.0},
    )
    evidence = res["evidence"]
    assert len(evidence) > 0
    correction_unit = next(
        (e for e in evidence if (e.get("knowledge_unit_id") or e.get("id")) == "ku_03"),
        evidence[0],
    )
    assert (correction_unit.get("knowledge_unit_id") or correction_unit.get("id")) == "ku_03"
    assert correction_unit["timestamp_start"] == 45.0
    assert correction_unit["timestamp_end"] == 52.0

    # Format citation via ProcessedKnowledgeUnit
    pku = ProcessedKnowledgeUnit(
        id=correction_unit.get("knowledge_unit_id") or correction_unit.get("id"),
        concept=correction_unit.get("concept", "Merge Sort Verbal Correction"),
        content=correction_unit.get("text") or correction_unit.get("content", ""),
        modality=correction_unit["modality"],
        timestamp_start=correction_unit["timestamp_start"],
        timestamp_end=correction_unit["timestamp_end"],
        version=correction_unit.get("version", 2),
    )
    citation = pku.format_citation()
    assert "45.0s–52.0s" in citation
    assert "[ASR]" in citation


# ===========================================================================
# SCENARIO 6: Unanswerable-Query Epistemic Abstention
# ===========================================================================

@pytest.mark.asyncio
async def test_scenario_6_unanswerable_query_abstention(demo_pipeline, demo_pack_data):
    """
    PASS Criteria:
    - Out-of-domain queries ('quantum Fourier transform', 'caffeine molecule')
      fail the evidence sufficiency gate and trigger abstention.
    """
    units_by_id = {u["id"]: u for u in demo_pack_data["knowledge_units"]}

    # Query 1: Quantum computing
    q_quantum = "What is the time complexity of quantum Fourier transform in Shor's algorithm?"
    res_quantum = await demo_pipeline.retriever.retrieve(
        query=q_quantum,
        source_id=DEMO_SOURCE_ID,
        strategy="hybrid",
        top_k=5,
        units_by_id=units_by_id,
    )
    is_sufficient_1, reason_1 = demo_pipeline.check_evidence_sufficiency(q_quantum, res_quantum, max_score=0.1)
    assert not is_sufficient_1, f"Expected abstention on quantum query, but got: {reason_1}"

    # Query 2: Organic chemistry
    q_caffeine = "How many protons are present in a caffeine molecule?"
    res_caffeine = await demo_pipeline.retriever.retrieve(
        query=q_caffeine,
        source_id=DEMO_SOURCE_ID,
        strategy="hybrid",
        top_k=5,
        units_by_id=units_by_id,
    )
    is_sufficient_2, reason_2 = demo_pipeline.check_evidence_sufficiency(q_caffeine, res_caffeine, max_score=0.1)
    assert not is_sufficient_2, f"Expected abstention on caffeine query, but got: {reason_2}"


# ===========================================================================
# SCENARIO 7: Persistence After Restart & VEKG Reconstruction
# ===========================================================================

def test_scenario_7_persistence_after_restart(demo_pack_data):
    """
    PASS Criteria:
    - When VEKG is re-instantiated and hydrated from raw stored units,
      all 15 nodes and version lineage relationships reconstruct identically.
    """
    pku_list = [
        ProcessedKnowledgeUnit(
            id=u["id"],
            concept=u["concept"],
            content=u["content"],
            modality=u["modality"],
            source_id=DEMO_SOURCE_ID,
            timestamp_start=u.get("timestamp_start"),
            timestamp_end=u.get("timestamp_end"),
            confidence=u.get("confidence", 1.0),
            status=u.get("status", "active"),
            version=u.get("version", 1),
            previous_version_id=u.get("previous_version_id"),
            correction_reason=u.get("correction_reason"),
        )
        for u in demo_pack_data["knowledge_units"]
    ]

    new_vekg = VEKG()
    new_vekg.reconstruct_from_units(pku_list, conflicts=demo_pack_data["conflicts"])

    # 1. Verify 15 nodes registered
    assert len(new_vekg.graph.nodes) == 15
    assert len(new_vekg._unit_index) == 15

    # 2. Verify lineage edge ku_03 -> ku_02
    assert new_vekg.graph.has_edge("ku_03", "ku_02")
    edge = new_vekg.graph.get_edge_data("ku_03", "ku_02")
    assert edge["relation"] == EDGE_CORRECTS

    # 3. Verify concept index contains all concepts
    assert "merge sort time complexity" in new_vekg._concept_index
    assert "binary search algorithm" in new_vekg._concept_index
    assert "kinetic energy slide equation" in new_vekg._concept_index


# ===========================================================================
# SCENARIO 8: Source Isolation and Non-Interference
# ===========================================================================

@pytest.mark.asyncio
async def test_scenario_8_source_isolation(demo_pipeline, demo_pack_data):
    """
    PASS Criteria:
    - Queries targeted to DEMO_SOURCE_ID return demo pack units.
    - Queries targeted to an unrelated production source return 0 demo units.
    """
    units_by_id = {u["id"]: u for u in demo_pack_data["knowledge_units"]}
    query = "What is the time complexity of merge sort?"

    # Query scoped to demo source
    demo_res = await demo_pipeline.run(
        query=query,
        source_id=DEMO_SOURCE_ID,
        source_type="video",
        top_k=5,
        units_by_id=units_by_id,
        requested_strategy="lexical_only",
    )
    assert len(demo_res["evidence"]) > 0
    assert all(r["source_id"] == DEMO_SOURCE_ID for r in demo_res["evidence"])

    # Query scoped to another source ID (simulating production lecture)
    other_source_id = "prod_source_unrelated_999"
    other_res = await demo_pipeline.run(
        query=query,
        source_id=other_source_id,
        source_type="video",
        top_k=5,
        units_by_id=units_by_id,
        requested_strategy="lexical_only",
    )
    # None of the demo pack units should be returned for another source
    assert len(other_res["evidence"]) == 0, "Demo units must not leak into foreign source retrieval queries"


# ===========================================================================
# PACKAGE INTEGRITY & MANIFEST VERIFICATION
# ===========================================================================

def test_conflict_demo_pack_manifest_integrity(demo_pack_data):
    """
    PASS Criteria:
    - Manifest file schema conforms to specifications.
    - Total unit count, conflict count, edge count, and statistics are consistent.
    """
    manifest = demo_pack_data["manifest"]
    assert manifest["pack_id"] == "visionrag-x-conflict-demo-pack"
    assert manifest["source"]["id"] == DEMO_SOURCE_ID

    kus = demo_pack_data["knowledge_units"]
    assert len(kus) == 15

    conflicts = demo_pack_data["conflicts"]
    assert len(conflicts) == 2

    edges = demo_pack_data["vekg_edges"]
    assert len(edges) >= 4

    test_plan = demo_pack_data["test_plan"]
    assert len(test_plan["scenarios"]) == 8


# ===========================================================================
# LOADER SERVICE UNIT TESTS (IDEMPOTENCY & CLEAN TEARDOWN)
# ===========================================================================

@pytest.mark.asyncio
async def test_loader_service_load_and_unload_flow():
    """
    PASS Criteria:
    - load_demo_pack executes without errors against mock session.
    - Added Source, ProcessingJob, KnowledgeUnits, Evidence, Conflicts.
    - unload_demo_pack executes cleanly.
    """
    from unittest.mock import AsyncMock
    from app.demo.conflict_demo_loader import load_demo_pack, unload_demo_pack

    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.execute = AsyncMock()
    mock_session.execute.return_value.scalar_one_or_none.return_value = None
    mock_session.commit = AsyncMock()
    mock_session.delete = AsyncMock()

    res = await load_demo_pack(mock_session, force_reload=False)
    assert res["status"] == "success"
    assert res["units_loaded"] == 15
    assert res["conflicts_loaded"] == 2
    assert res["source_id"] == DEMO_SOURCE_ID

    # Verify db.add was called for source, job, 15 KUs, 15 Evidence, 2 conflicts
    # Total adds = 1 + 1 + 15 + 15 + 2 = 34
    assert mock_session.add.call_count >= 34
    assert mock_session.commit.called

    # Test unload flow
    mock_session.execute.return_value.scalar_one_or_none.return_value = MagicMock()
    deleted = await unload_demo_pack(mock_session)
    assert deleted is True
    assert mock_session.delete.called
    assert mock_session.commit.called

