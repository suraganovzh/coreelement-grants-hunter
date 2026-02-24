"""EQT Foundation Science Grants scraper.

EQT Foundation funds critical minerals, climate tech, and deeptech research.
High priority due to direct alignment with Core Element AI's mission.
"""

import argparse
import json
from datetime import datetime
from pathlib import Path

from src.scrapers.base_scraper import BaseScraper, GrantResult
from src.utils.logger import setup_logger

logger = setup_logger("eqt_foundation_scraper")

EQT_URLS = {
    "foundation": "https://eqtgroup.com/eqt-foundation/",
    "news": "https://eqtgroup.com/news/",
    "grants": "https://eqtgroup.com/eqt-foundation/grant-submission",
}


class EQTFoundationScraper(BaseScraper):
    """Scraper for EQT Foundation grant announcements.

    EQT Foundation provides science grants focused on deeptech, climate,
    and green transition — directly aligned with critical minerals AI.
    """

    def __init__(self):
        super().__init__(rate_limit_calls=5, rate_limit_period=60)

    @property
    def name(self) -> str:
        return "eqt_foundation"

    def search(self, keywords: list[str] | None = None) -> list[GrantResult]:
        """Search EQT Foundation for grant opportunities."""
        all_results: list[GrantResult] = []

        # Scrape main foundation page
        try:
            results = self._scrape_foundation_page()
            all_results.extend(results)
        except Exception as e:
            logger.error("[eqt] Error scraping foundation page: %s", e)

        # Scrape news for grant announcements
        try:
            results = self._scrape_news()
            all_results.extend(results)
        except Exception as e:
            logger.error("[eqt] Error scraping news: %s", e)

        # Always include known active programs
        all_results.extend(self._known_active_programs())

        logger.info("[eqt] Total: %d grants", len(all_results))
        return all_results

    def _scrape_foundation_page(self) -> list[GrantResult]:
        """Scrape the EQT Foundation main page."""
        results: list[GrantResult] = []

        try:
            response = self._fetch(EQT_URLS["foundation"])
            soup = self._parse_html(response.text)

            items = soup.select("article, .card, section, .content-block, .grant-item")
            for item in items[:20]:
                try:
                    title_el = item.select_one("h2, h3, h4, .title")
                    if not title_el:
                        continue

                    title = title_el.get_text(strip=True)
                    if not title or len(title) < 5:
                        continue

                    text = item.get_text(separator=" ", strip=True).lower()
                    relevant = ["grant", "funding", "science", "research", "apply", "submission"]
                    if not any(term in text for term in relevant):
                        continue

                    link_el = item.select_one("a[href]")
                    url = EQT_URLS["foundation"]
                    if link_el:
                        href = link_el.get("href", "")
                        if href.startswith("http"):
                            url = href
                        elif href.startswith("/"):
                            url = f"https://eqtgroup.com{href}"

                    desc_el = item.select_one("p, .description")
                    description = desc_el.get_text(strip=True) if desc_el else ""

                    from src.utils.text_processor import TextProcessor
                    amount_min, amount_max, currency = TextProcessor.extract_amount(text)

                    results.append(GrantResult(
                        title=f"EQT Foundation: {title}",
                        funder="EQT Foundation",
                        description=description,
                        amount_min=amount_min,
                        amount_max=amount_max,
                        currency=currency or "EUR",
                        deadline=None,
                        url=url,
                        source="eqt_foundation",
                        grant_type="private_foundation",
                        industry_tags=["deeptech", "climate", "science"],
                    ))

                except Exception as e:
                    logger.debug("[eqt] Error parsing item: %s", e)

        except Exception as e:
            logger.warning("[eqt] Failed to fetch foundation page: %s", e)

        return results

    def _scrape_news(self) -> list[GrantResult]:
        """Scrape EQT news for grant announcements."""
        results: list[GrantResult] = []

        try:
            response = self._fetch(EQT_URLS["news"])
            soup = self._parse_html(response.text)

            articles = soup.select("article, .news-item, .card")
            for article in articles[:20]:
                try:
                    title_el = article.select_one("h2, h3, h4, .title")
                    if not title_el:
                        continue

                    title = title_el.get_text(strip=True)
                    text = article.get_text(separator=" ", strip=True).lower()

                    # Only care about grant/funding related news
                    grant_terms = ["grant", "fund", "award", "science", "foundation"]
                    if not any(term in text for term in grant_terms):
                        continue

                    link_el = article.select_one("a[href]")
                    url = EQT_URLS["news"]
                    if link_el:
                        href = link_el.get("href", "")
                        if href.startswith("http"):
                            url = href
                        elif href.startswith("/"):
                            url = f"https://eqtgroup.com{href}"

                    desc_el = article.select_one("p, .summary")
                    description = desc_el.get_text(strip=True) if desc_el else ""

                    from src.utils.text_processor import TextProcessor
                    amount_min, amount_max, currency = TextProcessor.extract_amount(text)

                    results.append(GrantResult(
                        title=f"EQT Foundation: {title}",
                        funder="EQT Foundation",
                        description=description,
                        amount_min=amount_min,
                        amount_max=amount_max,
                        currency=currency or "EUR",
                        deadline=None,
                        url=url,
                        source="eqt_foundation",
                        grant_type="private_foundation",
                        industry_tags=["deeptech", "climate", "science", "green transition"],
                    ))

                except Exception as e:
                    logger.debug("[eqt] Error parsing news item: %s", e)

        except Exception as e:
            logger.warning("[eqt] Failed to fetch news: %s", e)

        return results

    def _known_active_programs(self) -> list[GrantResult]:
        """Return known active EQT Foundation programs."""
        return [
            GrantResult(
                title="EQT Foundation - Critical Minerals Science Grants",
                funder="EQT Foundation",
                description=(
                    "EQT Foundation science grants for researchers working on "
                    "critical minerals, climate technology, and green transition. "
                    "Supports scientists affiliated with accredited nonprofit institutions. "
                    "Focus areas include deeptech, sustainability, and decarbonization."
                ),
                amount_min=25000,
                amount_max=100000,
                currency="EUR",
                deadline=None,
                url=EQT_URLS["grants"],
                source="eqt_foundation",
                grant_type="private_foundation",
                industry_tags=[
                    "critical minerals", "climate tech", "deeptech",
                    "green transition", "science", "sustainability",
                ],
                eligibility_text=(
                    "Scientists affiliated with accredited nonprofit institutions. "
                    "Partnership pathway: Core Element AI can apply via "
                    "Colorado School of Mines or Stanford Mineral-X affiliation."
                ),
            ),
        ]


def main():
    parser = argparse.ArgumentParser(description="Scrape EQT Foundation grants")
    parser.add_argument("--output", default="data/foundation_eqt_raw.json")
    args = parser.parse_args()

    with EQTFoundationScraper() as scraper:
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
            "focus_areas": r.industry_tags,
            "scraped_at": datetime.now().isoformat(),
        })

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w") as f:
        json.dump(grants, f, indent=2)

    print(f"EQT Foundation scraper: {len(grants)} grants saved to {args.output}")


if __name__ == "__main__":
    main()
