"""Complexity scorer — estimates application complexity and preparation time."""

from src.utils.logger import setup_logger

logger = setup_logger("complexity_scorer")

# Complexity indicators and their weights
COMPLEXITY_INDICATORS = {
    "high": {
        "keywords": [
            "full proposal", "detailed budget", "matching funds", "cost sharing",
            "partnership required", "consortium", "milestone deliverables",
            "peer review", "multi-phase", "environmental assessment",
            "data management plan", "IRB approval", "NEPA compliance",
        ],
        "weight": 2,
    },
    "medium": {
        "keywords": [
            "technical narrative", "budget justification", "letter of support",
            "biographical sketch", "references", "work plan",
            "evaluation criteria", "commercialization plan", "sustainability plan",
        ],
        "weight": 1,
    },
    "low": {
        "keywords": [
            "simple application", "short form", "pitch deck", "one-page",
            "executive summary only", "online form", "expression of interest",
        ],
        "weight": -1,
    },
}

# Prep time estimates by complexity level (hours)
PREP_TIME_MAP = {
    1: 4,    # Very simple form
    2: 8,    # Simple application
    3: 12,   # Simple with supporting docs
    4: 16,   # Standard application
    5: 24,   # Standard with technical details
    6: 32,   # Detailed application
    7: 48,   # Complex with partnerships
    8: 64,   # Very complex, multi-part
    9: 80,   # Major proposal
    10: 100, # Full federal/EU proposal
}


class ComplexityScorer:
    """Estimate grant application complexity and preparation time."""

    def score(self, grant_text: str, grant_type: str = "", amount: int | None = None) -> dict:
        """Calculate complexity score and estimated preparation time.

        Args:
            grant_text: Full grant description and requirements.
            grant_type: Type of grant (federal, private, international).
            amount: Funding amount (larger grants tend to be more complex).

        Returns:
            Dict with score (1-10), estimated_hours, breakdown, and classification.
        """
        lower = grant_text.lower()

        # Count complexity indicators
        high_count = sum(1 for kw in COMPLEXITY_INDICATORS["high"]["keywords"] if kw in lower)
        med_count = sum(1 for kw in COMPLEXITY_INDICATORS["medium"]["keywords"] if kw in lower)
        low_count = sum(1 for kw in COMPLEXITY_INDICATORS["low"]["keywords"] if kw in lower)

        # Base score calculation
        raw_score = (
            high_count * COMPLEXITY_INDICATORS["high"]["weight"]
            + med_count * COMPLEXITY_INDICATORS["medium"]["weight"]
            + low_count * COMPLEXITY_INDICATORS["low"]["weight"]
        )

        # Adjust for grant type
        type_adjustment = {
            "federal": 2,
            "international": 2,
            "private": 0,
            "corporate": -1,
        }
        raw_score += type_adjustment.get(grant_type, 0)

        # Adjust for amount
        if amount:
            if amount >= 1_000_000:
                raw_score += 2
            elif amount >= 500_000:
                raw_score += 1
            elif amount < 50_000:
                raw_score -= 1

        # Normalize to 1-10
        score = max(1, min(10, raw_score + 3))

        estimated_hours = PREP_TIME_MAP.get(score, 40)

        classification = self._classify(score)

        return {
            "score": score,
            "estimated_hours": estimated_hours,
            "classification": classification,
            "breakdown": {
                "high_complexity_indicators": high_count,
                "medium_complexity_indicators": med_count,
                "simplicity_indicators": low_count,
                "type_adjustment": type_adjustment.get(grant_type, 0),
            },
        }

    @staticmethod
    def _classify(score: int) -> str:
        """Classify complexity level."""
        if score <= 3:
            return "Simple application (form + pitch deck)"
        if score <= 6:
            return "Medium (detailed technical + financials)"
        return "Complex (full proposal + partnerships + milestones)"
