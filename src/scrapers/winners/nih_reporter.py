"""Scrape NIH RePORTER for awarded grants.

Source: NIH RePORTER API v2 — https://api.reporter.nih.gov
Free, no API key needed. Covers all NIH-funded research.
Useful for: biomedical AI, environmental health, and cross-agency grants.

Runs in GitHub Actions on a weekly schedule.
"""

import argparse
import json
from datetime import datetime
from pathlib import Path

import requests

from src.utils.logger import setup_logger

logger = setup_logger("nih_reporter")

BASE_URL = "https://api.reporter.nih.gov/v2/projects/search"

KEYWORDS = [
    "artificial intelligence", "machine learning",
    "environmental health", "exposure science",
    "geospatial", "critical minerals", "mining",
    "geological", "remote sensing", "earth science",
    "predictive modeling", "data science",
]


def scrape_nih_awards(fiscal_year: int | None = None) -> list[dict]:
    """Scrape awarded grants from NIH RePORTER.

    Args:
        fiscal_year: Fiscal year to search. Defaults to current year.

    Returns:
        List of award dicts with standardized fields.
    """
    if fiscal_year is None:
        fiscal_year = datetime.now().year

    awards: list[dict] = []
    seen_ids: set[str] = set()

    search_terms = [
        "artificial intelligence geological",
        "machine learning mineral",
        "geospatial predictive modeling",
        "mining environmental AI",
        "critical minerals health",
        "subsurface prediction",
    ]

    for term in search_terms:
        try:
            payload = {
                "criteria": {
                    "advanced_text_search": {
                        "operator": "and",
                        "search_field": "projecttitle,terms",
                        "search_text": term,
                    },
                    "fiscal_years": [fiscal_year],
                    "exclude_subprojects": True,
                },
                "offset": 0,
                "limit": 50,
                "sort_field": "AwardAmount",
                "sort_order": "desc",
            }

            response = requests.post(BASE_URL, json=payload, timeout=30)
            if not response.ok:
                logger.warning("NIH API returned %d for '%s'", response.status_code, term)
                continue

            data = response.json()
            results = data.get("results", [])

            for project in results:
                project_num = project.get("project_num", "")
                if not project_num or project_num in seen_ids:
                    continue
                seen_ids.add(project_num)

                title = project.get("project_title", "")
                abstract = project.get("abstract_text", "") or ""
                text = f"{title} {abstract}".lower()

                if not any(kw in text for kw in KEYWORDS):
                    continue

                # Extract PI info
                pi_info = project.get("principal_investigators", [])
                pi_name = ""
                if pi_info:
                    pi = pi_info[0]
                    pi_name = f"{pi.get('first_name', '')} {pi.get('last_name', '')}".strip()

                # Extract org info
                org = project.get("organization", {}) or {}

                amount = project.get("award_amount", 0) or 0

                # Agency/IC info
                agency_info = project.get("agency_ic_admin", {}) or {}
                ic_name = agency_info.get("name", "")

                processed = {
                    "id": f"nih-{project_num}",
                    "title": title,
                    "funder": f"NIH {ic_name}".strip(),
                    "funder_program": project.get("activity_code", ""),
                    "amount": amount,
                    "winner": org.get("org_name", ""),
                    "winner_location": f"{org.get('org_city', '')}, {org.get('org_state', '')}".strip(", "),
                    "pi": pi_name,
                    "abstract": abstract[:2000],
                    "award_date": project.get("award_notice_date", ""),
                    "start_date": project.get("project_start_date", ""),
                    "end_date": project.get("project_end_date", ""),
                    "fiscal_year": fiscal_year,
                    "keywords": [kw for kw in KEYWORDS if kw in text],
                    "source": "nih_reporter",
                    "scraped_at": datetime.now().isoformat(),
                }
                awards.append(processed)

            logger.info("NIH search '%s': %d results", term, len(results))

        except Exception as e:
            logger.error("Error searching NIH for '%s': %s", term, e)

    logger.info("Total: %d relevant NIH awards", len(awards))
    return awards


def main():
    parser = argparse.ArgumentParser(description="Scrape NIH RePORTER awards")
    parser.add_argument("--year", type=int, default=None, help="Fiscal year (default: current)")
    parser.add_argument("--output", default="data/winners_nih.json")
    args = parser.parse_args()

    year = args.year or datetime.now().year
    print(f"Scraping NIH awards for FY{year}...")
    awards = scrape_nih_awards(year)
    print(f"Found {len(awards)} relevant awards")

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w") as f:
        json.dump(awards, f, indent=2)

    print(f"Saved to {args.output}")

    # Print summary by IC
    ics = {}
    for a in awards:
        ic = a.get("funder", "Unknown")
        ics[ic] = ics.get(ic, 0) + 1
    if ics:
        print("\nBy NIH Institute/Center:")
        for ic, count in sorted(ics.items(), key=lambda x: -x[1])[:10]:
            print(f"  {ic}: {count}")


if __name__ == "__main__":
    main()
