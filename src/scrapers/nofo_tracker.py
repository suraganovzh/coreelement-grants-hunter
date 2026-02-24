"""Track Notices of Intent (NOI) for upcoming NOFOs.

These are "prepare now" opportunities — grants where the NOI has been
released but the full NOFO is pending. Critical for early preparation.
"""

import argparse
import json
from datetime import datetime
from pathlib import Path

from src.scrapers.base_scraper import BaseScraper, GrantResult
from src.utils.logger import setup_logger

logger = setup_logger("nofo_tracker")

# Sources for NOI/NOFO pipeline tracking
NOI_SOURCES = [
    {
        "name": "DOE EERE Funding",
        "url": "https://www.energy.gov/eere/funding/funding-opportunities",
        "funder": "DOE EERE",
    },
    {
        "name": "ARPA-E FOAs",
        "url": "https://arpa-e-foa.energy.gov/",
        "funder": "ARPA-E",
    },
    {
        "name": "DOE MESC",
        "url": "https://www.energy.gov/mesc/office-manufacturing-and-energy-supply-chains",
        "funder": "DOE MESC",
    },
]

# Manually tracked imminent grants where NOI was released
KNOWN_IMMINENT_GRANTS = [
    {
        "title": "DOE Battery Materials Processing NOFO",
        "funder": "DOE MESC",
        "description": (
            "Department of Energy Manufacturing and Energy Supply Chains "
            "office funding for battery materials processing and critical "
            "mineral supply chain development. NOI released August 2025, "
            "full NOFO expected Q2 2026. Relevant for AI-driven mineral "
            "exploration and processing optimization."
        ),
        "amount_min": 50000000,
        "amount_max": 200000000,
        "currency": "USD",
        "status": "NOFO_PENDING",
        "expected_release": "2026-Q2",
        "noi_date": "2025-08-13",
        "prepare_now": True,
        "url": "https://www.energy.gov/mesc/office-manufacturing-and-energy-supply-chains",
        "source": "nofo_pipeline",
        "grant_type": "federal",
        "industry_tags": [
            "battery materials", "critical minerals", "supply chain",
            "manufacturing", "mineral processing",
        ],
        "eligibility_text": (
            "Open to US entities. Small businesses, universities, "
            "national labs, and consortia eligible."
        ),
        "preparation_steps": [
            "Draft concept paper focused on AI for mineral exploration",
            "Identify DOE national lab partners (e.g., Lawrence Berkeley)",
            "Prepare budget for $5-20M sub-award",
            "Align with DOE critical minerals priority list",
        ],
    },
    {
        "title": "ARPA-E Critical Minerals Discovery Program",
        "funder": "ARPA-E",
        "description": (
            "ARPA-E program for transformative approaches to critical "
            "minerals discovery and extraction. Expected to fund novel "
            "AI/ML approaches to geological exploration."
        ),
        "amount_min": 1000000,
        "amount_max": 10000000,
        "currency": "USD",
        "status": "ANTICIPATED",
        "expected_release": "2026-Q2",
        "prepare_now": True,
        "url": "https://arpa-e-foa.energy.gov/",
        "source": "nofo_pipeline",
        "grant_type": "federal",
        "industry_tags": [
            "critical minerals", "AI", "discovery", "exploration",
            "transformative technology",
        ],
        "eligibility_text": "Open to US entities. High-risk high-reward research.",
        "preparation_steps": [
            "Prepare ARPA-E concept paper template",
            "Quantify technology performance metrics",
            "Document TRL advancement pathway",
        ],
    },
]


