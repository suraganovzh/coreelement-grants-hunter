"""Foundation & private grants scraper."""

from datetime import datetime

from src.scrapers.base_scraper import BaseScraper, GrantResult
from src.utils.logger import setup_logger
from src.utils.text_processor import TextProcessor

logger = setup_logger("foundation_scraper")

# Known foundation grant pages to monitor
FOUNDATION_SOURCES = [
    {
        "name": "Google AI Research",
        "url": "https://research.google/outreach/",
        "funder": "Google",
        "grant_type": "private",
        "selectors": {"listing": ".grant-item, .outreach-item, article"},
    },
    {
        "name": "Microsoft AI for Earth",
        "url": "https://www.microsoft.com/en-us/ai/ai-for-earth-grants",
        "funder": "Microsoft",
        "grant_type": "private",
        "selectors": {"listing": ".grant-card, .card, article"},
    },
    {
        "name": "Amazon Sustainability",
        "url": "https://sustainability.aboutamazon.com/",
        "funder": "Amazon",
        "grant_type": "private",
        "selectors": {"listing": ".grant-item, .card, article"},
    },
    {
        "name": "Intel Innovation",
        "url": "https://www.intel.com/content/www/us/en/research/overview.html",
        "funder": "Intel",
        "grant_type": "private",
        "selectors": {"listing": ".grant-item, .card, article"},
    },
]


class FoundationScraper(BaseScraper):
    """Scraper for private foundation grants.

    Scrapes known foundation websites for grant opportunities.
    Uses HTML parsing since most foundations don't have APIs.
    """

    def __init__(self):
        super().__init__(rate_limit_calls=10, rate_limit_period=60)

    @property
    def name(self) -> str:
        return "foundations"

    def search(self, keywords: list[str] | None = None) -> list[GrantResult]:
        """Search foundation websites for grants."""
        all_results: list[GrantResult] = []

        for source in FOUNDATION_SOURCES:
            try:
                results = self._scrape_foundation(source)
                all_results.extend(results)
                logger.info("[foundations] %s: found %d grants", source["name"], len(results))
            except Exception as e:
                logger.error("[foundations] Error scraping %s: %s", source["name"], e)

        logger.info("[foundations] Total: %d grants from %d sources", len(all_results), len(FOUNDATION_SOURCES))
        return all_results

    def _scrape_foundation(self, source: dict) -> list[GrantResult]:
        """Scrape a single foundation page."""
        results: list[GrantResult] = []

        try:
            response = self._fetch(source["url"])
            soup = self._parse_html(response.text)

            # Try multiple CSS selectors
            selectors = source.get("selectors", {}).get("listing", "article, .card")
            items = soup.select(selectors)

            for item in items[:20]:  # Limit to first 20 items
                try:
                    title_el = item.select_one("h2, h3, h4, .title, .heading")
                    if not title_el:
                        continue

                    title = title_el.get_text(strip=True)
                    if not title or len(title) < 10:
                        continue

                    # Check relevance
                    text = item.get_text(separator=" ", strip=True).lower()
                    relevant_terms = ["grant", "funding", "award", "innovation", "research", "apply"]
                    if not any(term in text for term in relevant_terms):
                        continue

                    # Extract link
                    link_el = item.select_one("a[href]")
                    url = ""
                    if link_el:
                        href = link_el.get("href", "")
                        if href.startswith("http"):
                            url = href
                        elif href.startswith("/"):
                            from urllib.parse import urljoin
                            url = urljoin(source["url"], href)

                    # Extract description
                    desc_el = item.select_one("p, .description, .summary")
                    description = desc_el.get_text(strip=True) if desc_el else ""

                    # Extract amount
                    amount_min, amount_max, currency = TextProcessor.extract_amount(text)

                    # Extract deadline
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
                        currency=currency,
                        deadline=deadline,
                        url=url or source["url"],
                        source="foundations",
                        grant_type=source["grant_type"],
                        industry_tags=self._extract_tags(text),
                    ))

                except Exception as e:
                    logger.debug("[foundations] Error parsing item: %s", e)

        except Exception as e:
            logger.error("[foundations] Failed to scrape %s: %s", source["url"], e)

        return results

    @staticmethod
    def _extract_tags(text: str) -> list[str]:
        """Extract relevant tags from text."""
        tags = []
        tag_map = {
            "AI": ["ai", "artificial intelligence", "machine learning"],
            "mining": ["mining", "mineral", "geological"],
            "cleantech": ["clean energy", "sustainable", "climate", "green"],
            "innovation": ["innovation", "startup", "technology"],
            "research": ["research", "science", "academic"],
        }
        for tag, keywords in tag_map.items():
            if any(kw in text for kw in keywords):
                tags.append(tag)
        return tags
