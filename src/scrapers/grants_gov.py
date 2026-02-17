"""Grants.gov scraper — US federal grants database."""

import os
from datetime import datetime

from src.scrapers.base_scraper import BaseScraper, GrantResult
from src.utils.logger import setup_logger
from src.utils.text_processor import TextProcessor

logger = setup_logger("grants_gov")

# Default keywords aligned with Core Element AI's focus
DEFAULT_KEYWORDS = [
    "critical minerals",
    "mineral exploration",
    "AI geology",
    "mining technology",
    "geological survey",
    "clean energy minerals",
    "lithium exploration",
    "battery metals",
    "subsurface prediction",
    "geospatial AI",
]


class GrantsGovScraper(BaseScraper):
    """Scraper for Grants.gov federal grants database.

    Uses the Grants.gov REST API to search for relevant federal grants.
    API docs: https://www.grants.gov/web-api
    """

    BASE_URL = "https://api.grants.gov/v1/api"

    def __init__(self):
        super().__init__(rate_limit_calls=100, rate_limit_period=3600)
        self.api_key = os.getenv("GRANTS_GOV_API_KEY", "")

    @property
    def name(self) -> str:
        return "grants_gov"

    def search(self, keywords: list[str] | None = None) -> list[GrantResult]:
        """Search Grants.gov for relevant grants.

        Args:
            keywords: Keywords to search for. Uses defaults if None.

        Returns:
            List of GrantResult objects.
        """
        keywords = keywords or DEFAULT_KEYWORDS
        all_results: list[GrantResult] = []
        seen_urls: set[str] = set()

        for keyword in keywords:
            try:
                grants = self._search_keyword(keyword)
                for grant in grants:
                    if grant.url not in seen_urls:
                        seen_urls.add(grant.url)
                        all_results.append(grant)
            except Exception as e:
                logger.error("[grants_gov] Error searching '%s': %s", keyword, e)

        logger.info("[grants_gov] Found %d unique grants across %d keywords", len(all_results), len(keywords))
        return all_results

    def _search_keyword(self, keyword: str) -> list[GrantResult]:
        """Search for a single keyword."""
        results: list[GrantResult] = []

        try:
            # Grants.gov API search endpoint
            params = {
                "keyword": keyword,
                "oppStatuses": "forecasted|posted",
                "sortBy": "openDate|desc",
                "rows": 25,
                "startRecordNum": 0,
            }

            response = self._post(
                f"{self.BASE_URL}/search",
                json=params,
                headers={"Content-Type": "application/json"},
            )
            data = response.json()

            opportunities = data.get("oppHits", [])
            logger.debug("[grants_gov] '%s' returned %d results", keyword, len(opportunities))

            for opp in opportunities:
                try:
                    grant = self._parse_opportunity(opp)
                    if grant:
                        results.append(grant)
                except Exception as e:
                    logger.warning("[grants_gov] Failed to parse opportunity: %s", e)

        except Exception as e:
            logger.error("[grants_gov] API error for '%s': %s", keyword, e)

        return results

    def _parse_opportunity(self, opp: dict) -> GrantResult | None:
        """Parse a Grants.gov opportunity into a GrantResult."""
        title = opp.get("title", "")
        if not title:
            return None

        opp_number = opp.get("number", "")
        description = TextProcessor.clean_html(opp.get("synopsis", {}).get("synopsisDesc", "") or "")

        # Parse dates
        close_date_str = opp.get("closeDate", "")
        deadline = None
        if close_date_str:
            try:
                deadline = datetime.strptime(close_date_str[:10], "%m/%d/%Y").date()
            except (ValueError, IndexError):
                try:
                    deadline = datetime.strptime(close_date_str[:10], "%Y-%m-%d").date()
                except (ValueError, IndexError):
                    pass

        # Parse amounts
        award_floor = opp.get("awardFloor", 0) or 0
        award_ceiling = opp.get("awardCeiling", 0) or 0

        # Build URL
        url = f"https://www.grants.gov/search-results-detail/{opp.get('id', opp_number)}"

        # Extract agency/funder
        funder = opp.get("agencyName", "") or opp.get("agency", {}).get("name", "")

        # Eligibility
        eligible_applicants = opp.get("eligibleApplicants", [])
        eligibility_text = ", ".join(eligible_applicants) if isinstance(eligible_applicants, list) else str(eligible_applicants)

        # Tags
        tags = self._extract_tags(title, description)

        return GrantResult(
            title=title,
            funder=funder,
            description=description,
            amount_min=int(award_floor) if award_floor else None,
            amount_max=int(award_ceiling) if award_ceiling else None,
            currency="USD",
            deadline=deadline,
            url=url,
            source="grants_gov",
            grant_type="federal",
            industry_tags=tags,
            eligibility_text=eligibility_text,
        )

    @staticmethod
    def _extract_tags(title: str, description: str) -> list[str]:
        """Extract industry tags from title and description."""
        combined = f"{title} {description}".lower()
        tags = []
        tag_keywords = {
            "mining": ["mining", "mineral", "ore", "extraction"],
            "AI": ["artificial intelligence", "machine learning", "deep learning", "AI", "neural network"],
            "geology": ["geology", "geological", "geoscience", "subsurface"],
            "critical minerals": ["critical mineral", "lithium", "cobalt", "copper", "rare earth"],
            "cleantech": ["clean energy", "green", "sustainable", "renewable", "climate"],
            "exploration": ["exploration", "discovery", "prospecting", "survey"],
            "geospatial": ["geospatial", "remote sensing", "satellite", "GIS"],
        }
        for tag, keywords in tag_keywords.items():
            if any(kw in combined for kw in keywords):
                tags.append(tag)
        return tags

    def get_opportunity_details(self, opp_id: str) -> dict:
        """Fetch detailed information for a specific opportunity."""
        try:
            response = self._fetch(f"{self.BASE_URL}/opportunity/{opp_id}")
            return response.json()
        except Exception as e:
            logger.error("[grants_gov] Failed to get details for %s: %s", opp_id, e)
            return {}


def main():
    """CLI entry point for GitHub Actions."""
    import argparse
    import json
    from pathlib import Path
    from dataclasses import asdict

    parser = argparse.ArgumentParser(description="Scrape grants.gov")
    parser.add_argument("--output", default="data/grants_gov_raw.json")
    parser.add_argument("--test", action="store_true")
    args = parser.parse_args()

    scraper = GrantsGovScraper()
    results = scraper.search()
    scraper.close()

    output = [asdict(r) for r in results]
    # Convert date objects to strings
    for item in output:
        if item.get("deadline"):
            item["deadline"] = str(item["deadline"])

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w") as f:
        json.dump(output, f, indent=2)

    print(f"grants.gov: {len(output)} grants saved to {args.output}")


if __name__ == "__main__":
    main()
