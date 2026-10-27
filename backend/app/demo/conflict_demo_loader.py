"""
VisionRAG-X Conflict Demo Pack Loader and Fixture Service.

Maps synthetic demo pack records into the production SQLAlchemy schema
under the isolated scope 'demo_conflict_source_001'.
Provides load, unload, and status reporting functions.
"""
import argparse
import asyncio
import json
import logging
import os
import sys
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.postgres import AsyncSessionLocal
from app.knowledge.models import (
    Conflict,
    Evidence,
    KnowledgeUnit,
    ProcessingJob,
    Source,
)
from app.knowledge.knowledge_units import ProcessedKnowledgeUnit
from app.knowledge.vekg import VEKG, EDGE_CORRECTS, EDGE_SUPERSEDES, EDGE_CONFLICTS_WITH, EDGE_RELATED_TO

logger = logging.getLogger(__name__)

# Dedicated scope identifier
DEMO_SOURCE_ID = "demo_conflict_source_001"


def get_demo_pack_dir() -> Path:
    """Locate the conflict_demo_pack directory."""
    # Try relative to this file
    base = Path(__file__).resolve().parent.parent.parent.parent
    candidates = [
        base / "conflict_demo_pack",
        base / "visionrag-x" / "conflict_demo_pack",
        Path("/Users/vabhiram/Documents/VisionRAG/visionrag-x/conflict_demo_pack"),
        Path("/Users/vabhiram/Documents/VisionRAG/conflict_demo_pack"),
    ]
    for c in candidates:
        if c.exists() and (c / "manifest.json").exists():
            return c
    raise FileNotFoundError("Could not find conflict_demo_pack directory with manifest.json")


def load_pack_json_files() -> Dict[str, Any]:
    """Load and parse all demo pack JSON files."""
    pack_dir = get_demo_pack_dir()
    manifest_path = pack_dir / "manifest.json"
    kus_path = pack_dir / "knowledge_units.json"
    conflicts_path = pack_dir / "conflicts.json"
    vekg_edges_path = pack_dir / "vekg_edges.json"
    test_plan_path = pack_dir / "demo_test_plan.json"

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)
    with open(kus_path, "r", encoding="utf-8") as f:
        knowledge_units = json.load(f)
    with open(conflicts_path, "r", encoding="utf-8") as f:
        conflicts = json.load(f)
    with open(vekg_edges_path, "r", encoding="utf-8") as f:
        vekg_edges = json.load(f)
    with open(test_plan_path, "r", encoding="utf-8") as f:
        test_plan = json.load(f)

    return {
        "manifest": manifest,
        "knowledge_units": knowledge_units,
        "conflicts": conflicts,
        "vekg_edges": vekg_edges,
        "test_plan": test_plan,
    }


async def get_demo_pack_status(db: AsyncSession) -> Dict[str, Any]:
    """Inspect current database state for the demo pack."""
    res = await db.execute(select(Source).where(Source.id == DEMO_SOURCE_ID))
    source = res.scalar_one_or_none()
    if not source:
        return {
            "loaded": False,
            "source_id": DEMO_SOURCE_ID,
            "source_title": None,
            "units_count": 0,
            "conflicts_count": 0,
        }

    ku_res = await db.execute(select(KnowledgeUnit).where(KnowledgeUnit.source_id == DEMO_SOURCE_ID))
    kus = ku_res.scalars().all()

    conf_res = await db.execute(select(Conflict).where(Conflict.source_id == DEMO_SOURCE_ID))
    confs = conf_res.scalars().all()

    return {
        "loaded": True,
        "source_id": DEMO_SOURCE_ID,
        "source_title": source.title,
        "status": source.status,
        "units_count": len(kus),
        "conflicts_count": len(confs),
    }


