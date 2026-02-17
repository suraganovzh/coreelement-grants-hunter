"""Scrape federal grant awards from USASpending.gov.

Source: USASpending API v2 — https://api.usaspending.gov
Free, no API key needed. Covers ALL federal spending.
Best for: seeing who actually received money, amounts, and from which agency.

Runs in GitHub Actions on a weekly schedule.
"""

import argparse
import json
from datetime import datetime, timedelta
from pathlib import Path

import requests

from src.utils.logger import setup_logger

logger = setup_logger("usaspending")

BASE_URL = "https://api.usaspending.gov/api/v2"

KEYWORDS = [
    "artificial intelligence", "machine learning",
    "mining", "mineral", "geology", "exploration",
    "geospatial", "critical minerals", "lithium",
    "copper", "cobalt", "rare earth", "subsurface",
    "geological", "drilling", "remote sensing",
    "clean energy", "battery metals",
]

# NAICS codes relevant to mining/AI/geology
NAICS_CODES = [
    "213112",  # Support Activities for Oil and Gas Operations
    "213113",  # Support Activities for Coal Mining
    "213114",  # Support Activities for Metal Mining
    "213115",  # Support Activities for Nonmetallic Minerals
    "541715",  # R&D in Physical, Engineering, and Life Sciences
    "541380",  # Testing Laboratories
    "518210",  # Data Processing and Hosting (AI/ML)
    "541512",  # Computer Systems Design Services
]

# Federal agency codes
AGENCIES = {
    "DOE": "8900",    # Department of Energy
    "DOI": "1400",    # Department of Interior (USGS)
    "NSF": "4900",    # National Science Foundation
    "DOD": "9700",    # Department of Defense
    "NASA": "8000",   # NASA
    "EPA": "6800",    # EPA
    "USDA": "1200",   # Department of Agriculture
}


def search_awards_by_keyword(keyword: str, days: int = 90) -> list[dict]:
    """Search awards by keyword using the spending explorer."""
    url = f"{BASE_URL}/search/spending_by_award/"

    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)

    payload = {
        "filters": {
            "keywords": [keyword],
            "time_period": [
                {
                    "start_date": start_date.strftime("%Y-%m-%d"),
                    "end_date": end_date.strftime("%Y-%m-%d"),
                }
            ],
            "award_type_codes": ["02", "03", "04", "05"],  # Grants only
        },
        "fields": [
            "Award ID", "Recipient Name", "Start Date", "End Date",
            "Award Amount", "Awarding Agency", "Awarding Sub Agency",
            "Award Type", "Description", "recipient_id",
            "Recipient State Code", "Recipient City Name",
            "NAICS Code", "NAICS Description",
        ],
        "page": 1,
        "limit": 100,
        "sort": "Award Amount",
        "order": "desc",
    }

    try:
        response = requests.post(url, json=payload, timeout=30)
        if not response.ok:
            logger.warning("USASpending API returned %d for '%s'", response.status_code, keyword)
            return []

        data = response.json()
        return data.get("results", [])

    except Exception as e:
        logger.error("USASpending search error for '%s': %s", keyword, e)
        return []


def scrape_usaspending_awards(days: int = 90) -> list[dict]:
    """Scrape relevant grant awards from USASpending.gov.

    Args:
        days: Look back this many days.

    Returns:
        List of award dicts with standardized fields.
    """
    awards: list[dict] = []
    seen_ids: set[str] = set()

    search_terms = [
        "critical minerals",
        "mineral exploration AI",
        "geological survey technology",
        "machine learning geoscience",
        "lithium exploration",
        "rare earth mining",
        "subsurface modeling",
        "geospatial AI",
    ]

    for term in search_terms:
        results = search_awards_by_keyword(term, days)

        for r in results:
            award_id = r.get("Award ID", "")
            if not award_id or award_id in seen_ids:
                continue
            seen_ids.add(award_id)

            description = r.get("Description", "") or ""
            text = f"{description}".lower()

            amount = 0
            raw_amount = r.get("Award Amount")
            if raw_amount:
                try:
                    amount = int(float(raw_amount))
                except (ValueError, TypeError):
                    pass

            processed = {
                "id": f"usa-{award_id}",
                "title": description[:200] if description else f"Award {award_id}",
                "funder": r.get("Awarding Agency", ""),
                "funder_sub": r.get("Awarding Sub Agency", ""),
                "amount": amount,
                "winner": r.get("Recipient Name", ""),
                "winner_location": f"{r.get('Recipient City Name', '')}, {r.get('Recipient State Code', '')}".strip(", "),
                "award_date": r.get("Start Date", ""),
                "end_date": r.get("End Date", ""),
                "award_type": r.get("Award Type", ""),
                "naics_code": r.get("NAICS Code", ""),
                "naics_desc": r.get("NAICS Description", ""),
                "keywords": [kw for kw in KEYWORDS if kw in text],
                "source": "usaspending.gov",
                "scraped_at": datetime.now().isoformat(),
            }
            awards.append(processed)

        logger.info("USASpending '%s': %d results", term, len(results))

    logger.info("Total: %d awards from USASpending", len(awards))
    return awards


def main():
    parser = argparse.ArgumentParser(description="Scrape USASpending.gov awards")
    parser.add_argument("--days", type=int, default=90)
    parser.add_argument("--output", default="data/winners_usaspending.json")
    args = parser.parse_args()

    print(f"Scraping USASpending.gov awards from last {args.days} days...")
    awards = scrape_usaspending_awards(args.days)
    print(f"Found {len(awards)} relevant awards")

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w") as f:
        json.dump(awards, f, indent=2)

    print(f"Saved to {args.output}")

    # Print summary by agency
    agencies = {}
    for a in awards:
        agency = a.get("funder", "Unknown")
        agencies[agency] = agencies.get(agency, 0) + 1
    if agencies:
        print("\nBy agency:")
        for agency, count in sorted(agencies.items(), key=lambda x: -x[1])[:10]:
            print(f"  {agency}: {count}")

    # Print top recipients
    recipients = {}
    for a in awards:
        name = a.get("winner", "Unknown")
        recipients[name] = recipients.get(name, 0) + a.get("amount", 0)
    if recipients:
        print("\nTop recipients by total amount:")
        for name, total in sorted(recipients.items(), key=lambda x: -x[1])[:10]:
            print(f"  {name}: ${total:,}")


if __name__ == "__main__":
    main()
