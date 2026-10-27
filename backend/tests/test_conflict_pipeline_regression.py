"""
Regression tests for VisionRAG-X Conflict Detection, VEKG Integration, and API truthful reporting.
"""
import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock

from app.verification.conflict_detector import ConflictDetector
from app.knowledge.vekg import VEKG, EDGE_CORRECTS, EDGE_CONFLICTS_WITH, EDGE_RELATED_TO
from app.knowledge.knowledge_units import ProcessedKnowledgeUnit
from app.knowledge.models import Conflict, KnowledgeUnit, Source, Evidence
from app.api.query import get_knowledge_graph, get_all_conflicts


@pytest.fixture
def detector(mock_settings):
    return ConflictDetector(mock_settings)


def test_unbalanced_bst_contradiction_detected(detector):
    """
    Contradictory pair:
    Speech claims unbalanced BST worst-case search is O(log n).
    Slide claims worst-case search in an unbalanced BST is O(n).
    Both share the same data structure and case ('unbalanced BST worst-case search'),
    so the Big-O disagreement (O(log n) vs O(n)) is a genuine contradiction.
    """
    text_speech = "An unbalanced BST has worst-case search complexity O(log n)."
    text_slide = "Worst-case search in an unbalanced BST is O(n)."
    
    conflict = detector.detect_between_claims(
        text_a=text_speech,
        text_b=text_slide,
        modality_a="asr",
        modality_b="ocr",
    )
    assert conflict is not None
    assert conflict["type"] == "complexity_disagreement"
    assert conflict["resolved"] is True
    assert "linear chain" in conflict["resolution"].lower() or "unbalanced bst" in conflict["resolution"].lower()
    assert "O(logn) [asr]" in conflict["claims"]
    assert "O(n) [ocr]" in conflict["claims"]


def test_compatible_bst_statements_not_flagged(detector):
    """
    Compatible statements describing different data structures or different scopes:
    1. Balanced BST height O(log n) vs Balanced BST search O(log n) -> same complexity, not flagged.
    2. Balanced BST search O(log n) vs Unbalanced BST search O(n) -> differing structure assumptions (balanced vs unbalanced), not flagged.
    """
    # 1. Compatible properties with same Big-O
    s1 = "A balanced BST has height O(log n)."
    s2 = "Search in a balanced BST is O(log n)."
    assert detector.detect_between_claims(s1, s2, "asr", "ocr") is None

    # 2. Differing structure assumptions (balanced vs unbalanced)
    s_balanced = "A balanced BST supports search in O(log n)."
    s_unbalanced = "An unbalanced BST has worst-case search complexity O(n)."
    assert detector.detect_between_claims(s_balanced, s_unbalanced, "asr", "ocr") is None

    # 3. Differing cases (worst-case vs average-case)
    s_avg = "Quick sort average case complexity is O(n log n)."
    s_worst = "Quick sort worst case complexity is O(n^2)."
    assert detector.detect_between_claims(s_avg, s_worst, "asr", "ocr") is None


def test_correction_produces_appropriate_lineage():
    """
    Verified corrections produce EDGE_CORRECTS and update node statuses in VEKG.
    """
    vekg = VEKG()
    u_old = ProcessedKnowledgeUnit(
        id="ku_draft",
        concept="Merge Sort Complexity",
        content="Merge sort has time complexity O(n^2) in draft slides.",
        modality="text",
        source_id="src_1",
        version=1,
        status="active",
    )
    u_new = ProcessedKnowledgeUnit(
        id="ku_errata",
        concept="Merge Sort Complexity",
        content="Errata correction: Merge sort time complexity is strictly O(n log n).",
        modality="text",
        source_id="src_1",
        version=2,
        status="verified",
        previous_version_id="ku_draft",
        correction_reason="Verbal errata correcting draft slide notation error.",
    )

    vekg.reconstruct_from_units([u_old, u_new], conflicts=[])
    
    # Check that old unit is superseded
    assert vekg.graph.nodes["ku_draft"]["status"] == "superseded"
    assert vekg.graph.nodes["ku_errata"]["status"] == "verified"
    
    # Check directed corrects edge from new to old
    assert vekg.graph.has_edge("ku_errata", "ku_draft")
    edge_data = vekg.graph.edges["ku_errata", "ku_draft"]
    assert edge_data["relation"] == EDGE_CORRECTS
    assert "Verbal errata" in edge_data["reason"]


