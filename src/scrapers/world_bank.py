"""World Bank & international development organizations scraper."""

from src.scrapers.base_scraper import BaseScraper, GrantResult
from src.utils.logger import setup_logger
from src.utils.text_processor import TextProcessor

logger = setup_logger("world_bank")

INTERNATIONAL_SOURCES = [
    {
        "name": "World Bank Innovation Labs",
        "url": "https://www.worldbank.org/en/programs/innovation-labs",
        "funder": "World Bank",
    },
    {
        "name": "IFC Startup Catalyst",
        "url": "https://www.ifc.org/en/what-we-do/sector-expertise/manufacturing",
        "funder": "IFC (International Finance Corporation)",
    },
    {
        "name": "Green Climate Fund",
        "url": "https://www.greenclimate.fund/about/resource-mobilisation",
        "funder": "Green Climate Fund",
    },
    {
        "name": "Global Environment Facility",
        "url": "https://www.thegef.org/how-we-work/funding",
        "funder": "Global Environment Facility",
    },
    {
        "name": "ADB Tech Innovation",
        "url": "https://www.adb.org/what-we-do/funds",
        "funder": "Asian Development Bank",
    },
    {
        "name": "EBRD Business Support",
        "url": "https://www.ebrd.com/what-we-do/get-support",
        "funder": "EBRD",
    },
]


class WorldBankScraper(BaseScraper):
    """Scraper for World Bank, IFC, GCF, GEF, ADB, EBRD funding."""

    def __init__(self):
        super().__init__(rate_limit_calls=10, rate_limit_period=60)

    @property
    def name(self) -> str:
        return "international_dev"

    def search(self, keywords: list[str] | None = None) -> list[GrantResult]:
        """Scrape international development organizations for funding."""
        all_results: list[GrantResult] = []

        for source in INTERNATIONAL_SOURCES:
            try:
                results = self._scrape_source(source)
                all_results.extend(results)
                logger.info("[world_bank] %s: %d results", source["name"], len(results))
            except Exception as e:
                logger.error("[world_bank] Error scraping %s: %s", source["name"], e)

        logger.info("[world_bank] Total: %d grants", len(all_results))
        return all_results

    def _scrape_source(self, source: dict) -> list[GrantResult]:
        """Scrape a single international source."""
        results: list[GrantResult] = []

        try:
            response = self._fetch(source["url"])
            soup = self._parse_html(response.text)

            # Generic article/card selector approach
            items = soup.select("article, .card, .item, .funding-item, .list-item, .post")[:15]

            for item in items:
                try:
                    title_el = item.select_one("h2, h3, h4, .title, .heading")
                    if not title_el:
                        continue

                    title = title_el.get_text(strip=True)
                    if len(title) < 10:
                        continue

                    text = item.get_text(separator=" ", strip=True).lower()
                    relevant_terms = [
                        "fund", "grant", "innovation", "technology", "mining",
                        "mineral", "climate", "energy", "apply", "proposal",
                    ]
                    if not any(term in text for term in relevant_terms):
                        continue

                    link_el = item.select_one("a[href]")
                    url = ""
                    if link_el:
                        href = link_el.get("href", "")
                        if href.startswith("http"):
                            url = href
                        elif href.startswith("/"):
                            from urllib.parse import urljoin
                            url = urljoin(source["url"], href)

                    desc_el = item.select_one("p, .description, .summary, .excerpt")
                    description = desc_el.get_text(strip=True) if desc_el else ""

                    amount_min, amount_max, currency = TextProcessor.extract_amount(text)

                    results.append(GrantResult(
                        title=title,
                        funder=source["funder"],
                        description=description,
                        amount_min=amount_min,
                        amount_max=amount_max,
                        currency=currency,
                        url=url or source["url"],
                        source="international_dev",
                        grant_type="international",
                        industry_tags=["international", "development"],
                    ))

                except Exception as e:
                    logger.debug("[world_bank] Parse error: %s", e)

        except Exception as e:
            logger.error("[world_bank] Failed to scrape %s: %s", source["url"], e)

        return results