async def unload_demo_pack(
    db: AsyncSession,
    hybrid_index: Optional[Any] = None,
) -> bool:
    """
    Remove all records belonging strictly to DEMO_SOURCE_ID.
    Never alters production user records.
    """
    res = await db.execute(select(Source).where(Source.id == DEMO_SOURCE_ID))
    source = res.scalar_one_or_none()
    if source:
        await db.delete(source)
        await db.commit()
        logger.info("Unloaded Source %s and all associated cascade records.", DEMO_SOURCE_ID)
        return True
    return False


async def load_demo_pack(
    db: AsyncSession,
    hybrid_index: Optional[Any] = None,
    vekg: Optional[VEKG] = None,
    force_reload: bool = True,
) -> Dict[str, Any]:
    """
    Load the synthetic Conflict Demo Pack into PostgreSQL, Vector/Lexical Index, and VEKG.
    """
    pack_data = load_pack_json_files()
    manifest = pack_data["manifest"]
    kus_data = pack_data["knowledge_units"]
    conflicts_data = pack_data["conflicts"]
    vekg_edges = pack_data["vekg_edges"]

    # If force_reload, clean prior state first
    if force_reload:
        await unload_demo_pack(db, hybrid_index=hybrid_index)

    # 1. Create Source record
    source_meta = manifest.get("source", {})
    source = Source(
        id=DEMO_SOURCE_ID,
        title=source_meta.get("title", "Multimodal Algorithms & Physics Lecture"),
        source_type=source_meta.get("source_type", "video"),
        duration=source_meta.get("duration", 360.0),
        channel=source_meta.get("channel", "VisionRAG-X Research Lab"),
        status="completed",
        metadata_=source_meta.get("metadata", {"is_demo": True}),
    )
    db.add(source)

    # 2. Create completed ProcessingJob
    job = ProcessingJob(
        id=str(uuid.uuid4()),
        source_id=DEMO_SOURCE_ID,
        status="completed",
        current_step="ready",
        progress=1.0,
    )
    db.add(job)

    # 3. Create Knowledge Units and Evidence records
    persisted_kus: List[KnowledgeUnit] = []
    pku_list: List[ProcessedKnowledgeUnit] = []

    for item in kus_data:
        ku = KnowledgeUnit(
            id=item["id"],
            concept=item["concept"],
            content=item["content"],
            modality=item["modality"],
            source_id=DEMO_SOURCE_ID,
            timestamp_start=item.get("timestamp_start"),
            timestamp_end=item.get("timestamp_end"),
            page=item.get("page"),
            slide=item.get("slide"),
            confidence=item.get("confidence", 1.0),
            status=item.get("status", "active"),
            version=item.get("version", 1),
            previous_version_id=item.get("previous_version_id"),
            correction_reason=item.get("correction_reason"),
        )
        db.add(ku)
        persisted_kus.append(ku)

        # Backing evidence segment
        ev = Evidence(
            id=str(uuid.uuid4()),
            knowledge_unit_id=item["id"],
            text=item["content"],
            modality=item["modality"],
            source_id=DEMO_SOURCE_ID,
            timestamp_start=item.get("timestamp_start"),
            timestamp_end=item.get("timestamp_end"),
            page=item.get("page"),
            extraction_confidence=item.get("confidence", 1.0),
        )
        db.add(ev)

        # Form ProcessedKnowledgeUnit for in-memory graph
        pku = ProcessedKnowledgeUnit(
            id=item["id"],
            concept=item["concept"],
            content=item["content"],
            modality=item["modality"],
            source_id=DEMO_SOURCE_ID,
            timestamp_start=item.get("timestamp_start"),
            timestamp_end=item.get("timestamp_end"),
            page=item.get("page"),
            slide=item.get("slide"),
            confidence=item.get("confidence", 1.0),
            status=item.get("status", "active"),
            version=item.get("version", 1),
            previous_version_id=item.get("previous_version_id"),
            correction_reason=item.get("correction_reason"),
        )
        pku_list.append(pku)

    # 4. Create Conflict records
    persisted_conflicts: List[Conflict] = []
    conflict_dicts: List[Dict[str, Any]] = []

    for c in conflicts_data:
        conf = Conflict(
            id=c.get("conflict_id", str(uuid.uuid4())),
            source_id=DEMO_SOURCE_ID,
            conflict_type=c.get("type", "cross_modal_disagreement"),
            modalities=c.get("sources", []),
            claims=c.get("claims", []),
            timestamp=c.get("timestamp"),
            page=c.get("page"),
            severity=c.get("severity", "high"),
            confidence=c.get("confidence", 0.9),
            resolved=c.get("resolved", True),
            resolution=c.get("resolution"),
        )
        db.add(conf)
        persisted_conflicts.append(conf)
        conflict_dicts.append({
            "id": conf.id,
            "type": conf.conflict_type,
            "modalities": conf.modalities,
            "claims": conf.claims,
            "timestamp": conf.timestamp,
            "severity": conf.severity,
            "resolved": conf.resolved,
            "resolution": conf.resolution,
            "unit_ids": c.get("unit_ids", []),
        })

    await db.commit()
    logger.info("Persisted demo source %s with %d KUs and %d conflicts.", DEMO_SOURCE_ID, len(persisted_kus), len(persisted_conflicts))

    # 5. Hydrate VEKG graph if provided
    if vekg is not None:
        vekg.reconstruct_from_units(pku_list, conflicts=conflict_dicts)
        # Apply expected edges if not fully implied
        for edge in vekg_edges:
            s_id = edge["source_unit_id"]
            t_id = edge["target_unit_id"]
            rel = edge["relation"]
            if s_id in vekg._unit_index and t_id in vekg._unit_index:
                if not vekg.graph.has_edge(s_id, t_id):
                    vekg.graph.add_edge(s_id, t_id, relation=rel, reason=edge.get("reason", ""))

    # 6. Index into HybridIndex if provided
    if hybrid_index is not None:
        try:
            ku_dicts = [
                {
                    "id": u.id,
                    "concept": u.concept,
                    "content": u.content,
                    "modality": u.modality,
                    "source_id": u.source_id,
                    "timestamp_start": u.timestamp_start,
                    "timestamp_end": u.timestamp_end,
                    "page": u.page,
                    "confidence": u.confidence,
                    "status": u.status,
                    "version": u.version,
                }
                for u in persisted_kus
            ]
            await hybrid_index.index_units(ku_dicts)
        except Exception as e:
            logger.warning("Optional hybrid index population encountered: %s", e)

    return {
        "status": "success",
        "source_id": DEMO_SOURCE_ID,
        "units_loaded": len(persisted_kus),
        "conflicts_loaded": len(persisted_conflicts),
        "vekg_edges_count": len(vekg_edges) if vekg_edges else 0,
    }


def main():
    """CLI handler for manual demo pack management."""
    parser = argparse.ArgumentParser(description="VisionRAG-X Conflict Demo Pack Loader")
    parser.add_argument("--load", action="store_true", help="Load demo pack into the database")
    parser.add_argument("--unload", action="store_true", help="Unload and cleanup demo pack records")
    parser.add_argument("--status", action="store_true", help="Display current demo pack load status")
    args = parser.parse_args()

    async def _run():
        async with AsyncSessionLocal() as session:
            if args.load:
                print(f"[DEMO LOADER] Loading VisionRAG-X Conflict Demo Pack into {DEMO_SOURCE_ID}...")
                res = await load_demo_pack(session)
                print(f"[DEMO LOADER] Successfully loaded: {res}")
            elif args.unload:
                print(f"[DEMO LOADER] Cleaning up demo pack {DEMO_SOURCE_ID}...")
                deleted = await unload_demo_pack(session)
                print(f"[DEMO LOADER] Cleanup completed (deleted: {deleted}).")
            elif args.status:
                status = await get_demo_pack_status(session)
                print(f"[DEMO LOADER] Status: {status}")
            else:
                parser.print_help()

    asyncio.run(_run())


if __name__ == "__main__":
    main()