class NOFOTracker(BaseScraper):
    """Track NOIs and upcoming NOFOs for early preparation.

    Monitors DOE, ARPA-E, and other agencies for Notices of Intent
    that signal upcoming funding opportunities.
    """

    def __init__(self):
        super().__init__(rate_limit_calls=5, rate_limit_period=60)

    @property
    def name(self) -> str:
        return "nofo_pipeline"

    def search(self, keywords: list[str] | None = None) -> list[GrantResult]:
        """Search for upcoming NOFOs and NOIs."""
        all_results: list[GrantResult] = []

        # Scrape agency pages for NOI announcements
        for source in NOI_SOURCES:
            try:
                results = self._scrape_noi_source(source)
                all_results.extend(results)
                logger.info("[nofo] %s: found %d items", source["name"], len(results))
            except Exception as e:
                logger.error("[nofo] Error scraping %s: %s", source["name"], e)

        logger.info("[nofo] Total scraped: %d items", len(all_results))
        return all_results

    def _scrape_noi_source(self, source: dict) -> list[GrantResult]:
        """Scrape a single NOI source page."""
        results: list[GrantResult] = []

        try:
            response = self._fetch(source["url"])
            soup = self._parse_html(response.text)

            items = soup.select(
                "article, .card, .funding-item, .opportunity-item, "
                "tr, .list-item, section, .content-block"
            )

            for item in items[:30]:
                try:
                    title_el = item.select_one("h2, h3, h4, a, .title, td:first-child")
                    if not title_el:
                        continue

                    title = title_el.get_text(strip=True)
                    if not title or len(title) < 10:
                        continue

                    text = item.get_text(separator=" ", strip=True).lower()

                    # Look for NOI/NOFO/anticipated language
                    noi_terms = [
                        "notice of intent", "noi", "anticipated",
                        "upcoming", "nofo", "planned", "expected",
                        "pre-announcement", "draft",
                    ]
                    # Also look for relevant topic terms
                    topic_terms = [
                        "mineral", "critical", "battery", "mining",
                        "energy", "clean", "ai", "technology",
                    ]

                    has_noi = any(term in text for term in noi_terms)
                    has_topic = any(term in text for term in topic_terms)

                    if not (has_noi and has_topic):
                        continue

                    link_el = item.select_one("a[href]")
                    url = source["url"]
                    if link_el:
                        href = link_el.get("href", "")
                        if href.startswith("http"):
                            url = href
                        elif href.startswith("/"):
                            from urllib.parse import urljoin
                            url = urljoin(source["url"], href)

                    desc_el = item.select_one("p, .description, .summary")
                    description = desc_el.get_text(strip=True) if desc_el else ""

                    from src.utils.text_processor import TextProcessor
                    amount_min, amount_max, currency = TextProcessor.extract_amount(text)

                    results.append(GrantResult(
                        title=f"[UPCOMING] {title}",
                        funder=source["funder"],
                        description=description,
                        amount_min=amount_min,
                        amount_max=amount_max,
                        currency=currency or "USD",
                        deadline=None,  # No deadline yet for upcoming NOFOs
                        url=url,
                        source="nofo_pipeline",
                        grant_type="federal",
                        industry_tags=["upcoming", "prepare_now"],
                    ))

                except Exception as e:
                    logger.debug("[nofo] Error parsing item: %s", e)

        except Exception as e:
            logger.warning("[nofo] Failed to fetch %s: %s", source["url"], e)

        return results

    @staticmethod
    def get_known_imminent() -> list[dict]:
        """Return known imminent grants from manual tracking."""
        return KNOWN_IMMINENT_GRANTS


def main():
    parser = argparse.ArgumentParser(description="Track upcoming NOFOs")
    parser.add_argument("--output", default="data/nofo_pipeline.json")
    args = parser.parse_args()

    # Combine scraped and known imminent grants
    all_grants: list[dict] = []

    # Add known imminent grants
    for grant in KNOWN_IMMINENT_GRANTS:
        grant["scraped_at"] = datetime.now().isoformat()
        grant["last_verified"] = datetime.now().isoformat()
        all_grants.append(grant)

    # Scrape for new NOIs
    try:
        with NOFOTracker() as tracker:
            results = tracker.search()
            for r in results:
                all_grants.append({
                    "title": r.title,
                    "funder": r.funder,
                    "description": r.description,
                    "amount_min": r.amount_min,
                    "amount_max": r.amount_max,
                    "currency": r.currency,
                    "deadline": "",
                    "url": r.url,
                    "source": r.source,
                    "grant_type": r.grant_type,
                    "industry_tags": r.industry_tags,
                    "status": "ANTICIPATED",
                    "prepare_now": True,
                    "scraped_at": datetime.now().isoformat(),
                })
    except Exception as e:
        logger.error("NOFO tracker scraping failed: %s", e)

    output = {
        "metadata": {
            "updated_at": datetime.now().isoformat(),
            "total_imminent": len(all_grants),
            "description": "Upcoming NOFOs and NOIs — prepare now opportunities",
        },
        "grants": all_grants,
    }

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w") as f:
        json.dump(output, f, indent=2)

    print(f"NOFO tracker: {len(all_grants)} imminent grants saved to {args.output}")


if __name__ == "__main__":
    main()
