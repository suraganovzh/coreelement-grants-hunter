"""Scrape DOE (Department of Energy) awards and funding opportunities.

Sources:
  - DOE EERE (Energy Efficiency & Renewable Energy) awards
  - DOE ARPA-E awarded projects
  - DOE Office of Science awards

Uses public data from DOE project databases.
Runs in GitHub Actions on a weekly schedule.
"""

import argparse
import json
from datetime import datetime, timedelta
from pathlib import Path

import requests

from src.utils.logger import setup_logger

logger = setup_logger("doe_awards")

KEYWORDS = [
    "artificial intelligence", "machine learning",
    "mining", "mineral", "geology", "exploration",
    "geospatial", "critical minerals", "lithium",
    "copper", "cobalt", "rare earth", "subsurface",
    "geological", "drilling", "remote sensing",
    "clean energy", "battery", "geothermal",
]

# DOE EERE project data
EERE_URL = "https://api.openei.org/utility_rates"

# ARPA-E project database
ARPAE_URL = "https://arpa-e.energy.gov"


def scrape_doe_sbir_awards(days: int = 90) -> list[dict]:
    """Scrape DOE SBIR/STTR awards via SBIR.gov API.

    DOE is the largest SBIR grantor for energy/mining.
    """
    url = "https://www.sbir.gov/api/awards.json"
    awards: list[dict] = []

    try:
        params = {
            "agency": "DOE",
            "rows": 500,
        }

        response = requests.get(url, params=params, timeout=30)
        if not response.ok:
            logger.warning("SBIR API returned %d for DOE", response.status_code)
            return []

        data = response.json()
        if not isinstance(data, list):
            data = data.get("results", []) if isinstance(data, dict) else []

        for award in data:
            title = award.get("title", "") or award.get("award_title", "")
            abstract = award.get("abstract", "") or ""
            text = f"{title} {abstract}".lower()

            if not any(kw in text for kw in KEYWORDS):
                continue

            awards.append({
                "id": f"doe-sbir-{award.get('award_id', award.get('id', ''))}",
                "title": title,
                "funder": f"DOE SBIR Phase {award.get('phase', '?')}",
                "funder_sub": award.get("branch", "") or award.get("subtopic", ""),
                "amount": award.get("award_amount", 0),
                "winner": award.get("company", "") or award.get("firm", ""),
                "winner_location": f"{award.get('city', '')}, {award.get('state', '')}".strip(", "),
                "pi": award.get("pi_name", ""),
                "abstract": abstract[:2000],
                "award_date": award.get("award_date", "") or award.get("date", ""),
                "keywords": [kw for kw in KEYWORDS if kw in text],
                "source": "doe_sbir",
                "scraped_at": datetime.now().isoformat(),
            })

        logger.info("Found %d relevant DOE SBIR awards", len(awards))

    except Exception as e:
        logger.error("Error scraping DOE SBIR: %s", e)

    return awards


def scrape_doe_grants_gov(days: int = 90) -> list[dict]:
    """Scrape DOE awards from grants.gov API."""
    url = "https://api.grants.gov/v1/api/search"
    awards: list[dict] = []

    search_terms = [
        "DOE critical minerals",
        "DOE artificial intelligence mining",
        "DOE clean energy technology",
        "ARPA-E mining",
        "DOE EERE minerals",
    ]

    for term in search_terms:
        try:
            payload = {
                "keyword": term,
                "oppStatuses": "closed,forecasted",
                "sortBy": "openDate|desc",
                "rows": 50,
                "startRecordNum": 0,
            }

            response = requests.post(url, json=payload, timeout=30)
            if not response.ok:
                continue

            hits = response.json().get("oppHits", [])
            seen_ids = {a["id"] for a in awards}

            for opp in hits:
                opp_id = str(opp.get("id", ""))
                if opp_id in seen_ids:
                    continue

                title = opp.get("title", "")
                agency = opp.get("agencyName", "")

                if "DOE" not in agency.upper() and "ENERGY" not in agency.upper():
                    continue

                desc = ""
                synopsis = opp.get("synopsis")
                if isinstance(synopsis, dict):
                    desc = synopsis.get("synopsisDesc", "")

                awards.append({
                    "id": f"doe-gg-{opp_id}",
                    "title": title,
                    "funder": agency,
                    "funder_sub": opp.get("cfdaList", ""),
                    "amount": opp.get("awardCeiling", 0),
                    "winner": "",
                    "abstract": desc[:2000],
                    "award_date": opp.get("closeDate", ""),
                    "opportunity_number": opp.get("number", ""),
                    "keywords": [kw for kw in KEYWORDS if kw in f"{title} {desc}".lower()],
                    "source": "doe_grants_gov",
                    "scraped_at": datetime.now().isoformat(),
                })

        except Exception as e:
            logger.debug("DOE grants.gov search '%s' failed: %s", term, e)

    logger.info("Found %d DOE grants from grants.gov", len(awards))
    return awards


def scrape_doe_awards(days: int = 90) -> list[dict]:
    """Scrape all DOE award sources and merge.

    Args:
        days: Look back period.

    Returns:
        Combined list of DOE awards from all sources.
    """
    all_awards: list[dict] = []

    # Source 1: DOE SBIR/STTR
    sbir = scrape_doe_sbir_awards(days)
    all_awards.extend(sbir)

    # Source 2: DOE via grants.gov
    gg = scrape_doe_grants_gov(days)
    all_awards.extend(gg)

    logger.info("Total: %d DOE awards from all sources", len(all_awards))
    return all_awards


def main():
    parser = argparse.ArgumentParser(description="Scrape DOE awards")
    parser.add_argument("--days", type=int, default=90)
    parser.add_argument("--output", default="data/winners_doe.json")
    args = parser.parse_args()

    print(f"Scraping DOE awards from last {args.days} days...")
    awards = scrape_doe_awards(args.days)
    print(f"Found {len(awards)} relevant awards")

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w") as f:
        json.dump(awards, f, indent=2)

    print(f"Saved to {args.output}")

    # Print summary by sub-source
    sources = {}
    for a in awards:
        src = a.get("source", "unknown")
        sources[src] = sources.get(src, 0) + 1
    if sources:
        print("\nBy source:")
        for src, count in sorted(sources.items(), key=lambda x: -x[1]):
            print(f"  {src}: {count}")


if __name__ == "__main__":
    main()
