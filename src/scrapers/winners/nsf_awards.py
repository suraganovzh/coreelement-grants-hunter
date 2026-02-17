"""Scrape NSF (National Science Foundation) awarded grants.

Source: NSF Award Search API — https://api.nsf.gov/services/v1/awards.json
Free, no API key needed. Covers all NSF directorates.

Runs in GitHub Actions on a weekly schedule.
"""

import argparse
import json
from datetime import datetime, timedelta
from pathlib import Path

import requests

from src.utils.logger import setup_logger

logger = setup_logger("nsf_awards")

KEYWORDS = [
    "artificial intelligence", "machine learning", "deep learning",
    "mining", "mineral", "geology", "exploration",
    "geospatial", "remote sensing", "critical minerals",
    "lithium", "copper", "cobalt", "rare earth",
    "geological survey", "subsurface", "geophysics",
    "clean energy", "battery", "earth science",
]

BASE_URL = "https://api.nsf.gov/services/v1/awards.json"


def scrape_nsf_awards(days: int = 90) -> list[dict]:
    """Scrape awarded grants from NSF API.

    Args:
        days: Look back this many days for awards.

    Returns:
        List of award dicts with standardized fields.
    """
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)

    awards: list[dict] = []
    seen_ids: set[str] = set()

    search_terms = [
        "critical minerals AI",
        "machine learning geology",
        "mineral exploration",
        "geospatial artificial intelligence",
        "subsurface modeling",
        "mining technology",
        "lithium exploration",
        "rare earth elements",
    ]

    for term in search_terms:
        try:
            params = {
                "keyword": term,
                "dateStart": start_date.strftime("%m/%d/%Y"),
                "dateEnd": end_date.strftime("%m/%d/%Y"),
                "printFields": (
                    "id,title,agency,awardeeCity,awardeeStateCode,"
                    "awardeeName,piFirstName,piLastName,date,startDate,"
                    "expDate,estimatedTotalAmt,fundsObligatedAmt,"
                    "abstractText,fundProgramName,primaryProgram"
                ),
                "offset": 1,
                "rpp": 100,
            }

            response = requests.get(BASE_URL, params=params, timeout=30)
            if not response.ok:
                logger.warning("NSF API returned %d for '%s'", response.status_code, term)
                continue

            data = response.json()
            results = data.get("response", {}).get("award", [])

            for award in results:
                award_id = str(award.get("id", ""))
                if not award_id or award_id in seen_ids:
                    continue
                seen_ids.add(award_id)

                title = award.get("title", "")
                abstract = award.get("abstractText", "")
                text = f"{title} {abstract}".lower()

                if not any(kw in text for kw in KEYWORDS):
                    continue

                amount = 0
                for field in ("estimatedTotalAmt", "fundsObligatedAmt"):
                    val = award.get(field, "")
                    if val:
                        try:
                            amount = int(str(val).replace(",", "").replace("$", ""))
                            break
                        except ValueError:
                            pass

                pi_name = f"{award.get('piFirstName', '')} {award.get('piLastName', '')}".strip()

                processed = {
                    "id": f"nsf-{award_id}",
                    "title": title,
                    "funder": "NSF",
                    "funder_program": award.get("fundProgramName", "") or award.get("primaryProgram", ""),
                    "amount": amount,
                    "winner": award.get("awardeeName", ""),
                    "winner_location": f"{award.get('awardeeCity', '')}, {award.get('awardeeStateCode', '')}".strip(", "),
                    "pi": pi_name,
                    "abstract": abstract[:2000],
                    "award_date": award.get("date", ""),
                    "start_date": award.get("startDate", ""),
                    "end_date": award.get("expDate", ""),
                    "keywords": [kw for kw in KEYWORDS if kw in text],
                    "source": "nsf.gov",
                    "scraped_at": datetime.now().isoformat(),
                }
                awards.append(processed)

            logger.info("NSF search '%s': %d results, %d relevant", term, len(results), len([a for a in awards if a["id"].startswith("nsf-")]))

        except Exception as e:
            logger.error("Error searching NSF for '%s': %s", term, e)

    logger.info("Total: %d relevant NSF awards", len(awards))
    return awards


def main():
    parser = argparse.ArgumentParser(description="Scrape NSF awarded grants")
    parser.add_argument("--days", type=int, default=90)
    parser.add_argument("--output", default="data/winners_nsf.json")
    args = parser.parse_args()

    print(f"Scraping NSF awards from last {args.days} days...")
    awards = scrape_nsf_awards(args.days)
    print(f"Found {len(awards)} relevant awards")

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w") as f:
        json.dump(awards, f, indent=2)

    print(f"Saved to {args.output}")

    # Print summary
    funders = {}
    for a in awards:
        prog = a.get("funder_program", "Unknown")
        funders[prog] = funders.get(prog, 0) + 1
    if funders:
        print("\nBy program:")
        for prog, count in sorted(funders.items(), key=lambda x: -x[1])[:10]:
            print(f"  {prog}: {count}")


if __name__ == "__main__":
    main()
