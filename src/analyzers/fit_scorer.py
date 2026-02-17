"""Fit scorer — calculates how well a grant matches Core Element AI."""

from pathlib import Path

import yaml

from src.utils.logger import setup_logger
from src.utils.text_processor import TextProcessor

logger = setup_logger("fit_scorer")

CONFIG_DIR = Path(__file__).parent.parent.parent / "config"


class FitScorer:
    """Calculate fit score (0-100%) between a grant and Core Element AI profile.

    Uses weighted criteria from config/filters.yaml.
    """

    def __init__(self):
        self.profile = self._load_config("core_element_profile.yaml")
        self.filters = self._load_config("filters.yaml")
        self.keywords_config = self._load_config("keywords.yaml")
        self.weights = self.filters.get("scoring", {}).get("weights", {})

    def _load_config(self, filename: str) -> dict:
        with open(CONFIG_DIR / filename) as f:
            return yaml.safe_load(f)

    def score(
        self,
        title: str,
        description: str,
        funder: str = "",
        grant_type: str = "",
        eligibility_text: str = "",
        amount_min: int | None = None,
        amount_max: int | None = None,
        deadline_days: int | None = None,
        complexity: int | None = None,
    ) -> dict:
        """Calculate comprehensive fit score.

        Returns:
            Dict with overall score and breakdown by category.
        """
        combined_text = f"{title} {description} {funder} {eligibility_text}"

        scores = {
            "keyword_match": self._keyword_score(combined_text),
            "industry_match": self._industry_score(combined_text),
            "eligibility_match": self._eligibility_score(eligibility_text),
            "amount_range": self._amount_score(amount_min, amount_max),
            "deadline_feasibility": self._deadline_score(deadline_days),
            "complexity_inverse": self._complexity_score(complexity),
            "geographic_match": self._geographic_score(combined_text),
        }

        # Calculate weighted overall score
        overall = 0.0
        for key, score_val in scores.items():
            weight = self.weights.get(key, 0.1)
            overall += score_val * weight

        # Normalize to 0-100
        overall_pct = min(100, max(0, int(overall * 100)))

        # Bonus for high-priority sources
        high_priority = self.filters.get("priority", {}).get("high_priority_sources", [])
        if any(hp.lower() in funder.lower() for hp in high_priority):
            overall_pct = min(100, overall_pct + 5)

        return {
            "overall": overall_pct,
            "breakdown": {k: int(v * 100) for k, v in scores.items()},
            "recommendation": self._recommendation(overall_pct),
        }

    def _keyword_score(self, text: str) -> float:
        """Score based on keyword matches."""
        all_keywords = []
        for category in self.keywords_config.get("primary", {}).values():
            all_keywords.extend(category)
        for category in self.keywords_config.get("secondary", {}).values():
            all_keywords.extend(category)

        primary_kws = []
        for category in self.keywords_config.get("primary", {}).values():
            primary_kws.extend(category)

        # Primary keywords have more weight
        primary_score = TextProcessor.keyword_match_score(text, primary_kws)
        all_score = TextProcessor.keyword_match_score(text, all_keywords)

        return primary_score * 0.7 + all_score * 0.3

    def _industry_score(self, text: str) -> float:
        """Score based on industry alignment."""
        industries = self.profile.get("company", {}).get("industries", [])
        minerals = [m["name"] for m in self.profile.get("focus_minerals", {}).get("primary", [])]
        minerals += [m["name"] for m in self.profile.get("focus_minerals", {}).get("secondary", [])]

        all_terms = industries + minerals
        return TextProcessor.keyword_match_score(text, all_terms)

    def _eligibility_score(self, eligibility_text: str) -> float:
        """Score eligibility match."""
        if not eligibility_text:
            return 0.5  # Unknown = neutral

        lower = eligibility_text.lower()
        accepted = self.filters.get("eligibility", {}).get("legal_structures_accepted", [])
        excluded = self.filters.get("eligibility", {}).get("legal_structures_excluded", [])

        # Check for explicit exclusion
        for excl in excluded:
            if excl.lower() in lower and "only" in lower:
                return 0.0

        # Check for explicit inclusion
        for acc in accepted:
            if acc.lower() in lower:
                return 1.0

        # Check for small business
        if "small business" in lower:
            return 0.9

        return 0.5

    def _amount_score(self, amount_min: int | None, amount_max: int | None) -> float:
        """Score based on funding amount range."""
        if amount_min is None and amount_max is None:
            return 0.5

        pref_min = self.filters.get("amount", {}).get("preferred_min_usd", 25000)
        pref_max = self.filters.get("amount", {}).get("preferred_max_usd", 2000000)
        abs_min = self.filters.get("amount", {}).get("min_usd", 10000)

        amount = amount_max or amount_min or 0

        if amount < abs_min:
            return 0.2
        if pref_min <= amount <= pref_max:
            return 1.0
        if amount > pref_max:
            return 0.8  # Large grants are still good
        return 0.6

    def _deadline_score(self, deadline_days: int | None) -> float:
        """Score based on deadline feasibility."""
        if deadline_days is None:
            return 0.5

        if deadline_days < 3:
            return 0.1  # Too soon
        if deadline_days < 7:
            return 0.4  # Very tight
        if deadline_days < 14:
            return 0.7  # Tight but possible
        if deadline_days < 60:
            return 1.0  # Ideal
        if deadline_days < 180:
            return 0.9  # Good planning horizon
        return 0.7  # Far out

    def _complexity_score(self, complexity: int | None) -> float:
        """Score inversely proportional to complexity (simpler = better ROI)."""
        if complexity is None:
            return 0.5
        # Complexity 1 = score 1.0, Complexity 10 = score 0.1
        return max(0.1, 1.0 - (complexity - 1) * 0.1)

    def _geographic_score(self, text: str) -> float:
        """Score geographic match."""
        primary_geo = self.filters.get("eligibility", {}).get("geographic", {}).get("primary", [])
        secondary_geo = self.filters.get("eligibility", {}).get("geographic", {}).get("secondary", [])

        primary_match = TextProcessor.keyword_match_score(text, primary_geo)
        secondary_match = TextProcessor.keyword_match_score(text, secondary_geo)

        if primary_match > 0:
            return min(1.0, 0.7 + primary_match * 0.3)
        if secondary_match > 0:
            return 0.5 + secondary_match * 0.3
        return 0.3

    @staticmethod
    def _recommendation(score: int) -> str:
        """Generate recommendation based on fit score."""
        if score >= 90:
            return "HIGHLY RECOMMENDED - Excellent fit, prioritize this application"
        if score >= 80:
            return "STRONGLY RECOMMENDED - Very good fit, consider applying"
        if score >= 70:
            return "RECOMMENDED - Good fit, worth pursuing"
        if score >= 50:
            return "MODERATE FIT - Review details carefully before applying"
        if score >= 30:
            return "LOW FIT - May not be worth the effort, review requirements"
        return "NOT RECOMMENDED - Poor fit with Core Element AI profile"
