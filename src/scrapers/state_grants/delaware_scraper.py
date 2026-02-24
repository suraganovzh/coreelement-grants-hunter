"""Delaware Division of Small Business grant scraper.

Focus: EDGE Grant (STEM Track) and related programs.
Delaware is priority because Core Element AI is incorporated there.
"""

import argparse
import json
from datetime import datetime
from pathlib import Path

from src.scrapers.base_scraper import BaseScraper, GrantResult
from src.utils.logger import setup_logger

logger = setup_logger("delaware_scraper")

DELAWARE_SOURCES = [
    {
        "name": "Delaware EDGE Grant",
        "url": "https://business.delaware.gov/edge-grants/",
        "backup_url": "https://business.delaware.gov/",
        "funder": "Delaware Division of Small Business",
        "focus": ["STEM", "technology", "innovation"],
    },
    {
        "name": "Delaware Strategic Fund",
        "url": "https://business.delaware.gov/incentives/delaware-strategic-fund/",
        "funder": "Delaware Economic Development Office",
        "focus": ["economic development", "business growth"],
    },
]


class DelawareScraper(BaseScraper):
    """Scraper for Delaware state grant programs.

    Focuses on EDGE Grant STEM Track, relevant for tech startups
    incorporated in Delaware.
    """

    def __init__(self):
        super().__init__(rate_limit_calls=5, rate_limit_period=60)

    @property
    def name(self) -> str:
        return "delaware_state"

    def search(self, keywords: list[str] | None = None) -> list[GrantResult]:
        """Scrape Delaware state grant programs."""
        all_results: list[GrantResult] = []

        for source in DELAWARE_SOURCES:
            try:
                results = self._scrape_source(source)
                all_results.extend(results)
                logger.info("[delaware] %s: found %d grants", source["name"], len(results))
            except Exception as e:
                logger.error("[delaware] Error scraping %s: %s", source["name"], e)

        all_results.extend(self._known_active_programs())

        logger.info("[delaware] Total: %d grants", len(all_results))
        return all_results

    def _scrape_source(self, source: dict) -> list[GrantResult]:
        """Scrape a single Delaware source page."""
        results: list[GrantResult] = []

        urls_to_try = [source["url"]]
        if "backup_url" in source:
            urls_to_try.append(source["backup_url"])

        for url in urls_to_try:
            try:
                response = self._fetch(url)
                soup = self._parse_html(response.text)

                items = soup.select("article, .card, .content-block, section, .wp-block-group")
                for item in items[:30]:
                    try:
                        title_el = item.select_one("h2, h3, h4, .title")
                        if not title_el:
                            continue

                        title = title_el.get_text(strip=True)
                        if not title or len(title) < 5:
                            continue

                        text = item.get_text(separator=" ", strip=True).lower()
                        relevant = ["grant", "funding", "award", "edge", "stem", "innovation", "apply"]
                        if not any(term in text for term in relevant):
                            continue

                        link_el = item.select_one("a[href]")
                        grant_url = url
                        if link_el:
                            href = link_el.get("href", "")
                            if href.startswith("http"):
                                grant_url = href
                            elif href.startswith("/"):
                                from urllib.parse import urljoin
                                grant_url = urljoin(url, href)

                        desc_el = item.select_one("p, .description")
                        description = desc_el.get_text(strip=True) if desc_el else ""

                        from src.utils.text_processor import TextProcessor
                        amount_min, amount_max, currency = TextProcessor.extract_amount(text)
                        deadline_str = TextProcessor.extract_deadline(text)
                        deadline = None
                        if deadline_str:
                            from src.utils.date_utils import DateUtils
                            deadline = DateUtils.parse_date(deadline_str)

                        results.append(GrantResult(
                            title=title,
                            funder=source["funder"],
                            description=description,
                            amount_min=amount_min,
                            amount_max=amount_max,
                            currency=currency or "USD",
                            deadline=deadline,
                            url=grant_url,
                            source="delaware_state",
                            grant_type="state",
                            industry_tags=source.get("focus", []),
                        ))

                    except Exception as e:
                        logger.debug("[delaware] Error parsing item: %s", e)

                if results:
                    break

            except Exception as e:
                logger.warning("[delaware] Failed to fetch %s: %s", url, e)

        return results

    def _known_active_programs(self) -> list[GrantResult]:
        """Return known active Delaware grant programs."""
        return [
            GrantResult(
                title="Delaware EDGE Grant - STEM Track",
                funder="Delaware Division of Small Business",
                description=(
                    "Encouraging Development, Growth, and Expansion (EDGE) Grants "
                    "for STEM-focused businesses. Supports technology companies "
                    "incorporated in Delaware with growth capital."
                ),
                amount_min=5000,
                amount_max=100000,
                currency="USD",
                deadline=None,
                url="https://business.delaware.gov/edge-grants/",
                source="delaware_state",
                grant_type="state",
                industry_tags=["STEM", "technology", "innovation"],
                eligibility_text=(
                    "Must be incorporated in Delaware. Small business. "
                    "Core Element AI qualifies as Delaware S-Corp."
                ),
            ),
        ]


def main():
    parser = argparse.ArgumentParser(description="Scrape Delaware state grants")
    parser.add_argument("--output", default="data/state_delaware_raw.json")
    args = parser.parse_args()

    with DelawareScraper() as scraper:
        results = scraper.search()

    grants = []
    for r in results:
        grants.append({
            "title": r.title,
            "funder": r.funder,
            "description": r.description,
            "amount_min": r.amount_min,
            "amount_max": r.amount_max,
            "currency": r.currency,
            "deadline": str(r.deadline) if r.deadline else "",
            "url": r.url,
            "source": r.source,
            "grant_type": r.grant_type,
            "industry_tags": r.industry_tags,
            "eligibility_text": r.eligibility_text,
            "scraped_at": datetime.now().isoformat(),
        })

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w") as f:
        json.dump(grants, f, indent=2)

    print(f"Delaware scraper: {len(grants)} grants saved to {args.output}")


if __name__ == "__main__":
    main()
