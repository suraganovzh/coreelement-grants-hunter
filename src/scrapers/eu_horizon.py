"""EU Horizon Europe scraper — European research funding."""

from datetime import datetime

from src.scrapers.base_scraper import BaseScraper, GrantResult
from src.utils.logger import setup_logger
from src.utils.text_processor import TextProcessor

logger = setup_logger("eu_horizon")

EU_KEYWORDS = [
    "critical raw materials",
    "mining AI",
    "mineral exploration",
    "geological AI",
    "raw materials intelligence",
    "sustainable mining",
    "battery materials",
    "clean energy transition minerals",
]


class EUHorizonScraper(BaseScraper):
    """Scraper for EU Horizon Europe and related EU funding programs.

    Searches the EU Funding & Tenders portal for relevant opportunities.
    Also covers EIT RawMaterials and EIC Accelerator.
    """

    SEARCH_API = "https://api.tech.ec.europa.eu/search-api/prod/rest/search"
    PORTAL_URL = "https://ec.europa.eu/info/funding-tenders/opportunities/portal"

    def __init__(self):
        super().__init__(rate_limit_calls=20, rate_limit_period=60)

    @property
    def name(self) -> str:
        return "eu_horizon"

    def search(self, keywords: list[str] | None = None) -> list[GrantResult]:
        """Search EU Funding & Tenders portal."""
        keywords = keywords or EU_KEYWORDS
        all_results: list[GrantResult] = []
        seen_urls: set[str] = set()

        for keyword in keywords:
            try:
                grants = self._search_portal(keyword)
                for grant in grants:
                    if grant.url not in seen_urls:
                        seen_urls.add(grant.url)
                        all_results.append(grant)
            except Exception as e:
                logger.error("[eu_horizon] Error searching '%s': %s", keyword, e)

        # Also scrape EIT RawMaterials
        try:
            eit_grants = self._scrape_eit_raw_materials()
            for grant in eit_grants:
                if grant.url not in seen_urls:
                    seen_urls.add(grant.url)
                    all_results.append(grant)
        except Exception as e:
            logger.error("[eu_horizon] EIT RawMaterials error: %s", e)

        logger.info("[eu_horizon] Found %d unique grants", len(all_results))
        return all_results

    def _search_portal(self, keyword: str) -> list[GrantResult]:
        """Search the EU Funding & Tenders API."""
        results: list[GrantResult] = []

        try:
            params = {
                "apiKey": "SEDIA",
                "text": keyword,
                "pageSize": 20,
                "pageNumber": 1,
                "type": "1",  # Calls for proposals
            }

            response = self._fetch(self.SEARCH_API, params=params)
            data = response.json()

            hits = data.get("results", [])
            logger.debug("[eu_horizon] '%s' returned %d results", keyword, len(hits))

            for hit in hits:
                try:
                    metadata = hit.get("metadata", {})
                    title = metadata.get("title", [""])[0] if isinstance(metadata.get("title"), list) else metadata.get("title", "")

                    if not title:
                        continue

                    description = metadata.get("description", [""])[0] if isinstance(metadata.get("description"), list) else metadata.get("description", "")
                    description = TextProcessor.clean_html(description)

                    # Deadline
                    deadline_str = metadata.get("deadlineDates", [""])[0] if isinstance(metadata.get("deadlineDates"), list) else metadata.get("deadlineDates", "")
                    deadline = None
                    if deadline_str:
                        try:
                            deadline = datetime.strptime(deadline_str[:10], "%Y-%m-%d").date()
                        except (ValueError, IndexError):
                            pass

                    # URL
                    identifier = metadata.get("identifier", [""])[0] if isinstance(metadata.get("identifier"), list) else metadata.get("identifier", "")
                    url = f"{self.PORTAL_URL}/search/topic/{identifier}" if identifier else ""

                    # Budget
                    budget_str = str(metadata.get("budget", ""))
                    amount_min, amount_max, _ = TextProcessor.extract_amount(budget_str)

                    results.append(GrantResult(
                        title=title,
                        funder="European Commission - Horizon Europe",
                        description=description,
                        amount_min=amount_min,
                        amount_max=amount_max,
                        currency="EUR",
                        deadline=deadline,
                        url=url,
                        source="eu_horizon",
                        grant_type="international",
                        industry_tags=["EU", "research", "innovation"],
                        eligibility_text="Open to entities from EU Member States and associated countries. Third-country participation may be possible.",
                    ))

                except Exception as e:
                    logger.warning("[eu_horizon] Failed to parse result: %s", e)

        except Exception as e:
            logger.error("[eu_horizon] Portal API error for '%s': %s", keyword, e)

        return results

    def _scrape_eit_raw_materials(self) -> list[GrantResult]:
        """Scrape EIT RawMaterials calls for proposals."""
        results: list[GrantResult] = []

        try:
            response = self._fetch("https://eitrawmaterials.eu/calls/")
            soup = self._parse_html(response.text)

            for article in soup.select("article, .call-item, .post-item")[:15]:
                try:
                    title_el = article.select_one("h2, h3, .entry-title")
                    if not title_el:
                        continue

                    title = title_el.get_text(strip=True)
                    link_el = article.select_one("a[href]")
                    url = link_el.get("href", "") if link_el else ""

                    desc_el = article.select_one("p, .excerpt, .entry-content")
                    description = desc_el.get_text(strip=True) if desc_el else ""

                    text = article.get_text(strip=True)
                    amount_min, amount_max, currency = TextProcessor.extract_amount(text)

                    results.append(GrantResult(
                        title=f"[EIT RawMaterials] {title}",
                        funder="EIT RawMaterials",
                        description=description,
                        amount_min=amount_min,
                        amount_max=amount_max,
                        currency=currency or "EUR",
                        url=url,
                        source="eit_raw_materials",
                        grant_type="international",
                        industry_tags=["raw materials", "mining", "innovation", "EU"],
                    ))

                except Exception as e:
                    logger.debug("[eu_horizon] EIT parse error: %s", e)

        except Exception as e:
            logger.error("[eu_horizon] EIT RawMaterials scrape failed: %s", e)

        return results
