"""Scrape state-level and foundation grant winners for pattern matching."""

import argparse
import json
from datetime import datetime
from pathlib import Path

from src.scrapers.base_scraper import BaseScraper
from src.utils.logger import setup_logger

logger = setup_logger("winner_scrapers")

STATE_WINNER_SOURCES = [
    {
        "name": "Colorado Advanced Industries Winners",
        "url": "https://choosecolorado.com/programs-initiatives/advanced-industries/",
        "funder": "Colorado OEDIT",
        "type": "state",
    },
    {
        "name": "Delaware EDGE Winners",
        "url": "https://business.delaware.gov/edge-grants/",
        "funder": "Delaware DSB",
        "type": "state",
    },
]

FOUNDATION_WINNER_SOURCES = [
    {
        "name": "EQT Foundation Grantees",
        "url": "https://eqtgroup.com/eqt-foundation/",
        "funder": "EQT Foundation",
        "type": "foundation",
    },
    {
        "name": "Sloan Foundation Grants",
        "url": "https://sloan.org/grants",
        "funder": "Alfred P. Sloan Foundation",
        "type": "foundation",
    },
]


class StateWinnerScraper(BaseScraper):
    """Scrape state-level grant award announcements."""

    def __init__(self):
        super().__init__(rate_limit_calls=5, rate_limit_period=60)

    @property
    def name(self) -> str:
        return "state_winners"

    def search(self, keywords: list[str] | None = None) -> list[dict]:
        """Scrape state winner announcements."""
        all_winners: list[dict] = []

        for source in STATE_WINNER_SOURCES:
            try:
                winners = self._scrape_winners(source)
                all_winners.extend(winners)
                logger.info("[state_winners] %s: found %d winners", source["name"], len(winners))
            except Exception as e:
                logger.error("[state_winners] Error scraping %s: %s", source["name"], e)

        return all_winners

    def _scrape_winners(self, source: dict) -> list[dict]:
        """Scrape winners from a single source."""
        winners: list[dict] = []

        try:
            response = self._fetch(source["url"])
            soup = self._parse_html(response.text)

            items = soup.select(
                "article, .card, .winner-item, .success-story, "
                ".portfolio-item, .case-study, li"
            )

            for item in items[:30]:
                try:
                    title_el = item.select_one("h2, h3, h4, a, .title")
                    if not title_el:
                        continue

                    title = title_el.get_text(strip=True)
                    if not title or len(title) < 5:
                        continue

                    text = item.get_text(separator=" ", strip=True).lower()
                    winner_terms = [
                        "awarded", "recipient", "winner", "grantee",
                        "funded", "selected", "grant", "award",
                    ]
                    if not any(term in text for term in winner_terms):
                        continue

                    desc_el = item.select_one("p, .description, .summary")
                    description = desc_el.get_text(strip=True) if desc_el else ""

                    from src.utils.text_processor import TextProcessor
                    amount_min, amount_max, currency = TextProcessor.extract_amount(text)

                    winners.append({
                        "company": title,
                        "funder": source["funder"],
                        "title": title,
                        "description": description,
                        "amount": amount_max or amount_min,
                        "currency": currency or "USD",
                        "source": source["type"],
                        "source_url": source["url"],
                        "scraped_at": datetime.now().isoformat(),
                    })

                except Exception as e:
                    logger.debug("[state_winners] Error parsing item: %s", e)

        except Exception as e:
            logger.warning("[state_winners] Failed to fetch %s: %s", source["url"], e)

        return winners


class FoundationWinnerScraper(BaseScraper):
    """Scrape foundation grant award announcements."""

    def __init__(self):
        super().__init__(rate_limit_calls=5, rate_limit_period=60)

    @property
    def name(self) -> str:
        return "foundation_winners"

    def search(self, keywords: list[str] | None = None) -> list[dict]:
        """Scrape foundation winner announcements."""
        all_winners: list[dict] = []

        for source in FOUNDATION_WINNER_SOURCES:
            try:
                winners = self._scrape_winners(source)
                all_winners.extend(winners)
                logger.info("[foundation_winners] %s: found %d", source["name"], len(winners))
            except Exception as e:
                logger.error("[foundation_winners] Error scraping %s: %s", source["name"], e)

        return all_winners

    def _scrape_winners(self, source: dict) -> list[dict]:
        """Scrape winners from a single foundation source."""
        winners: list[dict] = []

        try:
            response = self._fetch(source["url"])
            soup = self._parse_html(response.text)

            items = soup.select(
                "article, .card, .grant-item, .grantee-item, "
                ".portfolio-item, li, .content-block"
            )

            for item in items[:30]:
                try:
                    title_el = item.select_one("h2, h3, h4, a, .title")
                    if not title_el:
                        continue

                    title = title_el.get_text(strip=True)
                    if not title or len(title) < 5:
                        continue

                    text = item.get_text(separator=" ", strip=True).lower()
                    relevant = [
                        "grant", "award", "funded", "research",
                        "grantee", "recipient", "project",
                    ]
                    if not any(term in text for term in relevant):
                        continue

                    desc_el = item.select_one("p, .description, .summary")
                    description = desc_el.get_text(strip=True) if desc_el else ""

                    from src.utils.text_processor import TextProcessor
                    amount_min, amount_max, currency = TextProcessor.extract_amount(text)

                    winners.append({
                        "company": title,
                        "funder": source["funder"],
                        "title": title,
                        "description": description,
                        "amount": amount_max or amount_min,
                        "currency": currency or "USD",
                        "source": source["type"],
                        "source_url": source["url"],
                        "scraped_at": datetime.now().isoformat(),
                    })

                except Exception as e:
                    logger.debug("[foundation_winners] Error parsing: %s", e)

        except Exception as e:
            logger.warning("[foundation_winners] Failed to fetch %s: %s", source["url"], e)

        return winners


def main():
    parser = argparse.ArgumentParser(description="Scrape state & foundation winners")
    parser.add_argument("--output-state", default="data/winners_state.json")
    parser.add_argument("--output-foundation", default="data/winners_foundation.json")
    args = parser.parse_args()

    # State winners
    try:
        with StateWinnerScraper() as scraper:
            state_winners = scraper.search()
    except Exception as e:
        logger.error("State winner scraper failed: %s", e)
        state_winners = []

    # Foundation winners
    try:
        with FoundationWinnerScraper() as scraper:
            foundation_winners = scraper.search()
    except Exception as e:
        logger.error("Foundation winner scraper failed: %s", e)
        foundation_winners = []

    Path(args.output_state).parent.mkdir(parents=True, exist_ok=True)
    with open(args.output_state, "w") as f:
        json.dump({"winners": state_winners, "updated_at": datetime.now().isoformat()}, f, indent=2)

    with open(args.output_foundation, "w") as f:
        json.dump({"winners": foundation_winners, "updated_at": datetime.now().isoformat()}, f, indent=2)

    print(f"State winners: {len(state_winners)} saved to {args.output_state}")
    print(f"Foundation winners: {len(foundation_winners)} saved to {args.output_foundation}")


if __name__ == "__main__":
    main()
