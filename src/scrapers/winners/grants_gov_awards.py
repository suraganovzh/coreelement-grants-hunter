"""Scrape awarded grants from grants.gov.

Targets the last N days of awards, filtering for AI/mining/geology relevance.
Runs in GitHub Actions (cloud) on a weekly schedule.
"""

import argparse
import json
from datetime import datetime, timedelta
from pathlib import Path

import requests

from src.utils.logger import setup_logger

logger = setup_logger("grants_gov_awards")

KEYWORDS = [
    "artificial intelligence", "machine learning", "AI",
    "mining", "mineral", "geology", "exploration",
    "geospatial", "remote sensing", "critical minerals",
    "lithium", "copper", "cobalt", "rare earth",
    "geological survey", "subsurface", "drilling",
    "clean energy", "battery metals",
]

BASE_URL = "https://api.grants.gov/v1/api/search"


def scrape_awards(days: int = 30) -> list[dict]:
    """Scrape awarded grants from grants.gov API."""
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)

    awards: list[dict] = []

    try:
        payload = {
            "keyword": "awarded",
            "oppStatuses": "closed",
            "sortBy": "openDate|desc",
            "rows": 100,
            "startRecordNum": 0,
        }

        response = requests.post(BASE_URL, json=payload, timeout=30)
        response.raise_for_status()
        data = response.json()

        opportunities = data.get("oppHits", [])
        logger.info("Fetched %d closed opportunities", len(opportunities))

        for opp in opportunities:
            title = opp.get("title", "") or opp.get("opportunityTitle", "")
            description = opp.get("synopsis", {}).get("synopsisDesc", "") if isinstance(opp.get("synopsis"), dict) else ""
            text = f"{title} {description}".lower()

            if not any(kw in text for kw in KEYWORDS):
                continue

            award_date_str = opp.get("closeDate", "")
            if award_date_str:
                try:
                    award_date = datetime.strptime(award_date_str[:10], "%m/%d/%Y")
                    if award_date < start_date:
                        continue
                except (ValueError, IndexError):
                    pass

            award = {
                "id": str(opp.get("id", opp.get("opportunityNumber", ""))),
                "title": title,
                "funder": opp.get("agencyName", ""),
                "amount": opp.get("awardCeiling", 0),
                "winner": opp.get("awardee", ""),
                "abstract": description[:2000],
                "award_date": award_date_str,
                "opportunity_number": opp.get("number", ""),
                "keywords": [kw for kw in KEYWORDS if kw in text],
                "source": "grants.gov",
                "scraped_at": datetime.now().isoformat(),
            }
            awards.append(award)

    except Exception as e:
        logger.error("Error scraping grants.gov awards: %s", e)

    # Also try the search with keyword approach for broader coverage
    for search_kw in ["critical minerals award", "AI mining award", "geological exploration award"]:
        try:
            payload = {
                "keyword": search_kw,
                "oppStatuses": "closed",
                "sortBy": "openDate|desc",
                "rows": 50,
                "startRecordNum": 0,
            }
            response = requests.post(BASE_URL, json=payload, timeout=30)
            if response.ok:
                hits = response.json().get("oppHits", [])
                seen_ids = {a["id"] for a in awards}
                for opp in hits:
                    opp_id = str(opp.get("id", ""))
                    if opp_id in seen_ids:
                        continue
                    title = opp.get("title", "")
                    desc = opp.get("synopsis", {}).get("synopsisDesc", "") if isinstance(opp.get("synopsis"), dict) else ""
                    text = f"{title} {desc}".lower()
                    if any(kw in text for kw in KEYWORDS):
                        awards.append({
                            "id": opp_id,
                            "title": title,
                            "funder": opp.get("agencyName", ""),
                            "amount": opp.get("awardCeiling", 0),
                            "winner": "",
                            "abstract": desc[:2000],
                            "award_date": opp.get("closeDate", ""),
                            "opportunity_number": opp.get("number", ""),
                            "keywords": [kw for kw in KEYWORDS if kw in text],
                            "source": "grants.gov",
                            "scraped_at": datetime.now().isoformat(),
                        })
        except Exception as e:
            logger.debug("Search for '%s' failed: %s", search_kw, e)

    logger.info("Found %d relevant awarded grants from grants.gov", len(awards))
    return awards


def main():
    parser = argparse.ArgumentParser(description="Scrape grants.gov awarded grants")
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--output", default="data/winners_grants_gov.json")
    args = parser.parse_args()

    print(f"Scraping awarded grants from last {args.days} days...")
    awards = scrape_awards(args.days)
    print(f"Found {len(awards)} relevant awarded grants")

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w") as f:
        json.dump(awards, f, indent=2)

    print(f"Saved to {args.output}")


if __name__ == "__main__":
    main()
