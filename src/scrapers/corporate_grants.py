"""Corporate & mining industry grants scraper."""

from src.scrapers.base_scraper import BaseScraper, GrantResult
from src.utils.logger import setup_logger
from src.utils.text_processor import TextProcessor

logger = setup_logger("corporate_grants")

CORPORATE_SOURCES = [
    {
        "name": "Anglo American Foundation",
        "url": "https://www.angloamerican.com/sustainability/our-sustainable-mining-plan",
        "funder": "Anglo American",
        "industry": "mining",
    },
    {
        "name": "Rio Tinto Innovation",
        "url": "https://www.riotinto.com/en/sustainability",
        "funder": "Rio Tinto",
        "industry": "mining",
    },
    {
        "name": "BHP Foundation",
        "url": "https://www.bhp.com/community/bhp-foundation",
        "funder": "BHP",
        "industry": "mining",
    },
    {
        "name": "Natural Resources Canada",
        "url": "https://natural-resources.canada.ca/science-and-data/funding-partnerships/funding-opportunities/current-funding-opportunities/4943",
        "funder": "Natural Resources Canada",
        "industry": "resources",
    },
    {
        "name": "Breakthrough Energy Fellows",
        "url": "https://www.breakthroughenergy.org/scaling-the-solution/fellows/",
        "funder": "Breakthrough Energy",
        "industry": "cleantech",
    },
    {
        "name": "ARPA-E Programs",
        "url": "https://arpa-e.energy.gov/technologies/open-funding-opportunities",
        "funder": "ARPA-E / DOE",
        "industry": "energy",
    },
]


class CorporateGrantsScraper(BaseScraper):
    """Scraper for corporate grants and mining industry funding."""

    def __init__(self):
        super().__init__(rate_limit_calls=10, rate_limit_period=60)

    @property
    def name(self) -> str:
        return "corporate_grants"

    def search(self, keywords: list[str] | None = None) -> list[GrantResult]:
        """Scrape corporate and industry funding sources."""
        all_results: list[GrantResult] = []

        for source in CORPORATE_SOURCES:
            try:
                results = self._scrape_source(source)
                all_results.extend(results)
                logger.info("[corporate] %s: %d results", source["name"], len(results))
            except Exception as e:
                logger.error("[corporate] Error scraping %s: %s", source["name"], e)

        logger.info("[corporate] Total: %d grants", len(all_results))
        return all_results

    def _scrape_source(self, source: dict) -> list[GrantResult]:
        """Scrape a single corporate/industry source."""
        results: list[GrantResult] = []

        try:
            response = self._fetch(source["url"])
            soup = self._parse_html(response.text)

            items = soup.select("article, .card, .item, .grant-item, section, .content-block")[:15]

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
                        "grant", "fund", "innovation", "technology", "research",
                        "apply", "program", "award", "partnership", "challenge",
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

                    desc_el = item.select_one("p, .description, .summary")
                    description = desc_el.get_text(strip=True) if desc_el else ""

                    amount_min, amount_max, currency = TextProcessor.extract_amount(text)

                    tags = [source["industry"]]
                    if "mining" in text or "mineral" in text:
                        tags.append("mining")
                    if "ai" in text or "technology" in text:
                        tags.append("technology")

                    results.append(GrantResult(
                        title=title,
                        funder=source["funder"],
                        description=description,
                        amount_min=amount_min,
                        amount_max=amount_max,
                        currency=currency,
                        url=url or source["url"],
                        source="corporate_grants",
                        grant_type="private",
                        industry_tags=tags,
                    ))

                except Exception as e:
                    logger.debug("[corporate] Parse error: %s", e)

        except Exception as e:
            logger.error("[corporate] Failed to scrape %s: %s", source["url"], e)

        return results
