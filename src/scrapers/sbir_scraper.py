"""SBIR/STTR scraper — Small Business Innovation Research program."""

from datetime import datetime

from src.scrapers.base_scraper import BaseScraper, GrantResult
from src.utils.logger import setup_logger
from src.utils.text_processor import TextProcessor

logger = setup_logger("sbir_scraper")

TARGET_AGENCIES = ["DOE", "NSF", "DOD", "DOI", "EPA", "NASA", "USDA"]

RELEVANT_KEYWORDS = [
    "mineral", "mining", "geological", "geoscience", "critical mineral",
    "lithium", "cobalt", "copper", "AI", "machine learning", "deep learning",
    "subsurface", "exploration", "clean energy", "battery", "rare earth",
    "geospatial", "remote sensing",
]


class SBIRScraper(BaseScraper):
    """Scraper for SBIR.gov — Small Business Innovation Research & STTR.

    Searches for open SBIR/STTR solicitations relevant to Core Element AI.
    API: https://www.sbir.gov/api/solicitations.json
    """

    API_URL = "https://www.sbir.gov/api/solicitations.json"
    DETAIL_URL = "https://www.sbir.gov/node"

    def __init__(self):
        super().__init__(rate_limit_calls=30, rate_limit_period=60)

    @property
    def name(self) -> str:
        return "sbir_sttr"

    def search(self, keywords: list[str] | None = None) -> list[GrantResult]:
        """Search SBIR/STTR for open solicitations.

        Fetches all open solicitations and filters by relevance.
        """
        results: list[GrantResult] = []
        match_keywords = keywords or RELEVANT_KEYWORDS

        try:
            # Fetch open solicitations
            params = {"keyword": "open"}
            response = self._fetch(self.API_URL, params=params)
            solicitations = response.json()

            if not isinstance(solicitations, list):
                solicitations = solicitations.get("results", [])

            logger.info("[sbir] Fetched %d solicitations", len(solicitations))

            for sol in solicitations:
                try:
                    # Filter by target agencies
                    agency = sol.get("agency", "")
                    if agency and agency not in TARGET_AGENCIES:
                        continue

                    # Check keyword relevance
                    title = sol.get("solicitation_title", "") or sol.get("title", "")
                    description = sol.get("solicitation_abstract", "") or sol.get("abstract", "") or ""
                    combined = f"{title} {description}".lower()

                    if not any(kw.lower() in combined for kw in match_keywords):
                        continue

                    grant = self._parse_solicitation(sol)
                    if grant:
                        results.append(grant)

                except Exception as e:
                    logger.warning("[sbir] Failed to parse solicitation: %s", e)

        except Exception as e:
            logger.error("[sbir] API error: %s", e)

        logger.info("[sbir] Found %d relevant solicitations", len(results))
        return results

    def _parse_solicitation(self, sol: dict) -> GrantResult | None:
        """Parse SBIR/STTR solicitation into GrantResult."""
        title = sol.get("solicitation_title", "") or sol.get("title", "")
        if not title:
            return None

        agency = sol.get("agency", "Unknown")
        program = sol.get("program", "SBIR")  # SBIR or STTR
        phase = sol.get("phase", "")

        description = TextProcessor.clean_html(
            sol.get("solicitation_abstract", "") or sol.get("abstract", "") or ""
        )

        # Parse dates
        close_date_str = sol.get("close_date", "") or sol.get("current_closing_date", "")
        deadline = None
        if close_date_str:
            for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d", "%m/%d/%Y"):
                try:
                    deadline = datetime.strptime(close_date_str[:19], fmt).date()
                    break
                except ValueError:
                    continue

        # Typical SBIR/STTR amounts
        amount_min, amount_max = self._phase_amounts(phase)

        # Build URL
        sol_number = sol.get("solicitation_number", "") or sol.get("id", "")
        url = sol.get("solicitation_url", "") or sol.get("url", "")
        if not url and sol_number:
            url = f"https://www.sbir.gov/node/{sol_number}"

        # Tags
        tags = ["SBIR" if "SBIR" in program else "STTR"]
        combined = f"{title} {description}".lower()
        if any(kw in combined for kw in ["mineral", "mining", "geological"]):
            tags.append("mining")
        if any(kw in combined for kw in ["ai", "machine learning", "deep learning"]):
            tags.append("AI")
        if any(kw in combined for kw in ["critical mineral", "lithium", "cobalt", "copper"]):
            tags.append("critical minerals")
        if any(kw in combined for kw in ["clean energy", "green", "sustainable"]):
            tags.append("cleantech")

        return GrantResult(
            title=f"[{program} {phase}] {title}",
            funder=f"{agency} - {program}",
            description=description,
            amount_min=amount_min,
            amount_max=amount_max,
            currency="USD",
            deadline=deadline,
            url=url,
            source="sbir_sttr",
            grant_type="federal",
            industry_tags=tags,
            eligibility_text="Small business concern (SBC) that is organized for-profit, US-based, >50% US-owned",
        )

    @staticmethod
    def _phase_amounts(phase: str) -> tuple[int, int]:
        """Return typical amount range for SBIR/STTR phase."""
        phase_lower = phase.lower() if phase else ""
        if "i" in phase_lower and "ii" not in phase_lower:
            return 50000, 275000  # Phase I
        if "ii" in phase_lower:
            return 500000, 1500000  # Phase II
        if "iii" in phase_lower:
            return 1000000, 5000000  # Phase III
        return 50000, 1500000  # Unknown phase


def main():
    """CLI entry point for GitHub Actions."""
    import argparse
    import json
    from pathlib import Path
    from dataclasses import asdict

    parser = argparse.ArgumentParser(description="Scrape SBIR/STTR")
    parser.add_argument("--output", default="data/sbir_raw.json")
    args = parser.parse_args()

    scraper = SBIRScraper()
    results = scraper.search()
    scraper.close()

    output = [asdict(r) for r in results]
    for item in output:
        if item.get("deadline"):
            item["deadline"] = str(item["deadline"])

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w") as f:
        json.dump(output, f, indent=2)

    print(f"SBIR/STTR: {len(output)} grants saved to {args.output}")


if __name__ == "__main__":
    main()
