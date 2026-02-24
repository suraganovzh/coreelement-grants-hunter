"""Colorado Office of Economic Development grant scraper.

Focus: Advanced Industries Proof of Concept Grant and related programs.
Colorado is a priority state due to Colorado School of Mines partnership.
"""

import argparse
import json
from datetime import datetime
from pathlib import Path

from src.scrapers.base_scraper import BaseScraper, GrantResult
from src.utils.logger import setup_logger

logger = setup_logger("colorado_scraper")

COLORADO_SOURCES = [
    {
        "name": "Advanced Industries Proof of Concept",
        "url": "https://choosecolorado.com/programs-initiatives/advanced-industries/",
        "backup_url": "https://oedit.colorado.gov/advance-industries-accelerator-programs",
        "funder": "Colorado OEDIT",
        "grant_type": "state",
        "focus": ["Advanced Industries", "Proof of Concept"],
    },
    {
        "name": "Colorado Advanced Industries Accelerator",
        "url": "https://oedit.colorado.gov/advance-industries-accelerator-programs",
        "funder": "Colorado OEDIT",
        "grant_type": "state",
        "focus": ["AI", "cleantech", "technology"],
    },
    {
        "name": "Colorado Innovation Network",
        "url": "https://choosecolorado.com/programs-initiatives/",
        "funder": "Colorado OEDIT",
        "grant_type": "state",
        "focus": ["innovation", "startups", "technology"],
    },
]


class ColoradoScraper(BaseScraper):
    """Scraper for Colorado state grant programs.

    Focuses on OEDIT Advanced Industries grants, which are highly relevant
    for Core Element AI due to CSM partnership and cleantech focus.
    """

    def __init__(self):
        super().__init__(rate_limit_calls=5, rate_limit_period=60)

    @property
    def name(self) -> str:
        return "colorado_state"

    def search(self, keywords: list[str] | None = None) -> list[GrantResult]:
        """Scrape Colorado state grant programs."""
        all_results: list[GrantResult] = []

        for source in COLORADO_SOURCES:
            try:
                results = self._scrape_source(source)
                all_results.extend(results)
                logger.info("[colorado] %s: found %d grants", source["name"], len(results))
            except Exception as e:
                logger.error("[colorado] Error scraping %s: %s", source["name"], e)

        # Always include known active programs as baseline
        all_results.extend(self._known_active_programs())

        logger.info("[colorado] Total: %d grants", len(all_results))
        return all_results

    def _scrape_source(self, source: dict) -> list[GrantResult]:
        """Scrape a single Colorado source page."""
        results: list[GrantResult] = []

        urls_to_try = [source["url"]]
        if "backup_url" in source:
            urls_to_try.append(source["backup_url"])

        for url in urls_to_try:
            try:
                response = self._fetch(url)
                soup = self._parse_html(response.text)

                # Look for grant listings in various page structures
                items = soup.select("article, .card, .program-item, .grant-item, .content-block, section")
                for item in items[:30]:
                    try:
                        title_el = item.select_one("h2, h3, h4, .title, .heading")
                        if not title_el:
                            continue

                        title = title_el.get_text(strip=True)
                        if not title or len(title) < 5:
                            continue

                        text = item.get_text(separator=" ", strip=True).lower()

                        # Check for relevance to grant programs
                        relevant_terms = [
                            "grant", "funding", "award", "proof of concept",
                            "accelerator", "innovation", "poc", "apply",
                            "advanced industries", "cleantech",
                        ]
                        if not any(term in text for term in relevant_terms):
                            continue

                        # Extract link
                        link_el = item.select_one("a[href]")
                        grant_url = url
                        if link_el:
                            href = link_el.get("href", "")
                            if href.startswith("http"):
                                grant_url = href
                            elif href.startswith("/"):
                                from urllib.parse import urljoin
                                grant_url = urljoin(url, href)

                        # Extract description
                        desc_el = item.select_one("p, .description, .summary")
                        description = desc_el.get_text(strip=True) if desc_el else ""

                        # Extract amount
                        from src.utils.text_processor import TextProcessor
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
                            currency=currency or "USD",
                            deadline=deadline,
                            url=grant_url,
                            source="colorado_state",
                            grant_type="state",
                            industry_tags=source.get("focus", []),
                            eligibility_text="Colorado-based or partnered companies. Small businesses eligible.",
                        ))

                    except Exception as e:
                        logger.debug("[colorado] Error parsing item: %s", e)

                if results:
                    break  # Success with first URL, skip backup

            except Exception as e:
                logger.warning("[colorado] Failed to fetch %s: %s", url, e)

        return results

    def _known_active_programs(self) -> list[GrantResult]:
        """Return known active Colorado grant programs.

        These are manually tracked high-priority programs that may not
        always be discoverable via web scraping.
        """
        known = []

        # Advanced Industries Proof of Concept Grant
        known.append(GrantResult(
            title="Colorado Advanced Industries Proof of Concept Grant",
            funder="Colorado OEDIT",
            description=(
                "Provides early-stage capital to advance the development of a "
                "commercially viable product or process in one of Colorado's "
                "Advanced Industries: aerospace, advanced manufacturing, bioscience, "
                "electronics, energy and natural resources, infrastructure engineering, "
                "and technology and information."
            ),
            amount_min=50000,
            amount_max=150000,
            currency="USD",
            deadline=None,  # Rolling / periodic deadlines
            url="https://oedit.colorado.gov/advance-industries-accelerator-programs",
            source="colorado_state",
            grant_type="state",
            industry_tags=[
                "cleantech", "AI", "advanced manufacturing",
                "energy", "natural resources", "technology",
            ],
            eligibility_text=(
                "Must be a Colorado-based company or partnered with a Colorado "
                "research institution. Small businesses encouraged. "
                "Core Element AI qualifies via Colorado School of Mines partnership."
            ),
        ))

        return known


def main():
    parser = argparse.ArgumentParser(description="Scrape Colorado state grants")
    parser.add_argument("--output", default="data/state_colorado_raw.json")
    args = parser.parse_args()

    with ColoradoScraper() as scraper:
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

    print(f"Colorado scraper: {len(grants)} grants saved to {args.output}")


if __name__ == "__main__":
    main()
