"""Multi-state economic development grant scraper.

Scrapes grant programs from priority US states for critical minerals,
AI, cleantech, and mining technology opportunities.
"""

import argparse
import json
from datetime import datetime
from pathlib import Path

from src.scrapers.base_scraper import BaseScraper, GrantResult
from src.utils.logger import setup_logger

logger = setup_logger("multi_state_scraper")

# Priority states and their economic development grant portals
PRIORITY_STATES = [
    {
        "state": "Colorado",
        "office": "Colorado OEDIT",
        "urls": [
            "https://choosecolorado.com/programs-initiatives/advanced-industries/",
            "https://oedit.colorado.gov/advance-industries-accelerator-programs",
        ],
        "relevance": "CSM partnership, Advanced Industries grants",
        "focus": ["cleantech", "AI", "advanced manufacturing", "energy"],
    },
    {
        "state": "Delaware",
        "office": "Delaware DSB",
        "urls": [
            "https://business.delaware.gov/edge-grants/",
            "https://business.delaware.gov/incentives/",
        ],
        "relevance": "HQ incorporation state, EDGE grants",
        "focus": ["STEM", "technology", "innovation"],
    },
    {
        "state": "Arizona",
        "office": "Arizona Commerce Authority",
        "urls": [
            "https://www.azcommerce.com/incentives/",
            "https://www.azcommerce.com/programs/innovation-challenge/",
        ],
        "relevance": "Major mining hub, copper and lithium deposits",
        "focus": ["mining", "cleantech", "innovation", "technology"],
    },
    {
        "state": "Nevada",
        "office": "Nevada Governor's Office of Economic Development",
        "urls": [
            "https://goed.nv.gov/programs-incentives/",
            "https://goed.nv.gov/key-industries/mining-materials/",
        ],
        "relevance": "Critical minerals hub, lithium deposits",
        "focus": ["mining", "critical minerals", "lithium", "cleantech"],
    },
    {
        "state": "California",
        "office": "California Governor's Office of Business and Economic Development",
        "urls": [
            "https://business.ca.gov/advantages/opportunity-zones/",
            "https://www.caloes.ca.gov/office-of-the-director/operations/recovery-programs/",
        ],
        "relevance": "Tech ecosystem, Stanford connection",
        "focus": ["technology", "AI", "cleantech", "innovation"],
    },
    {
        "state": "Wyoming",
        "office": "Wyoming Business Council",
        "urls": [
            "https://www.wyomingbusiness.org/programs",
        ],
        "relevance": "Rare earth elements, mining innovation",
        "focus": ["mining", "rare earths", "energy", "natural resources"],
    },
    {
        "state": "Alaska",
        "office": "Alaska Division of Economic Development",
        "urls": [
            "https://www.commerce.alaska.gov/web/ded/",
        ],
        "relevance": "Mineral resources, critical minerals exploration",
        "focus": ["mining", "mineral exploration", "natural resources"],
    },
]


class MultiStateScraper(BaseScraper):
    """Scraper for grants across multiple priority US states.

    Targets economic development offices and innovation programs in states
    with high relevance to Core Element AI's business.
    """

    def __init__(self):
        super().__init__(rate_limit_calls=10, rate_limit_period=60)

    @property
    def name(self) -> str:
        return "multi_state"

    def search(self, keywords: list[str] | None = None) -> list[GrantResult]:
        """Scrape all priority state grant programs."""
        all_results: list[GrantResult] = []

        for state_config in PRIORITY_STATES:
            try:
                results = self._scrape_state(state_config)
                all_results.extend(results)
                logger.info(
                    "[multi_state] %s: found %d grants",
                    state_config["state"], len(results),
                )
            except Exception as e:
                logger.error(
                    "[multi_state] Error scraping %s: %s",
                    state_config["state"], e,
                )

        logger.info("[multi_state] Total: %d grants from %d states", len(all_results), len(PRIORITY_STATES))
        return all_results

    def _scrape_state(self, config: dict) -> list[GrantResult]:
        """Scrape a single state's grant programs."""
        results: list[GrantResult] = []

        for url in config["urls"]:
            try:
                response = self._fetch(url)
                soup = self._parse_html(response.text)

                items = soup.select(
                    "article, .card, .program-item, .grant-item, "
                    ".content-block, section, .incentive-item, li.program"
                )
                for item in items[:30]:
                    try:
                        title_el = item.select_one("h2, h3, h4, .title, .heading, a")
                        if not title_el:
                            continue

                        title = title_el.get_text(strip=True)
                        if not title or len(title) < 5:
                            continue

                        text = item.get_text(separator=" ", strip=True).lower()
                        relevant = [
                            "grant", "funding", "award", "incentive",
                            "innovation", "technology", "apply", "program",
                            "mining", "clean", "energy", "ai",
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
                                from urllib.parse import urljoin
                                grant_url = urljoin(url, href)

                        desc_el = item.select_one("p, .description, .summary")
                        description = desc_el.get_text(strip=True) if desc_el else ""

                        from src.utils.text_processor import TextProcessor
                        amount_min, amount_max, currency = TextProcessor.extract_amount(text)
                        deadline_str = TextProcessor.extract_deadline(text)
                        deadline = None
                        if deadline_str:
                            from src.utils.date_utils import DateUtils
                            deadline = DateUtils.parse_date(deadline_str)

                        results.append(GrantResult(
                            title=f"{config['state']}: {title}",
                            funder=config["office"],
                            description=description,
                            amount_min=amount_min,
                            amount_max=amount_max,
                            currency=currency or "USD",
                            deadline=deadline,
                            url=grant_url,
                            source=f"{config['state'].lower()}_state",
                            grant_type="state",
                            industry_tags=config.get("focus", []),
                        ))

                    except Exception as e:
                        logger.debug("[multi_state] Error parsing item in %s: %s", config["state"], e)

            except Exception as e:
                logger.warning("[multi_state] Failed to fetch %s: %s", url, e)

        return results


def main():
    parser = argparse.ArgumentParser(description="Scrape multi-state grants")
    parser.add_argument("--output", default="data/state_grants_raw.json")
    args = parser.parse_args()

    # Import dedicated state scrapers
    from src.scrapers.state_grants.colorado_scraper import ColoradoScraper
    from src.scrapers.state_grants.delaware_scraper import DelawareScraper

    all_grants: list[dict] = []

    # Run dedicated scrapers first
    for ScraperClass in [ColoradoScraper, DelawareScraper]:
        try:
            with ScraperClass() as scraper:
                results = scraper.search()
                for r in results:
                    all_grants.append({
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
        except Exception as e:
            logger.error("Dedicated scraper %s failed: %s", ScraperClass.__name__, e)

    # Run multi-state scraper for remaining states
    try:
        with MultiStateScraper() as scraper:
            results = scraper.search()
            for r in results:
                all_grants.append({
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
                    "scraped_at": datetime.now().isoformat(),
                })
    except Exception as e:
        logger.error("Multi-state scraper failed: %s", e)

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w") as f:
        json.dump(all_grants, f, indent=2)

    print(f"State scrapers: {len(all_grants)} grants saved to {args.output}")


if __name__ == "__main__":
    main()
