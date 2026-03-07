"""Consolidated grant data pipeline.

Merges grants from all sources (federal, state, private foundations,
EU, corporate, imminent NOFOs) into a single analyzed.json.
"""

import argparse
import json
from datetime import datetime
from pathlib import Path

from src.utils.logger import setup_logger
from src.utils.merge_grants import generate_grant_id, normalize_grant, deduplicate

logger = setup_logger("consolidate")


def load_json_safe(path: str) -> list[dict]:
    """Load grants from a JSON file, handling various formats."""
    try:
        with open(path) as f:
            data = json.load(f)
            if isinstance(data, list):
                return data
            if isinstance(data, dict):
                if "grants" in data:
                    return data["grants"]
                return [data]
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.warning("Could not load %s: %s", path, e)
    return []


def calculate_urgency(grant: dict) -> dict:
    """Calculate urgency flags for a grant."""
    from src.utils.date_utils import DateUtils

    deadline = grant.get("deadline", "")
    days = DateUtils.days_until(deadline) if deadline else None

    if days is None:
        return {
            "days_until_deadline": None,
            "priority_level": "PLANNING",
            "action_required": "monitor",
        }

    if days < 0:
        return {
            "days_until_deadline": days,
            "priority_level": "EXPIRED",
            "action_required": "none",
        }
    if days <= 3:
        return {
            "days_until_deadline": days,
            "priority_level": "CRITICAL",
            "action_required": "immediate",
        }
    if days <= 7:
        return {
            "days_until_deadline": days,
            "priority_level": "URGENT",
            "action_required": "this_week",
        }
    if days <= 30:
        return {
            "days_until_deadline": days,
            "priority_level": "IMPORTANT",
            "action_required": "this_month",
        }

    return {
        "days_until_deadline": days,
        "priority_level": "PLANNING",
        "action_required": "prepare",
    }


def enrich_grant(grant: dict) -> dict:
    """Enrich grant with urgency, source tracking, and metadata."""
    # Add urgency flags
    grant["urgency"] = calculate_urgency(grant)

    # Add source tracking
    if "source_type" not in grant:
        source = grant.get("source", "")
        if "state" in source:
            grant["source_type"] = "state"
        elif "foundation" in source or "eqt" in source or "sloan" in source:
            grant["source_type"] = "private_foundation"
        elif "eu" in source or "horizon" in source:
            grant["source_type"] = "eu"
        elif "nofo" in source or "pipeline" in source:
            grant["source_type"] = "nofo_pipeline"
        elif source in ("grants_gov", "sbir_sttr", "nsf", "doe", "arpa_e"):
            grant["source_type"] = "federal"
        elif "corporate" in source:
            grant["source_type"] = "corporate"
        else:
            grant["source_type"] = "other"

    # Add last verified timestamp
    if "last_verified" not in grant:
        grant["last_verified"] = grant.get("scraped_at", datetime.now().isoformat())

    return grant


def consolidate_all_grants(data_dir: str = "data") -> list[dict]:
    """Merge and enrich grants from all sources.

    Sources:
    - Federal grants (grants.json from existing pipeline)
    - State grants (state_grants_raw.json, state_colorado_raw.json, etc.)
    - Private foundations (foundation_eqt_raw.json, foundation_sloan_raw.json, etc.)
    - EU grants (eu_raw.json)
    - Corporate grants (corporate_raw.json)
    - NOFO pipeline (nofo_pipeline.json)
    - SBIR status (sbir_status.json - for status info, not grants)
    """
    all_grants: list[dict] = []

    # Federal grants (main pipeline)
    federal = load_json_safe(f"{data_dir}/grants.json")
    all_grants.extend(federal)
    logger.info("Federal: %d grants", len(federal))

    # State grants
    state_files = [
        "state_grants_raw.json",
        "state_colorado_raw.json",
        "state_delaware_raw.json",
    ]
    for fname in state_files:
        state = load_json_safe(f"{data_dir}/{fname}")
        all_grants.extend(state)
        if state:
            logger.info("State (%s): %d grants", fname, len(state))

    # Foundation grants
    foundation_files = [
        "foundation_raw.json",
        "foundation_eqt_raw.json",
        "foundation_sloan_raw.json",
    ]
    for fname in foundation_files:
        found = load_json_safe(f"{data_dir}/{fname}")
        all_grants.extend(found)
        if found:
            logger.info("Foundation (%s): %d grants", fname, len(found))

    # EU grants
    eu = load_json_safe(f"{data_dir}/eu_raw.json")
    all_grants.extend(eu)
    if eu:
        logger.info("EU: %d grants", len(eu))

    # Corporate grants
    corporate = load_json_safe(f"{data_dir}/corporate_raw.json")
    all_grants.extend(corporate)
    if corporate:
        logger.info("Corporate: %d grants", len(corporate))

    # NOFO pipeline (imminent grants)
    nofo = load_json_safe(f"{data_dir}/nofo_pipeline.json")
    all_grants.extend(nofo)
    if nofo:
        logger.info("NOFO pipeline: %d grants", len(nofo))

    # Kazakhstan grants
    kz = load_json_safe(f"{data_dir}/kazakhstan_raw.json")
    all_grants.extend(kz)
    if kz:
        logger.info("Kazakhstan: %d grants", len(kz))

    # Normalize all grants
    normalized = [normalize_grant(g) for g in all_grants]

    # Deduplicate
    unique = deduplicate(normalized)

    # Enrich each grant
    enriched = [enrich_grant(g) for g in unique]

    # Filter out expired grants
    active = [
        g for g in enriched
        if g.get("urgency", {}).get("priority_level") != "EXPIRED"
    ]
    expired_count = len(enriched) - len(active)
    if expired_count:
        logger.info("Filtered out %d expired grants", expired_count)

    logger.info(
        "Consolidated: %d active grants from %d total (%d expired removed)",
        len(active), len(all_grants), expired_count,
    )
    return active


def main():
    parser = argparse.ArgumentParser(description="Consolidate all grant data")
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--output", default="data/analyzed.json")
    args = parser.parse_args()

    grants = consolidate_all_grants(args.data_dir)

    # Load SBIR status for metadata
    sbir_status = {}
    try:
        with open(f"{args.data_dir}/sbir_status.json") as f:
            sbir_status = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        pass

    # Count by source type
    source_counts: dict[str, int] = {}
    for g in grants:
        st = g.get("source_type", "other")
        source_counts[st] = source_counts.get(st, 0) + 1

    # Count urgent
    urgent_count = sum(
        1 for g in grants
        if g.get("urgency", {}).get("priority_level") in ("CRITICAL", "URGENT")
    )

    output = {
        "metadata": {
            "updated_at": datetime.now().isoformat(),
            "total_grants": len(grants),
            "source_breakdown": source_counts,
            "urgent_grants": urgent_count,
            "sbir_status": sbir_status.get("overall_status", "UNKNOWN"),
        },
        "grants": grants,
    }

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w") as f:
        json.dump(output, f, indent=2)

    print(f"Consolidated: {len(grants)} unique grants")
    print(f"  Source breakdown: {source_counts}")
    print(f"  Urgent (< 7 days): {urgent_count}")
    print(f"  SBIR status: {sbir_status.get('overall_status', 'UNKNOWN')}")
    print(f"  Saved to {args.output}")


if __name__ == "__main__":
    main()
