"""Alfred P. Sloan Foundation - Energy & Environment grants scraper."""

import argparse
import json
from datetime import datetime
from pathlib import Path

from src.scrapers.base_scraper import BaseScraper, GrantResult
from src.utils.logger import setup_logger

logger = setup_logger("sloan_foundation_scraper")

SLOAN_URLS = {
    "energy": "https://sloan.org/programs/energy-and-environment",
    "grants": "https://sloan.org/grants",
    "programs": "https://sloan.org/programs",
}


class SloanFoundationScraper(BaseScraper):
    """Scraper for Alfred P. Sloan Foundation grants.

    Focuses on Energy & Environment program and related research grants
    relevant to critical minerals and clean energy.
    """

    def __init__(self):
        super().__init__(rate_limit_calls=5, rate_limit_period=60)

    @property
    def name(self) -> str:
        return "sloan_foundation"

    def search(self, keywords: list[str] | None = None) -> list[GrantResult]:
        """Search Sloan Foundation for grant opportunities."""
        all_results: list[GrantResult] = []

        for page_key, url in SLOAN_URLS.items():
            try:
                results = self._scrape_page(url, page_key)
                all_results.extend(results)
                logger.info("[sloan] %s: found %d grants", page_key, len(results))
            except Exception as e:
                logger.error("[sloan] Error scraping %s: %s", page_key, e)

        all_results.extend(self._known_active_programs())

        logger.info("[sloan] Total: %d grants", len(all_results))
        return all_results

    def _scrape_page(self, url: str, page_key: str) -> list[GrantResult]:
        """Scrape a single Sloan Foundation page."""
        results: list[GrantResult] = []

        try:
            response = self._fetch(url)
            soup = self._parse_html(response.text)

            items = soup.select("article, .card, .grant-item, .program-item, section")
            for item in items[:20]:
                try:
                    title_el = item.select_one("h2, h3, h4, .title")
                    if not title_el:
                        continue

                    title = title_el.get_text(strip=True)
                    if not title or len(title) < 5:
                        continue

                    text = item.get_text(separator=" ", strip=True).lower()
                    relevant = [
                        "grant", "funding", "research", "energy",
                        "environment", "mineral", "apply",
                    ]
                    if not any(term in text for term in relevant):
                        continue

                    link_el = item.select_one("a[href]")
                    grant_url = url
                    if link_el:
                        href = link_el.get("href", "")
                        if href.startswith("http"):
                            grant_url = href
                        elif href.startswith("/"):
                            grant_url = f"https://sloan.org{href}"

                    desc_el = item.select_one("p, .description")
                    description = desc_el.get_text(strip=True) if desc_el else ""

                    from src.utils.text_processor import TextProcessor
                    amount_min, amount_max, currency = TextProcessor.extract_amount(text)

                    results.append(GrantResult(
                        title=f"Sloan Foundation: {title}",
                        funder="Alfred P. Sloan Foundation",
                        description=description,
                        amount_min=amount_min,
                        amount_max=amount_max,
                        currency=currency or "USD",
                        deadline=None,
                        url=grant_url,
                        source="sloan_foundation",
                        grant_type="private_foundation",
                        industry_tags=["energy", "environment", "research", "science"],
                    ))

                except Exception as e:
                    logger.debug("[sloan] Error parsing item: %s", e)

        except Exception as e:
            logger.warning("[sloan] Failed to fetch %s: %s", url, e)

        return results

    def _known_active_programs(self) -> list[GrantResult]:
        """Return known active Sloan Foundation programs."""
        return [
            GrantResult(
                title="Sloan Foundation - Energy & Environment Research Grants",
                funder="Alfred P. Sloan Foundation",
                description=(
                    "The Sloan Foundation's Energy & Environment program supports "
                    "research on energy systems, environmental science, and the "
                    "transition to sustainable energy. Relevant to critical minerals "
                    "research and clean technology."
                ),
                amount_min=50000,
                amount_max=500000,
                currency="USD",
                deadline=None,
                url=SLOAN_URLS["energy"],
                source="sloan_foundation",
                grant_type="private_foundation",
                industry_tags=[
                    "energy", "environment", "clean energy",
                    "sustainability", "research",
                ],
                eligibility_text=(
                    "Primarily funds academic researchers. Partnership pathway "
                    "through university affiliations (CSM, Stanford, Berkeley)."
                ),
            ),
        ]


def main():
    parser = argparse.ArgumentParser(description="Scrape Sloan Foundation grants")
    parser.add_argument("--output", default="data/foundation_sloan_raw.json")
    args = parser.parse_args()

    with SloanFoundationScraper() as scraper:
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

    print(f"Sloan Foundation scraper: {len(grants)} grants saved to {args.output}")


if __name__ == "__main__":
    main()
