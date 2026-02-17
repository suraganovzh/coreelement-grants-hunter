"""Eligibility checker — verifies if Core Element AI qualifies for a grant."""

from pathlib import Path

import yaml

from src.utils.logger import setup_logger
from src.utils.api_clients import GroqClient

logger = setup_logger("eligibility_checker")

CONFIG_DIR = Path(__file__).parent.parent.parent / "config"


class EligibilityChecker:
    """Checks whether Core Element AI is eligible for a given grant.

    Uses both rule-based checks and AI analysis for thorough evaluation.
    """

    def __init__(self, groq_client: GroqClient | None = None):
        self.groq = groq_client or GroqClient()
        self.profile = self._load_profile()
        self.filters = self._load_filters()

    def _load_profile(self) -> dict:
        with open(CONFIG_DIR / "core_element_profile.yaml") as f:
            return yaml.safe_load(f)

    def _load_filters(self) -> dict:
        with open(CONFIG_DIR / "filters.yaml") as f:
            return yaml.safe_load(f)

    def check(self, grant_title: str, grant_text: str, grant_type: str = "") -> dict:
        """Run full eligibility check.

        Args:
            grant_title: Grant title.
            grant_text: Full grant text (description + eligibility + requirements).
            grant_type: Grant type (federal, private, international).

        Returns:
            Dict with eligible, reasons, blockers, confidence.
        """
        # Step 1: Rule-based quick checks
        rule_result = self._rule_based_check(grant_text)

        # Step 2: AI-powered deep check (if not clearly disqualified)
        if rule_result["eligible"] or rule_result["confidence"] < 0.7:
            ai_result = self._ai_check(grant_title, grant_text)
            return self._merge_results(rule_result, ai_result)

        return rule_result

    def _rule_based_check(self, text: str) -> dict:
        """Fast rule-based eligibility check."""
        lower = text.lower()
        eligible = True
        reasons: list[str] = []
        blockers: list[str] = []
        confidence = 0.5

        # Check for excluded legal structures
        excluded = self.filters.get("eligibility", {}).get("legal_structures_excluded", [])
        for excl in excluded:
            excl_lower = excl.lower()
            # Check if grant is ONLY for excluded types
            if excl_lower in lower:
                # More nuanced: "non-profit only" is a blocker, but "non-profit and for-profit" is not
                if "only" in lower[max(0, lower.index(excl_lower) - 20):lower.index(excl_lower) + len(excl_lower) + 20]:
                    blockers.append(f"Requires: {excl}")
                    eligible = False
                    confidence = 0.8

        # Check for accepted structures
        accepted = self.filters.get("eligibility", {}).get("legal_structures_accepted", [])
        for acc in accepted:
            if acc.lower() in lower:
                reasons.append(f"Accepts: {acc}")
                confidence = max(confidence, 0.7)

        # Check US-specific requirements for non-US grants
        if "us-based" in lower or "united states only" in lower:
            reasons.append("US-based entity accepted (Core Element is Delaware S-Corp)")

        # Check small business criteria
        if "small business" in lower or "sbc" in lower:
            reasons.append("Small business eligible (Core Element qualifies)")

        # Check for equity requirements
        if "equity" in lower:
            if "no equity" in lower or "non-dilutive" in lower:
                reasons.append("Non-dilutive funding")
            else:
                reasons.append("May require equity - review terms")

        return {
            "eligible": eligible,
            "reasons": reasons,
            "blockers": blockers,
            "confidence": confidence,
            "method": "rule_based",
        }

    def _ai_check(self, title: str, text: str) -> dict:
        """AI-powered eligibility analysis using Groq."""
        profile_summary = self._get_profile_summary()
        try:
            result = self.groq.check_eligibility(
                f"Title: {title}\n\n{text[:3000]}",
                profile_summary,
            )
            result["method"] = "ai"
            return result
        except Exception as e:
            logger.error("AI eligibility check failed: %s", e)
            return {"eligible": True, "reasons": [], "blockers": [], "confidence": 0.3, "method": "ai_failed"}

    def _merge_results(self, rule: dict, ai: dict) -> dict:
        """Merge rule-based and AI results."""
        # If both agree it's blocked, definitely blocked
        if not rule.get("eligible") and not ai.get("eligible"):
            return {
                "eligible": False,
                "reasons": list(set(rule.get("reasons", []) + ai.get("reasons", []))),
                "blockers": list(set(rule.get("blockers", []) + ai.get("blockers", []))),
                "confidence": max(rule.get("confidence", 0), ai.get("confidence", 0)),
                "method": "merged",
            }

        # If either says eligible, lean towards eligible (conservative approach: don't miss grants)
        return {
            "eligible": True,
            "reasons": list(set(rule.get("reasons", []) + ai.get("reasons", []))),
            "blockers": list(set(rule.get("blockers", []) + ai.get("blockers", []))),
            "confidence": (rule.get("confidence", 0.5) + ai.get("confidence", 0.5)) / 2,
            "fit_score": ai.get("fit_score", 50),
            "complexity_score": ai.get("complexity_score", 5),
            "key_requirements": ai.get("key_requirements", []),
            "method": "merged",
        }

    def _get_profile_summary(self) -> str:
        """Create a concise profile summary for AI prompts."""
        company = self.profile.get("company", {})
        tech = self.profile.get("technology", {})
        vp = self.profile.get("value_propositions", {})

        return f"""Company: {company.get('name', 'Core Element AI')}
Legal: {company.get('legal_structure', 'S-Corp')}, {company.get('incorporation_state', 'Delaware')}
Industry: {', '.join(company.get('industries', []))}
Technology: {tech.get('name', 'Probabilistic AI Modeling for Geological Exploration')}
TRL: {tech.get('trl_level', 7)}
Size: {company.get('size', {}).get('employees', '1-10')} employees, Small Business
Key Metrics: {'; '.join(m['value'] + ' - ' + m['description'] for m in vp.get('key_metrics', [])[:4])}
Focus: Critical minerals (Li, Cu, Co, Al, Fe) for green energy transition"""
