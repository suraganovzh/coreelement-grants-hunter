"""Scrape SBIR/STTR awarded grants from sbir.gov.

Runs in GitHub Actions on a weekly schedule.
Source: https://www.sbir.gov/api/awards.json
"""

import argparse
import json
from datetime import datetime, timedelta
from pathlib import Path

import requests

from src.utils.logger import setup_logger

logger = setup_logger("sbir_awards")

AGENCIES = ["DOE", "NSF", "DOD", "NASA", "USDA", "DOI", "EPA"]

KEYWORDS = [
    "ai", "artificial intelligence", "machine learning",
    "mining", "mineral", "geology", "exploration",
    "geospatial", "critical minerals", "lithium",
    "copper", "cobalt", "rare earth", "subsurface",
    "geological", "drilling", "remote sensing",
    "clean energy", "battery",
]


def scrape_sbir_awards(phase: int = 1, days: int = 30) -> list[dict]:
    """Scrape SBIR/STTR awards from sbir.gov API."""
    url = "https://www.sbir.gov/api/awards.json"
    awards: list[dict] = []

    for agency in AGENCIES:
        try:
            params = {
                "agency": agency,
                "rows": 200,
            }
            if phase in (1, 2):
                params["phase"] = phase

            response = requests.get(url, params=params, timeout=30)
            if not response.ok:
                logger.warning("SBIR API returned %d for %s", response.status_code, agency)
                continue

            data = response.json()
            if not isinstance(data, list):
                data = data.get("results", []) if isinstance(data, dict) else []

            for award in data:
                title = award.get("title", "") or award.get("award_title", "")
                abstract = award.get("abstract", "") or ""
                text = f"{title} {abstract}".lower()

                if not any(kw in text for kw in KEYWORDS):
                    continue

                processed = {
                    "id": str(award.get("award_id", award.get("id", ""))),
                    "title": title,
                    "funder": f"{agency} SBIR Phase {phase}",
                    "agency": agency,
                    "phase": phase,
                    "amount": award.get("award_amount", 0),
                    "winner": award.get("company", "") or award.get("firm", ""),
                    "winner_location": f"{award.get('city', '')}, {award.get('state', '')}".strip(", "),
                    "abstract": abstract[:2000],
                    "award_date": award.get("award_date", "") or award.get("date", ""),
                    "keywords": [kw for kw in KEYWORDS if kw in text],
                    "source": "sbir.gov",
                    "scraped_at": datetime.now().isoformat(),
                }
                awards.append(processed)

            logger.info("[%s] Found %d relevant Phase %d awards", agency, len([a for a in awards if a["agency"] == agency]), phase)

        except Exception as e:
            logger.error("Error scraping SBIR awards for %s: %s", agency, e)

    logger.info("Total: %d relevant SBIR Phase %d awards", len(awards), phase)
    return awards


def main():
    parser = argparse.ArgumentParser(description="Scrape SBIR/STTR awards")
    parser.add_argument("--phase", type=int, default=1, choices=[1, 2])
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--output", default="data/winners_sbir.json")
    args = parser.parse_args()

    print(f"Scraping SBIR Phase {args.phase} awards...")
    awards = scrape_sbir_awards(args.phase, args.days)
    print(f"Found {len(awards)} relevant awards")

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w") as f:
        json.dump(awards, f, indent=2)

    print(f"Saved to {args.output}")


if __name__ == "__main__":
    main()