def test_intra_unit_and_inter_unit_conflict_vekg_reconstruction():
    """
    VEKG reconstructs both inter-unit conflicts (between 2 distinct units)
    and intra-unit conflicts (cross-modal disagreement within a single unit's page/timestamp).
    """
    vekg = VEKG()
    u1 = ProcessedKnowledgeUnit(
        id="ku_1",
        concept="Slide 1 Topic",
        content="Content on page 1",
        modality="ocr",
        source_id="src_1",
        page=1,
        status="active",
    )
    u2 = ProcessedKnowledgeUnit(
        id="ku_2",
        concept="Slide 2 Speech",
        content="Speech on page 2",
        modality="asr",
        source_id="src_1",
        page=2,
        status="active",
    )
    u3 = ProcessedKnowledgeUnit(
        id="ku_3",
        concept="Slide 2 Visual",
        content="Visual text on page 2",
        modality="ocr",
        source_id="src_1",
        page=2,
        status="active",
    )

    # Conflict A: intra-unit on page 1 (only ku_1 on page 1)
    # Conflict B: inter-unit on page 2 (ku_2 and ku_3 on page 2)
    conflicts = [
        {
            "id": "conf_intra",
            "conflict_type": "numeric_disagreement",
            "page": 1,
            "claims": ["text: 10", "ocr: 3"],
            "severity": "medium",
            "resolved": False,
        },
        {
            "id": "conf_inter",
            "conflict_type": "complexity_disagreement",
            "page": 2,
            "claims": ["O(n log n)", "O(n^2)"],
            "severity": "high",
            "resolved": False,
        },
    ]

    vekg.reconstruct_from_units([u1, u2, u3], conflicts=conflicts)

    # Inter-unit conflict creates edge between ku_2 and ku_3
    assert vekg.graph.has_edge("ku_2", "ku_3")
    assert vekg.graph.edges["ku_2", "ku_3"]["relation"] == EDGE_CONFLICTS_WITH
    assert vekg.graph.nodes["ku_2"]["status"] == "disputed"
    assert vekg.graph.nodes["ku_3"]["status"] == "disputed"

    # Intra-unit conflict marks ku_1 as disputed and adds self-loop edge
    assert vekg.graph.nodes["ku_1"]["status"] == "disputed"
    assert vekg.graph.has_edge("ku_1", "ku_1")
    assert vekg.graph.edges["ku_1", "ku_1"]["relation"] == EDGE_CONFLICTS_WITH


@pytest.mark.asyncio
async def test_get_knowledge_graph_truthful_summary_and_edges():
    """
    Test that get_knowledge_graph returns truthful counts:
    - Exactly distinguishes lineage_edges, conflict_edges, and related_edges
    - Does not drop intra-unit or inter-unit conflicts
    - Includes source_label and target_label on all edges
    """
    mock_db = AsyncMock()

    source = Source(id="src_test", title="Test Course", status="completed")
    
    ku_1 = KnowledgeUnit(
        id="ku_1",
        concept="BST Search",
        content="Search in BST is O(n)",
        modality="ocr",
        source_id="src_test",
        page=1,
        status="disputed",
        version=1,
    )
    ku_2 = KnowledgeUnit(
        id="ku_2",
        concept="BST Search",
        content="Errata: Balanced BST is O(log n)",
        modality="text",
        source_id="src_test",
        page=2,
        status="verified",
        version=2,
        previous_version_id="ku_1",
        correction_reason="Errata correction",
    )

    conflict = Conflict(
        id="c_1",
        source_id="src_test",
        conflict_type="numeric_disagreement",
        modalities=["text", "ocr"],
        claims=["text: 5", "ocr: 10"],
        page=1,
        severity="medium",
        confidence=0.8,
        resolved=False,
    )

    # Mock DB executions
    async def mock_execute(stmt):
        mock_result = MagicMock()
        stmt_str = str(stmt)
        if "FROM sources" in stmt_str:
            mock_result.scalars.return_value.all.return_value = [source]
        elif "FROM knowledge_units" in stmt_str:
            mock_result.scalars.return_value.all.return_value = [ku_1, ku_2]
        elif "FROM conflicts" in stmt_str:
            mock_result.scalars.return_value.all.return_value = [conflict]
        elif "FROM evidence" in stmt_str:
            mock_result.all.return_value = [("ku_1", 1), ("ku_2", 1)]
        else:
            mock_result.scalars.return_value.all.return_value = []
        return mock_result

    mock_db.execute = mock_execute

    graph = await get_knowledge_graph("src_test", mock_db)
    summary = graph["summary"]

    assert summary["total_nodes"] == 2
    assert summary["lineage_edges"] == 1
    assert summary["correction_edges"] == 1
    assert summary["conflict_edges"] == 1
    assert summary["conflicts_count"] == 1

    # Check that edges have labels
    for e in graph["edges"]:
        assert "source_label" in e
        assert "target_label" in e
        assert e["source_label"] is not None
        assert e["target_label"] is not None


@pytest.mark.asyncio
async def test_get_all_conflicts_endpoint():
    """
    Test that get_all_conflicts returns structured conflict items.
    """
    mock_db = AsyncMock()
    c = Conflict(
        id="c_demo",
        source_id="src_1",
        conflict_type="complexity_disagreement",
        modalities=["asr", "ocr"],
        claims=["O(n log n)", "O(n^2)"],
        page=2,
        severity="high",
        confidence=0.9,
        resolved=True,
        resolution="Verified errata on page 6",
    )
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [c]
    mock_db.execute.return_value = mock_result

    res = await get_all_conflicts(source_id=None, db=mock_db)
    assert len(res) == 1
    assert res[0]["id"] == "c_demo"
    assert res[0]["conflict_type"] == "complexity_disagreement"
    assert res[0]["resolved"] is True
    assert res[0]["resolution"] == "Verified errata on page 6"
