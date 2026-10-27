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
import re
import uuid
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional, Tuple

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

    def reconstruct_from_units(
        self,
        units: List[ProcessedKnowledgeUnit],
        conflicts: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        """
        Reconstruct the VEKG graph, version lineage edges, and conflict relationships
        from persisted knowledge units and conflict records.

        Ensures:
        1. All units are registered as nodes and in _unit_index / _concept_index.
        2. Version correction and superseding edges (CORRECTS / SUPERSEDES) are
           reconstructed from previous_version_id matching the graph API direction.
        3. Dangling previous_version_id references (pointing to non-existent units)
           are safely detected and do not create invalid edges.
        4. Bidirectional CONFLICTS_WITH edges are reconstructed from persisted conflict
           records without duplicates.
        5. Historical claims and their superseded / disputed statuses are preserved.
        """
        # Step 1: Add all units to graph nodes and indexes
        for u in units:
            self.add_unit(u)

        # Step 2: Reconstruct version lineage edges (new_version -> old_version)
        for u in units:
            if u.previous_version_id:
                prev_id = u.previous_version_id
                if prev_id in self._unit_index:
                    old_unit = self._unit_index[prev_id]
                    is_correction = bool(u.correction_reason or old_unit.status == "superseded" or u.status == "verified")
                    if is_correction and old_unit.status != "superseded":
                        old_unit.status = "superseded"
                        self.graph.nodes[prev_id]["status"] = "superseded"
                    relation = EDGE_CORRECTS if is_correction else EDGE_SUPERSEDES
                    if not self.graph.has_edge(u.id, prev_id):
                        self.graph.add_edge(
                            u.id,
                            prev_id,
                            relation=relation,
                            reason=u.correction_reason or "Version update",
                        )
                else:
                    logger.warning(
                        "Dangling previous_version_id reference: unit %s references %s which is not in persisted units",
                        u.id, prev_id
                    )

        # Step 3: Reconstruct conflict relationships
        if conflicts:
            for c in conflicts:
                # Direct unit IDs if present
                u_ids = c.get("unit_ids") or []
                if len(u_ids) >= 2:
                    u_a, u_b = u_ids[0], u_ids[1]
                    if u_a in self._unit_index and u_b in self._unit_index:
                        self.add_conflict(u_a, u_b, {
                            "conflict_type": c.get("conflict_type") or c.get("type", "unknown"),
                            "severity": c.get("severity", "medium"),
                            "confidence": c.get("confidence", 0.5),
                            "claims": c.get("claims", []),
                            "resolved": bool(c.get("resolved", False)),
                            "resolution": c.get("resolution"),
                        })
                        continue

                # Fallback: Match units by timestamp/page proximity and concept/claim text
                c_ts = c.get("timestamp")
                c_page = c.get("page")
                c_modalities = c.get("modalities") or c.get("sources") or []
                c_claims = [str(cl).lower() for cl in c.get("claims", [])]

                candidate_units = []
                for uid, u in self._unit_index.items():
                    ts_match = (c_ts is not None and u.timestamp_start is not None and abs(c_ts - u.timestamp_start) <= 30.0)
                    page_match = (c_page is not None and (u.page == c_page or u.slide == c_page))
                    modality_match = (not c_modalities) or (u.modality in c_modalities)
                    claim_match = (not c_claims) or any(cl in u.content.lower() or u.concept.lower() in cl for cl in c_claims)
                    if (ts_match or page_match) and (modality_match or claim_match):
                        candidate_units.append(u)

                if len(candidate_units) >= 2:
                    u_a = candidate_units[0]
                    u_b = candidate_units[1]
                    self.add_conflict(u_a.id, u_b.id, {
                        "conflict_type": c.get("conflict_type") or c.get("type", "unknown"),
                        "severity": c.get("severity", "medium"),
                        "confidence": c.get("confidence", 0.5),
                        "claims": c.get("claims", []),
                        "resolved": bool(c.get("resolved", False)),
                        "resolution": c.get("resolution"),
                    })
                elif len(candidate_units) == 1:
                    u_a = candidate_units[0]
                    self.add_conflict(u_a.id, u_a.id, {
                        "conflict_type": c.get("conflict_type") or c.get("type", "unknown"),
                        "severity": c.get("severity", "medium"),
                        "confidence": c.get("confidence", 0.5),
                        "claims": c.get("claims", []),
                        "resolved": bool(c.get("resolved", False)),
                        "resolution": c.get("resolution"),
                    })

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
                # If conflict is resolved, do not downgrade superseded or verified terminal statuses
                if conflict_info.get("resolved"):
                    if self._unit_index[uid].status not in ("superseded", "verified"):
                        self._unit_index[uid].status = "disputed"
                        self.graph.nodes[uid]["status"] = "disputed"
                else:
                    # Unresolved conflict marks units as disputed
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

    def traverse_related_concepts(
        self,
        query: str,
        threshold: float = 0.35,
        source_id: Optional[str] = None,
        max_results: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Traverse the VEKG graph starting from seed concept nodes matching the query.
        Discovers:
        - Direct concept matches and lineage chains (corrects/supersedes)
        - Connected conflict nodes (cross-modal disagreements)
        - Multi-hop related topic nodes (supports/related_to)

        Returns a list of dicts with unit, relevance score, and graph relationship metadata.
        """
        seeds = self.search_by_concept(query, threshold=threshold)
        query_words = set(re.findall(r'\b[a-zA-Z0-9_\^²³]{2,}\b', query.lower()))

        # Also search unit content if seeds from concept labels alone are sparse
        if len(seeds) < 3:
            for u in self._unit_index.values():
                if source_id and u.source_id != source_id:
                    continue
                content_lower = u.content.lower()
                if any(qw in content_lower for qw in query_words if len(qw) > 3):
                    if u not in seeds:
                        seeds.append(u)

        candidates_map: Dict[str, Dict[str, Any]] = {}

        for seed in seeds:
            if source_id and seed.source_id != source_id:
                continue

            base_score = float(seed.confidence)
            # Boost active and verified status in graph
            if seed.status == 'verified':
                base_score *= 1.10
            elif seed.status == 'superseded':
                base_score *= 0.85

            if seed.id not in candidates_map:
                candidates_map[seed.id] = {
                    'unit': seed,
                    'score': base_score,
                    'is_seed': True,
                    'relations': [],
                }

            # Traverse adjacent nodes in VEKG
            if seed.id in self.graph:
                # Outgoing edges
                for _, target_id, edge_data in self.graph.out_edges(seed.id, data=True):
                    rel = edge_data.get('relation', EDGE_RELATED_TO)
                    target_unit = self._unit_index.get(target_id)
                    if target_unit:
                        if source_id and target_unit.source_id != source_id:
                            continue
                        rel_info = f"{rel} -> {target_unit.concept}"
                        candidates_map[seed.id]['relations'].append(rel_info)

                        if target_id not in candidates_map:
                            t_score = target_unit.confidence * (
                                1.05 if rel in (EDGE_CORRECTS, EDGE_SUPERSEDES) else 0.80
                            )
                            candidates_map[target_id] = {
                                'unit': target_unit,
                                'score': t_score,
                                'is_seed': False,
                                'relations': [f"Connected via {rel} from {seed.concept}"],
                            }

                # Incoming edges
                for src_id, _, edge_data in self.graph.in_edges(seed.id, data=True):
                    rel = edge_data.get('relation', EDGE_RELATED_TO)
                    src_unit = self._unit_index.get(src_id)
                    if src_unit:
                        if source_id and src_unit.source_id != source_id:
                            continue
                        if src_id not in candidates_map:
                            s_score = src_unit.confidence * (
                                1.15 if rel in (EDGE_CORRECTS, EDGE_SUPERSEDES) else 0.80
                            )
                            candidates_map[src_id] = {
                                'unit': src_unit,
                                'score': s_score,
                                'is_seed': False,
                                'relations': [f"Incoming {rel} to {seed.concept}"],
                            }

        results = list(candidates_map.values())
        results.sort(key=lambda x: x['score'], reverse=True)
        return results[:max_results]

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
