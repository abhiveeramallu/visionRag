"""
Verified Knowledge Evolution Graph (VEKG).

EXPERIMENTAL: This graph structure and update mechanisms are research
prototypes that have not been formally evaluated.

Nodes represent KnowledgeUnits. Edges represent relationships:
- corrects       : newer version corrects an error in an older version
- supersedes     : newer version replaces an older version
- supports       : two units provide mutually supporting evidence
- conflicts_with : two units disagree (cross-modal conflict)
- related_to     : semantic relatedness (not directional in meaning)
"""
import logging
import uuid
from difflib import SequenceMatcher
from typing import Dict, List, Optional, Tuple

import networkx as nx

from app.knowledge.knowledge_units import ProcessedKnowledgeUnit

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Edge-type constants
# ---------------------------------------------------------------------------

EDGE_CORRECTS = "corrects"
EDGE_SUPERSEDES = "supersedes"
EDGE_SUPPORTS = "supports"
EDGE_CONFLICTS_WITH = "conflicts_with"
EDGE_RELATED_TO = "related_to"


# ---------------------------------------------------------------------------
# VEKG
# ---------------------------------------------------------------------------

class VEKG:
    """
    In-memory graph of knowledge units and their relationships.

    The graph is held in RAM and is rebuilt from the database on startup.
    It is NOT persisted directly – use the database layer for durability.
    """

    def __init__(self) -> None:
        self.graph: nx.DiGraph = nx.DiGraph()
        # Primary look-up: unit_id -> ProcessedKnowledgeUnit
        self._unit_index: Dict[str, ProcessedKnowledgeUnit] = {}
        # Secondary index: concept_key -> [unit_ids]   (case-folded)
        self._concept_index: Dict[str, List[str]] = {}

    # ------------------------------------------------------------------
    # Node operations
    # ------------------------------------------------------------------

    def add_unit(self, unit: ProcessedKnowledgeUnit) -> None:
        """Add a new unit to the graph. Silently overwrites if id already exists."""
        self._unit_index[unit.id] = unit
        self.graph.add_node(
            unit.id,
            concept=unit.concept,
            modality=unit.modality,
            confidence=unit.confidence,
            status=unit.status,
            version=unit.version,
            source_id=unit.source_id,
        )

        concept_key = unit.concept.lower().strip()
        self._concept_index.setdefault(concept_key, [])
        if unit.id not in self._concept_index[concept_key]:
            self._concept_index[concept_key].append(unit.id)

        logger.debug("Added unit %s (concept=%r modality=%s)", unit.id, unit.concept, unit.modality)

    def update_unit(
        self,
        old_id: str,
        new_unit: ProcessedKnowledgeUnit,
        reason: str,
    ) -> None:
        """
        Supersede an existing unit with a corrected version.

        The old unit is marked 'superseded' and a directed CORRECTS edge is
        added from the new unit to the old unit.
        """
        if old_id not in self._unit_index:
            raise ValueError(f"Unit {old_id!r} not found in VEKG")

        old_unit = self._unit_index[old_id]
        old_unit.status = "superseded"
        old_unit.correction_reason = reason
        self.graph.nodes[old_id]["status"] = "superseded"

        # Link lineage
        new_unit.previous_version_id = old_id
        new_unit.version = old_unit.version + 1

        self.add_unit(new_unit)
        self.graph.add_edge(
            new_unit.id,
            old_id,
            relation=EDGE_CORRECTS,
            reason=reason,
        )
        logger.info("Updated unit %s -> %s (reason=%r)", old_id, new_unit.id, reason)

    # ------------------------------------------------------------------
    # Edge operations
    # ------------------------------------------------------------------

    def add_conflict(
        self,
        unit_id_a: str,
        unit_id_b: str,
        conflict_info: dict,
    ) -> None:
        """
        Mark two units as conflicting.

        Both units are set to 'disputed' status and bidirectional
        CONFLICTS_WITH edges are added.
        """
        for uid in (unit_id_a, unit_id_b):
            if uid in self._unit_index:
                self._unit_index[uid].status = "disputed"
                self.graph.nodes[uid]["status"] = "disputed"

        self.graph.add_edge(unit_id_a, unit_id_b, relation=EDGE_CONFLICTS_WITH, **conflict_info)
        self.graph.add_edge(unit_id_b, unit_id_a, relation=EDGE_CONFLICTS_WITH, **conflict_info)
        logger.debug("Conflict edge: %s <-> %s", unit_id_a, unit_id_b)

    def add_support(self, unit_id_a: str, unit_id_b: str) -> None:
        """Add a bidirectional SUPPORTS edge between two compatible units."""
        self.graph.add_edge(unit_id_a, unit_id_b, relation=EDGE_SUPPORTS)
        self.graph.add_edge(unit_id_b, unit_id_a, relation=EDGE_SUPPORTS)

    def add_related(self, unit_id_a: str, unit_id_b: str) -> None:
        """Add a bidirectional RELATED_TO edge (semantic relatedness)."""
        self.graph.add_edge(unit_id_a, unit_id_b, relation=EDGE_RELATED_TO)
        self.graph.add_edge(unit_id_b, unit_id_a, relation=EDGE_RELATED_TO)

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_lineage(self, unit_id: str) -> List[ProcessedKnowledgeUnit]:
        """
        Return the full version history of a unit, newest first.

        Follows the previous_version_id linked list until the root.
        """
        lineage: List[ProcessedKnowledgeUnit] = []
        current_id: Optional[str] = unit_id
        visited: set = set()

        while current_id and current_id not in visited:
            visited.add(current_id)
            unit = self._unit_index.get(current_id)
            if unit is None:
                break
            lineage.append(unit)
            current_id = unit.previous_version_id

        return lineage

    def get_active_units(
        self,
        concept: Optional[str] = None,
        source_id: Optional[str] = None,
    ) -> List[ProcessedKnowledgeUnit]:
        """Return units whose status is 'active' or 'verified'."""
        units = list(self._unit_index.values())
        if concept:
            units = [u for u in units if concept.lower() in u.concept.lower()]
        if source_id:
            units = [u for u in units if u.source_id == source_id]
        return [u for u in units if u.status in ("active", "verified")]

    def get_all_units(
        self,
        source_id: Optional[str] = None,
    ) -> List[ProcessedKnowledgeUnit]:
        """Return all units regardless of status, optionally filtered by source."""
        units = list(self._unit_index.values())
        if source_id:
            units = [u for u in units if u.source_id == source_id]
        return units

    def get_unit(self, unit_id: str) -> Optional[ProcessedKnowledgeUnit]:
        """Return a single unit by id, or None if not present."""
        return self._unit_index.get(unit_id)

    def get_conflicting_units(
        self,
        source_id: Optional[str] = None,
    ) -> List[Tuple[ProcessedKnowledgeUnit, ProcessedKnowledgeUnit]]:
        """
        Return pairs of conflicting units.

        Each pair is returned once (u < v in string ordering avoids duplicates).
        """
        conflicts: List[Tuple[ProcessedKnowledgeUnit, ProcessedKnowledgeUnit]] = []
        for u, v, data in self.graph.edges(data=True):
            if data.get("relation") == EDGE_CONFLICTS_WITH and u < v:
                unit_a = self._unit_index.get(u)
                unit_b = self._unit_index.get(v)
                if unit_a and unit_b:
                    if source_id is None or unit_a.source_id == source_id:
                        conflicts.append((unit_a, unit_b))
        return conflicts

    def search_by_concept(
        self,
        query: str,
        threshold: float = 0.5,
    ) -> List[ProcessedKnowledgeUnit]:
        """
        Find units whose concept label matches the query.

        Tries substring matching first; falls back to SequenceMatcher fuzzy
        matching for near-misses above ``threshold``.  Results are sorted by
        confidence descending.
        """
        results: List[ProcessedKnowledgeUnit] = []
        query_lower = query.lower().strip()

        for unit in self._unit_index.values():
            concept_lower = unit.concept.lower().strip()
            if query_lower in concept_lower or concept_lower in query_lower:
                results.append(unit)
            else:
                ratio = SequenceMatcher(None, query_lower, concept_lower).ratio()
                if ratio >= threshold:
                    results.append(unit)

        # Deduplicate (a unit might match both branches)
        seen: set = set()
        deduped: List[ProcessedKnowledgeUnit] = []
        for u in results:
            if u.id not in seen:
                seen.add(u.id)
                deduped.append(u)

        return sorted(deduped, key=lambda u: u.confidence, reverse=True)

    def get_neighbours(
        self,
        unit_id: str,
        relation: Optional[str] = None,
    ) -> List[ProcessedKnowledgeUnit]:
        """
        Return all units directly connected to ``unit_id``.

        Optionally filter by edge relation type.
        """
        if unit_id not in self.graph:
            return []
        neighbours: List[ProcessedKnowledgeUnit] = []
        for _, v, data in self.graph.out_edges(unit_id, data=True):
            if relation is None or data.get("relation") == relation:
                unit = self._unit_index.get(v)
                if unit:
                    neighbours.append(unit)
        return neighbours

    # ------------------------------------------------------------------
    # Status mutations
    # ------------------------------------------------------------------

    def mark_verified(self, unit_id: str) -> None:
        """Promote a unit's status from 'active' to 'verified'."""
        if unit_id in self._unit_index:
            self._unit_index[unit_id].status = "verified"
            self.graph.nodes[unit_id]["status"] = "verified"

    def mark_resolved(self, unit_id_a: str, unit_id_b: str, resolution: str) -> None:
        """
        Mark a conflict as resolved by removing CONFLICTS_WITH edges and
        restoring affected units to 'active' status.
        """
        for u, v in [(unit_id_a, unit_id_b), (unit_id_b, unit_id_a)]:
            if self.graph.has_edge(u, v):
                edge_data = self.graph.edges[u, v]
                if edge_data.get("relation") == EDGE_CONFLICTS_WITH:
                    self.graph.remove_edge(u, v)

        for uid in (unit_id_a, unit_id_b):
            if uid in self._unit_index:
                unit = self._unit_index[uid]
                if unit.status == "disputed":
                    unit.status = "active"
                    self.graph.nodes[uid]["status"] = "active"

        logger.info(
            "Conflict resolved between %s and %s: %r",
            unit_id_a, unit_id_b, resolution,
        )

    # ------------------------------------------------------------------
    # Serialisation / export
    # ------------------------------------------------------------------

    def to_dict(self, source_id: Optional[str] = None) -> dict:
        """
        Serialise the graph (or a source-filtered sub-graph) to a JSON-safe
        dict suitable for the /knowledge-graph API endpoint.
        """
        units = self.get_all_units(source_id)
        unit_ids = {u.id for u in units}

        edges = [
            {
                "from": u,
                "to": v,
                "relation": data.get("relation"),
            }
            for u, v, data in self.graph.edges(data=True)
            if u in unit_ids and v in unit_ids
        ]

        return {
            "nodes": [
                {
                    "id": u.id,
                    "concept": u.concept,
                    "modality": u.modality,
                    "status": u.status,
                    "confidence": u.confidence,
                    "version": u.version,
                    "source_id": u.source_id,
                }
                for u in units
            ],
            "edges": edges,
            "stats": self.stats(source_id),
        }

    def stats(self, source_id: Optional[str] = None) -> dict:
        """Return aggregate counts for the graph or a source sub-graph."""
        units = self.get_all_units(source_id)
        conflict_edge_count = sum(
            1
            for _, _, d in self.graph.edges(data=True)
            if d.get("relation") == EDGE_CONFLICTS_WITH
        ) // 2  # bidirectional edges counted once

        return {
            "total_units": len(units),
            "active": sum(1 for u in units if u.status == "active"),
            "verified": sum(1 for u in units if u.status == "verified"),
            "disputed": sum(1 for u in units if u.status == "disputed"),
            "superseded": sum(1 for u in units if u.status == "superseded"),
            "conflict_pairs": conflict_edge_count,
            "total_nodes": self.graph.number_of_nodes(),
            "total_edges": self.graph.number_of_edges(),
        }

    # ------------------------------------------------------------------
    # Magic methods
    # ------------------------------------------------------------------

    def __len__(self) -> int:
        return len(self._unit_index)

    def __contains__(self, unit_id: str) -> bool:
        return unit_id in self._unit_index

    def __repr__(self) -> str:
        s = self.stats()
        return (
            f"<VEKG units={s['total_units']} active={s['active']} "
            f"disputed={s['disputed']} conflict_pairs={s['conflict_pairs']}>"
        )
