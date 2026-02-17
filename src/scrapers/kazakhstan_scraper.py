"""Kazakhstan-specific grants and innovation funding scraper."""

from src.scrapers.base_scraper import BaseScraper, GrantResult
from src.utils.logger import setup_logger
from src.utils.text_processor import TextProcessor

logger = setup_logger("kazakhstan_scraper")

KZ_SOURCES = [
    {
        "name": "Astana Hub",
        "url": "https://astanahub.com/en/grants",
        "funder": "Astana Hub",
        "description": "Kazakhstan's international technopark for IT startups",
    },
    {
        "name": "QazInnovations (NATD)",
        "url": "https://qazinnovations.gov.kz/en",
        "funder": "QazInnovations / NATD",
        "description": "National Agency for Technological Development of Kazakhstan",
    },
    {
        "name": "Ministry of Digital Development",
        "url": "https://www.gov.kz/memleket/entities/mdai",
        "funder": "Ministry of Digital Development, Innovation and Aerospace Industry",
        "description": "Kazakhstan government digital and innovation programs",
    },
    {
        "name": "Baiterek Holding",
        "url": "https://www.baiterek.gov.kz/en",
        "funder": "Baiterek National Holding",
        "description": "National development institution for entrepreneurship support",
    },
]


class KazakhstanScraper(BaseScraper):
    """Scraper for Kazakhstan-specific innovation grants.

    Covers Astana Hub, NATD/QazInnovations, Ministry of Digital Development,
    and other KZ-specific funding sources.
    """

    def __init__(self):
        super().__init__(rate_limit_calls=10, rate_limit_period=60)

    @property
    def name(self) -> str:
        return "kazakhstan"

    def search(self, keywords: list[str] | None = None) -> list[GrantResult]:
        """Search Kazakhstan funding sources."""
        all_results: list[GrantResult] = []

        for source in KZ_SOURCES:
            try:
                results = self._scrape_source(source)
                all_results.extend(results)
                logger.info("[kz] %s: %d results", source["name"], len(results))
            except Exception as e:
                logger.error("[kz] Error scraping %s: %s", source["name"], e)

        logger.info("[kz] Total: %d grants", len(all_results))
        return all_results

    def _scrape_source(self, source: dict) -> list[GrantResult]:
        """Scrape a single KZ source."""
        results: list[GrantResult] = []

        try:
            response = self._fetch(source["url"])
            soup = self._parse_html(response.text)

            items = soup.select("article, .card, .item, .grant-item, .news-item, .post, .program-item")[:15]

            for item in items:
                try:
                    title_el = item.select_one("h2, h3, h4, .title, .heading, .name")
                    if not title_el:
                        continue

                    title = title_el.get_text(strip=True)
                    if len(title) < 5:
                        continue

                    text = item.get_text(separator=" ", strip=True).lower()
                    relevant_terms = [
                        "grant", "грант", "funding", "финансирование",
                        "innovation", "инновации", "technology", "технологии",
                        "program", "программа", "apply", "заявка", "конкурс",
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
                        title=f"[KZ] {title}",
                        funder=source["funder"],
                        description=description or source["description"],
                        amount_min=amount_min,
                        amount_max=amount_max,
                        currency=currency or "KZT",
                        url=url or source["url"],
                        source="kazakhstan",
                        grant_type="international",
                        industry_tags=["kazakhstan", "innovation"],
                    ))

                except Exception as e:
                    logger.debug("[kz] Parse error: %s", e)

        except Exception as e:
            logger.error("[kz] Failed to scrape %s: %s", source["url"], e)

        return results
