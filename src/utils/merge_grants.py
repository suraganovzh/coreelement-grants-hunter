"""Merge and deduplicate grant data from multiple scraper outputs.

Combines all *_raw.json files into a single grants.json with deduplication.
Runs in GitHub Actions after all scrapers complete.
"""

import argparse
import json
import hashlib
from datetime import datetime
from pathlib import Path

from src.utils.logger import setup_logger

logger = setup_logger("merge_grants")


def generate_grant_id(grant: dict) -> str:
    """Generate a deterministic ID from grant title + funder + URL."""
    key = f"{grant.get('title', '')}{grant.get('funder', '')}{grant.get('url', '')}".lower().strip()
    return hashlib.md5(key.encode()).hexdigest()[:12]


def load_raw_files(data_dir: str = "data") -> list[dict]:
    """Load all *_raw.json files from the data directory."""
    all_grants: list[dict] = []

    for raw_file in sorted(Path(data_dir).glob("*_raw.json")):
        try:
            with open(raw_file) as f:
                data = json.load(f)
                if isinstance(data, list):
                    all_grants.extend(data)
                elif isinstance(data, dict) and "grants" in data:
                    all_grants.extend(data["grants"])
                elif isinstance(data, dict):
                    all_grants.append(data)
            logger.info("Loaded %d grants from %s", len(data) if isinstance(data, list) else 1, raw_file.name)
        except (json.JSONDecodeError, FileNotFoundError) as e:
            logger.error("Failed to load %s: %s", raw_file, e)

    return all_grants


def deduplicate(grants: list[dict]) -> list[dict]:
    """Remove duplicate grants based on title similarity and URL."""
    seen: dict[str, dict] = {}

    for grant in grants:
        grant_id = generate_grant_id(grant)

        if "id" not in grant:
            grant["id"] = grant_id

        if grant_id not in seen:
            seen[grant_id] = grant
        else:
            # Keep the one with more data
            existing = seen[grant_id]
            if len(json.dumps(grant)) > len(json.dumps(existing)):
                seen[grant_id] = grant

    return list(seen.values())


def normalize_grant(grant: dict) -> dict:
    """Normalize grant fields to a consistent schema."""
    # Ensure all expected fields exist
    return {
        "id": grant.get("id", generate_grant_id(grant)),
        "title": grant.get("title", ""),
        "funder": grant.get("funder", ""),
        "description": grant.get("description", ""),
        "amount_min": grant.get("amount_min") or 0,
        "amount_max": grant.get("amount_max") or 0,
        "currency": grant.get("currency", "USD"),
        "deadline": grant.get("deadline", ""),
        "url": grant.get("url", ""),
        "source": grant.get("source", ""),
        "grant_type": grant.get("grant_type", ""),
        "industry_tags": grant.get("industry_tags", []),
        "eligibility": grant.get("eligibility_text", "") or grant.get("eligibility", ""),
        "requirements": grant.get("requirements_text", "") or grant.get("requirements", ""),
        "focus_areas": grant.get("focus_areas", []),
        "scraped_at": grant.get("scraped_at", datetime.now().isoformat()),
    }


def main():
    parser = argparse.ArgumentParser(description="Merge and deduplicate grant data")
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--output", default="data/grants.json")
    args = parser.parse_args()

    print("Loading raw grant files...")
    raw_grants = load_raw_files(args.data_dir)
    print(f"Loaded {len(raw_grants)} total grants from raw files")

    # Load existing grants to preserve already-processed ones
    existing_grants: list[dict] = []
    try:
        with open(args.output) as f:
            data = json.load(f)
            existing_grants = data.get("grants", []) if isinstance(data, dict) else data
    except (FileNotFoundError, json.JSONDecodeError):
        pass

    # Combine and deduplicate
    all_grants = existing_grants + [normalize_grant(g) for g in raw_grants]
    unique_grants = deduplicate(all_grants)

    new_count = len(unique_grants) - len(existing_grants)

    output = {
        "metadata": {
            "updated_at": datetime.now().isoformat(),
            "total_grants": len(unique_grants),
            "new_grants": max(0, new_count),
        },
        "grants": unique_grants,
    }

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w") as f:
        json.dump(output, f, indent=2)

    print(f"Merged: {len(unique_grants)} unique grants ({max(0, new_count)} new)")
    print(f"Saved to {args.output}")


if __name__ == "__main__":
    main()
