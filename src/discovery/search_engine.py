"""
Search-based grant discovery using multiple query strategies.

More reliable than HTML scraping (sites change structure frequently).
Uses a multi-strategy approach: funder search, deadline search,
topic search, program type search, and geography search.
"""

import hashlib
import json
import re
from datetime import datetime, timedelta
from pathlib import Path

from src.utils.logger import setup_logger

logger = setup_logger("search_engine")


class GrantSearchEngine:
    """Multi-strategy search engine for grant discovery."""

    def __init__(self):
        self.search_strategies = [
            self.search_by_funder,
            self.search_by_deadline,
            self.search_by_topic,
            self.search_by_program_type,
            self.search_by_geography,
        ]

    def discover_all_grants(self):
        """Run all search strategies and consolidate results."""
        all_grants = []

        for strategy in self.search_strategies:
            try:
                grants = strategy()
                all_grants.extend(grants)
                logger.info("Strategy %s found %d grants", strategy.__name__, len(grants))
            except Exception as e:
                logger.warning("Strategy %s failed: %s", strategy.__name__, e)

        unique_grants = self.deduplicate(all_grants)
        validated = self.validate_grants(unique_grants)

        logger.info("Total: %d raw, %d unique, %d validated", len(all_grants), len(unique_grants), len(validated))
        return validated

    def search_by_funder(self):
        """Strategy 1: Search by known funders."""
        funders = [
            "ARPA-E",
            "DOE Office of Science",
            "DOE EERE",
            "NSF SBIR",
            "EQT Foundation",
            "Horizon Europe",
            "Colorado OEDIT",
            "Quebec MERN",
            "BHP",
        ]

        grants = []
        for funder in funders:
            query = f"{funder} grants 2026 open applications"
            results = self.execute_search(query)
            grants.extend(self.parse_search_results(results, funder))

        return grants

    def search_by_deadline(self):
        """Strategy 2: Search by deadline timeframes."""
        timeframes = [
            "grants closing February 2026",
            "grants deadline March 2026",
            "grants closing April 2026",
            "grants deadline Q2 2026",
        ]

        grants = []
        for timeframe in timeframes:
            query = f"critical minerals AI {timeframe}"
            results = self.execute_search(query)
            grants.extend(self.parse_search_results(results))

        return grants

    def search_by_topic(self):
        """Strategy 3: Search by topic/technology."""
        topics = [
            "critical minerals grants 2026",
            "AI exploration grants",
            "mining technology grants",
            "lithium copper cobalt grants",
            "geospatial AI grants",
            "geothermal energy grants 2026",
        ]

        grants = []
        for topic in topics:
            results = self.execute_search(topic)
            grants.extend(self.parse_search_results(results))

        return grants

    def search_by_program_type(self):
        """Strategy 4: Search by program type."""
        programs = [
            "SBIR STTR 2026 critical minerals",
            "proof of concept grants mining",
            "advanced industries grants",
            "foundation grants deeptech",
            "horizon europe critical raw materials",
            "ARPA-E SUPERHOT geothermal",
            "ARPA-E RECOVER critical minerals",
        ]

        grants = []
        for program in programs:
            results = self.execute_search(program)
            grants.extend(self.parse_search_results(results))

        return grants

    def search_by_geography(self):
        """Strategy 5: Search by location."""
        locations = [
            "Colorado mining grants 2026",
            "Delaware EDGE grant",
            "Quebec exploration grants",
            "European Union critical minerals",
            "Canada mining innovation grants",
        ]

        grants = []
        for location in locations:
            results = self.execute_search(location)
            grants.extend(self.parse_search_results(results))

        return grants

    def execute_search(self, query):
        """Execute search query.

        This method can be extended with actual search APIs:
        - Google Custom Search API
        - Bing Search API
        - Grants.gov API
        - Web scraping of search results

        Returns:
            List of raw search result dicts.
        """
        logger.debug("Search query: %s", query)
        # Actual search integration goes here
        # For now returns empty; known grants are added via add_known_grants()
        return []

    def parse_search_results(self, results, funder=None):
        """Parse search results into grant objects."""
        grants = []

        if not results:
            return grants

        for result in results:
            grant = self.extract_grant_info(result, funder)
            if grant:
                grants.append(grant)

        return grants

    def extract_grant_info(self, result, funder=None):
        """Extract grant information from a search result."""
        title = result.get("title", "")
        url = result.get("url", "")
        snippet = result.get("snippet", "")

        if not title or not url:
            return None

        grant_id = hashlib.md5(f"{title}{url}".encode()).hexdigest()[:12]

        grant = {
            "id": grant_id,
            "title": title,
            "funder": funder or self._extract_funder(title, snippet),
            "description": snippet,
            "url": url,
            "amount_min": 0,
            "amount_max": 0,
            "currency": "USD",
            "deadline": self._extract_deadline(snippet),
            "source": "search_discovery",
            "grant_type": self._infer_grant_type(funder or "", url),
            "industry_tags": [],
            "eligibility": "",
            "scraped_at": datetime.now().isoformat(),
        }

        return grant

    def _extract_funder(self, title, text):
        """Try to extract funder name from text."""
        known_funders = {
            "ARPA-E": ["arpa-e", "arpa e"],
            "DOE": ["department of energy", "doe "],
            "NSF": ["national science foundation", "nsf "],
            "EQT Foundation": ["eqt foundation"],
            "Horizon Europe": ["horizon europe", "horizon 2020"],
            "BHP": ["bhp"],
        }

        combined = f"{title} {text}".lower()
        for funder, patterns in known_funders.items():
            if any(p in combined for p in patterns):
                return funder

        return "Unknown"

    def _extract_deadline(self, text):
        """Try to extract deadline date from text."""
        patterns = [
            r"deadline[:\s]+(\w+\s+\d{1,2},?\s+\d{4})",
            r"due[:\s]+(\w+\s+\d{1,2},?\s+\d{4})",
            r"closes?[:\s]+(\w+\s+\d{1,2},?\s+\d{4})",
            r"(\d{1,2}/\d{1,2}/\d{4})",
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1)

        return ""

    def _infer_grant_type(self, funder, url):
        """Infer grant type from funder and URL."""
        funder_lower = funder.lower()
        url_lower = url.lower()

        if any(f in funder_lower for f in ["arpa-e", "doe", "nsf", "nih"]):
            return "federal"
        if "grants.gov" in url_lower:
            return "federal"
        if any(f in funder_lower for f in ["foundation", "sloan", "eqt"]):
            return "private_foundation"
        if "horizon" in funder_lower or "europa.eu" in url_lower:
            return "eu"
        if any(f in funder_lower for f in ["colorado", "delaware", "quebec"]):
            return "state"
        if any(f in funder_lower for f in ["bhp", "rio tinto"]):
            return "corporate"

        return "other"

    def deduplicate(self, grants):
        """Remove duplicate grants based on URL and title similarity."""
        seen_urls = set()
        seen_titles = set()
        unique = []

        for grant in grants:
            url = grant.get("url", "").rstrip("/").lower()
            title_key = re.sub(r"[^a-z0-9]", "", grant.get("title", "").lower())[:60]

            if url in seen_urls or title_key in seen_titles:
                continue

            if url:
                seen_urls.add(url)
            if title_key:
                seen_titles.add(title_key)

            unique.append(grant)

        return unique

    def validate_grants(self, grants):
        """Validate each grant has required fields."""
        valid = []
        for grant in grants:
            if self.is_valid_grant(grant):
                valid.append(grant)
            else:
                logger.debug("Invalid grant skipped: %s", grant.get("title", "?")[:50])
        return valid

    def is_valid_grant(self, grant):
        """Check if grant has all required fields."""
        required = ["id", "title", "funder", "url"]
        return all(grant.get(field) for field in required)
