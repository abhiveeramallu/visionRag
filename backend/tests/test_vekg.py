"""
Tests for the VEKG (Verified Knowledge Evolution Graph).
"""
import pytest
from app.knowledge.vekg import VEKG, EDGE_CONFLICTS_WITH, EDGE_CORRECTS


def make_unit(uid, concept='Merge Sort', content='Content', modality='asr',
              source_id='src-1', confidence=0.8, status='active'):
    """Create a minimal ProcessedKnowledgeUnit-like object."""
    from app.knowledge.knowledge_units import ProcessedKnowledgeUnit
    return ProcessedKnowledgeUnit(
        id=uid, concept=concept, content=content, modality=modality,
        source_id=source_id, timestamp_start=0.0, timestamp_end=15.0,
        page=None, slide=None, confidence=confidence, evidence=[],
        status=status, version=1, previous_version_id=None,
        correction_reason=None, embedding=None, embedding_id=None,
    )


@pytest.fixture
def vekg():
    return VEKG()


def test_add_unit(vekg):
    """Unit should be added and retrievable."""
    unit = make_unit('u1')
    vekg.add_unit(unit)
    assert len(vekg) == 1
    assert 'u1' in vekg


def test_get_active_units(vekg):
    """get_active_units should return only active and verified units."""
    vekg.add_unit(make_unit('u1', status='active'))
    vekg.add_unit(make_unit('u2', status='superseded'))
    vekg.add_unit(make_unit('u3', status='verified'))
    active = vekg.get_active_units()
    ids = {u.id for u in active}
    assert 'u1' in ids
    assert 'u3' in ids
    assert 'u2' not in ids


def test_update_marks_superseded(vekg):
    """Updating a unit should mark the old one as superseded."""
    old = make_unit('u1', content='Wrong content')
    vekg.add_unit(old)
    new = make_unit('u2', content='Correct content')
    vekg.update_unit('u1', new, reason='Formula corrected at 14:32')
    assert vekg._unit_index['u1'].status == 'superseded'
    assert vekg._unit_index['u2'].version == 2
    assert vekg._unit_index['u2'].previous_version_id == 'u1'


def test_get_lineage(vekg):
    """get_lineage should return version chain from newest to oldest."""
    u1 = make_unit('u1', content='v1')
    vekg.add_unit(u1)
    u2 = make_unit('u2', content='v2')
    vekg.update_unit('u1', u2, 'corrected')
    lineage = vekg.get_lineage('u2')
    assert lineage[0].id == 'u2'
    assert lineage[1].id == 'u1'


def test_conflict_marks_disputed(vekg):
    """Adding a conflict edge should mark both units as disputed."""
    vekg.add_unit(make_unit('u1'))
    vekg.add_unit(make_unit('u2'))
    vekg.add_conflict('u1', 'u2', {'type': 'complexity_disagreement'})
    assert vekg._unit_index['u1'].status == 'disputed'
    assert vekg._unit_index['u2'].status == 'disputed'


def test_stats(vekg):
    """stats() should return correct counts."""
    vekg.add_unit(make_unit('u1', status='active'))
    vekg.add_unit(make_unit('u2', status='verified'))
    vekg.add_unit(make_unit('u3', status='active'))
    stats = vekg.stats()
    assert stats['total_units'] == 3
    assert stats['active'] == 2
    assert stats['verified'] == 1


def test_search_by_concept(vekg):
    """search_by_concept should find fuzzy concept matches."""
    vekg.add_unit(make_unit('u1', concept='Newton-Raphson Method'))
    vekg.add_unit(make_unit('u2', concept='Binary Search'))
    results = vekg.search_by_concept('Newton')
    ids = [u.id for u in results]
    assert 'u1' in ids


def test_mark_verified(vekg):
    """mark_verified should set status to verified."""
    vekg.add_unit(make_unit('u1', status='active'))
    vekg.mark_verified('u1')
    assert vekg._unit_index['u1'].status == 'verified'


def test_to_dict(vekg):
    """to_dict should return nodes, edges, stats."""
    vekg.add_unit(make_unit('u1'))
    d = vekg.to_dict()
    assert 'nodes' in d
    assert 'edges' in d
    assert 'stats' in d
    assert len(d['nodes']) == 1


def test_get_conflicting_units(vekg):
    """get_conflicting_units should return pairs of disputed units."""
    vekg.add_unit(make_unit('u1'))
    vekg.add_unit(make_unit('u2'))
    vekg.add_conflict('u1', 'u2', {})
    pairs = vekg.get_conflicting_units()
    assert len(pairs) == 1


def test_update_missing_unit_raises(vekg):
    """Updating a non-existent unit should raise ValueError."""
    with pytest.raises(ValueError):
        vekg.update_unit('nonexistent', make_unit('u_new'), 'reason')
