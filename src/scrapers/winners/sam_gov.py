"""Scrape federal contract/grant opportunities from SAM.gov.

Source: SAM.gov Entity/Opportunities API
Free, requires API key from https://sam.gov/content/entity-information

SAM.gov is the official source for federal procurement and grant opportunities.
Useful for: finding who gets contracts, active opportunities, and federal grantors.

Runs in GitHub Actions on a weekly schedule.
"""

import argparse
import json
import os
from datetime import datetime, timedelta
from pathlib import Path

import requests

from src.utils.logger import setup_logger

logger = setup_logger("sam_gov")

BASE_URL = "https://api.sam.gov/opportunities/v2/search"

KEYWORDS = [
    "artificial intelligence", "machine learning",
    "mining", "mineral", "geology", "exploration",
    "geospatial", "critical minerals", "lithium",
    "copper", "cobalt", "rare earth", "subsurface",
    "geological", "drilling", "remote sensing",
    "clean energy", "battery", "geothermal",
    "SBIR", "STTR",
]

# NAICS codes for mining/tech
NAICS_CODES = [
    "213114",  # Support Activities for Metal Mining
    "541715",  # R&D in Physical/Engineering Sciences
    "541512",  # Computer Systems Design
    "541380",  # Testing Laboratories
]


def scrape_sam_opportunities(days: int = 30) -> list[dict]:
    """Scrape grant/contract opportunities from SAM.gov.

    Args:
        days: Look back this many days.

    Returns:
        List of opportunity dicts.
    """
    api_key = os.getenv("SAM_GOV_API_KEY", "")
    if not api_key:
        logger.warning("SAM_GOV_API_KEY not set - using public search (limited)")
        return _scrape_sam_public(days)

    awards: list[dict] = []
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)

    for naics in NAICS_CODES:
        try:
            params = {
                "api_key": api_key,
                "postedFrom": start_date.strftime("%m/%d/%Y"),
                "postedTo": end_date.strftime("%m/%d/%Y"),
                "naics": naics,
                "limit": 100,
                "offset": 0,
            }

            response = requests.get(BASE_URL, params=params, timeout=30)
            if not response.ok:
                logger.warning("SAM.gov API returned %d for NAICS %s", response.status_code, naics)
                continue

            data = response.json()
            opportunities = data.get("opportunitiesData", [])

            for opp in opportunities:
                title = opp.get("title", "")
                desc = opp.get("description", "") or ""
                text = f"{title} {desc}".lower()

                if not any(kw.lower() in text for kw in KEYWORDS):
                    continue

                awards.append({
                    "id": f"sam-{opp.get('noticeId', '')}",
                    "title": title,
                    "funder": opp.get("fullParentPathName", "") or opp.get("department", ""),
                    "funder_sub": opp.get("subtierAgency", ""),
                    "amount": 0,  # SAM doesn't always show amounts
                    "type": opp.get("type", ""),
                    "set_aside": opp.get("typeOfSetAsideDescription", ""),
                    "naics_code": naics,
                    "description": desc[:2000],
                    "posted_date": opp.get("postedDate", ""),
                    "response_deadline": opp.get("responseDeadLine", ""),
                    "url": opp.get("uiLink", ""),
                    "keywords": [kw for kw in KEYWORDS if kw.lower() in text],
                    "source": "sam.gov",
                    "scraped_at": datetime.now().isoformat(),
                })

            logger.info("SAM.gov NAICS %s: %d opportunities, %d relevant", naics, len(opportunities), len([a for a in awards if a.get("naics_code") == naics]))

        except Exception as e:
            logger.error("SAM.gov error for NAICS %s: %s", naics, e)

    logger.info("Total: %d relevant SAM.gov opportunities", len(awards))
    return awards


def _scrape_sam_public(days: int) -> list[dict]:
    """Fallback: scrape SAM.gov via public search (no API key)."""
    awards: list[dict] = []

    search_terms = [
        "critical minerals AI",
        "mineral exploration technology",
        "geological AI",
        "mining SBIR",
    ]

    for term in search_terms:
        try:
            params = {
                "q": term,
                "index": "opp",
                "page": 0,
                "size": 25,
                "mode": "search",
                "is_active": "true",
            }
            url = "https://sam.gov/api/prod/sgs/v1/search/"
            response = requests.get(url, params=params, timeout=30)
            if not response.ok:
                continue

            data = response.json()
            results = data.get("_embedded", {}).get("results", [])

            for r in results:
                title = r.get("title", "")
                desc = r.get("description", "") or ""

                awards.append({
                    "id": f"sam-pub-{r.get('_id', '')}",
                    "title": title,
                    "funder": r.get("organizationHierarchy", [{}])[0].get("name", "") if r.get("organizationHierarchy") else "",
                    "description": desc[:2000],
                    "type": r.get("type", ""),
                    "posted_date": r.get("modifiedDate", ""),
                    "keywords": [kw for kw in KEYWORDS if kw.lower() in f"{title} {desc}".lower()],
                    "source": "sam.gov_public",
                    "scraped_at": datetime.now().isoformat(),
                })

        except Exception as e:
            logger.debug("SAM.gov public search '%s' failed: %s", term, e)

    return awards


def main():
    parser = argparse.ArgumentParser(description="Scrape SAM.gov opportunities")
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--output", default="data/winners_sam.json")
    args = parser.parse_args()

    print(f"Scraping SAM.gov from last {args.days} days...")
    awards = scrape_sam_opportunities(args.days)
    print(f"Found {len(awards)} relevant opportunities")

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w") as f:
        json.dump(awards, f, indent=2)

    print(f"Saved to {args.output}")

    # Print summary
    funders = {}
    for a in awards:
        f = a.get("funder", "Unknown")
        funders[f] = funders.get(f, 0) + 1
    if funders:
        print("\nBy funder/agency:")
        for f, count in sorted(funders.items(), key=lambda x: -x[1])[:10]:
            print(f"  {f}: {count}")


if __name__ == "__main__":
    main()
