"""Eligibility checker — verifies if Core Element AI qualifies for a grant.

Enhanced with partnership-aware eligibility pathways (STTR, EU Consortium).
"""

from pathlib import Path

import yaml

from src.utils.logger import setup_logger
from src.utils.api_clients import GroqClient

logger = setup_logger("eligibility_checker")

CONFIG_DIR = Path(__file__).parent.parent.parent / "config"

# Known partnerships that enable alternative eligibility pathways
COMPANY_PARTNERSHIPS = {
    "colorado_school_of_mines": {
        "name": "Colorado School of Mines",
        "type": "university",
        "location": "Colorado",
        "enables": ["STTR", "state_grants", "EU_consortiums", "foundation_grants"],
        "contact_note": "Research collaboration partner",
    },
    "stanford_mineral_x": {
        "name": "Stanford Mineral-X",
        "type": "research_center",
        "location": "California",
        "enables": ["STTR", "collaborative_grants", "foundation_grants"],
        "contact_note": "Innovation program partner",
    },
    "lawrence_berkeley_lab": {
        "name": "Lawrence Berkeley National Laboratory",
        "type": "national_lab",
        "location": "California",
        "enables": ["STTR", "DOE_partnerships", "EU_connections", "national_lab_grants"],
        "contact_note": "Research collaboration partner",
    },
}


class EligibilityChecker:
    """Checks whether Core Element AI is eligible for a given grant.

    Uses both rule-based checks and AI analysis for thorough evaluation.
    Enhanced with partnership-aware pathways for grants requiring
    university or nonprofit affiliation.
    """

    def __init__(self, groq_client: GroqClient | None = None):
        self.groq = groq_client or GroqClient()
        self.profile = self._load_profile()
        self.filters = self._load_filters()
        self.partnerships = COMPANY_PARTNERSHIPS

    def _load_profile(self) -> dict:
        with open(CONFIG_DIR / "core_element_profile.yaml") as f:
            return yaml.safe_load(f)

    def _load_filters(self) -> dict:
        with open(CONFIG_DIR / "filters.yaml") as f:
            return yaml.safe_load(f)

    def check(self, grant_title: str, grant_text: str, grant_type: str = "") -> dict:
        """Run full eligibility check including partnership pathways.

        Args:
            grant_title: Grant title.
            grant_text: Full grant text (description + eligibility + requirements).
            grant_type: Grant type (federal, private, international, state).

        Returns:
            Dict with eligible, reasons, blockers, confidence, and
            partnership pathway info if applicable.
        """
        # Step 1: Rule-based quick checks
        rule_result = self._rule_based_check(grant_text)

        # Step 2: Partnership pathway check (can override blockers)
        partnership_result = self._check_partnership_pathways(grant_text, grant_type)
        if partnership_result:
            rule_result = self._apply_partnership_override(rule_result, partnership_result)

        # Step 3: AI-powered deep check (if not clearly disqualified)
        if rule_result["eligible"] or rule_result["confidence"] < 0.7:
            ai_result = self._ai_check(grant_title, grant_text)
            merged = self._merge_results(rule_result, ai_result)
            if partnership_result:
                merged["partnership_pathway"] = partnership_result
            return merged

        if partnership_result:
            rule_result["partnership_pathway"] = partnership_result
        return rule_result

    def check_flexible(self, grant: dict) -> dict:
        """Check eligibility with full partnership awareness.

        Args:
            grant: Full grant dict with title, description, eligibility, etc.

        Returns:
            Dict with direct_eligible, sttr_eligible, partnership_path,
            recommended_partner, and standard eligibility fields.
        """
        title = grant.get("title", "")
        text = " ".join([
            grant.get("description", ""),
            grant.get("eligibility", ""),
            grant.get("eligibility_text", ""),
            grant.get("requirements", ""),
        ])
        grant_type = grant.get("grant_type", "")

        # Standard check
        result = self.check(title, text, grant_type)

        # Determine pathway
        pathway = {
            "direct_eligible": result.get("eligible", False),
            "sttr_eligible": False,
            "consortium_eligible": False,
            "partnership_path": None,
            "recommended_partner": None,
        }

        lower = text.lower()

        # Check STTR pathway
        if not pathway["direct_eligible"]:
            sttr_terms = ["sttr", "university", "research institution", "nonprofit"]
            if any(term in lower for term in sttr_terms):
                for key, partner in self.partnerships.items():
                    if "STTR" in partner["enables"]:
                        pathway["sttr_eligible"] = True
                        pathway["partnership_path"] = "STTR"
                        pathway["recommended_partner"] = partner["name"]
                        break

        # Check EU consortium pathway
        if not pathway["direct_eligible"] and grant_type in ("international", "eu"):
            eu_terms = ["consortium", "eu partner", "european partner"]
            if any(term in lower for term in eu_terms):
                for key, partner in self.partnerships.items():
                    if "EU_connections" in partner["enables"]:
                        pathway["consortium_eligible"] = True
                        pathway["partnership_path"] = "EU_Consortium"
                        pathway["recommended_partner"] = partner["name"]
                        break

        # Check foundation partnership pathway
        if not pathway["direct_eligible"]:
            foundation_terms = ["nonprofit institution", "accredited institution", "academic"]
            if any(term in lower for term in foundation_terms):
                for key, partner in self.partnerships.items():
                    if "foundation_grants" in partner["enables"]:
                        pathway["partnership_path"] = "Foundation_Affiliate"
                        pathway["recommended_partner"] = partner["name"]
                        break

        # Override eligibility if partnership path exists
        if pathway["sttr_eligible"] or pathway["consortium_eligible"] or pathway["partnership_path"]:
            result["eligible"] = True
            result["reasons"].append(
                f"Eligible via {pathway['partnership_path']} with {pathway['recommended_partner']}"
            )

        result["eligibility_pathway"] = pathway
        return result

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

    def _check_partnership_pathways(self, text: str, grant_type: str) -> dict | None:
        """Check if partnership pathways enable eligibility.

        Returns:
            Partnership info dict if a pathway exists, None otherwise.
        """
        lower = text.lower()

        # STTR pathway: grant mentions university/research institution requirement
        sttr_indicators = [
            "research institution", "university partner",
            "sttr", "small business technology transfer",
            "nonprofit research", "academic partner",
        ]
        if any(ind in lower for ind in sttr_indicators):
            for key, partner in self.partnerships.items():
                if partner["type"] in ("university", "national_lab") and "STTR" in partner["enables"]:
                    return {
                        "pathway": "STTR",
                        "partner_key": key,
                        "partner_name": partner["name"],
                        "partner_type": partner["type"],
                        "note": f"STTR pathway via {partner['name']}",
                    }

        # EU consortium: grant requires EU partner
        eu_indicators = ["eu partner", "european consortium", "horizon europe"]
        if grant_type in ("international", "eu") or any(ind in lower for ind in eu_indicators):
            for key, partner in self.partnerships.items():
                if "EU_connections" in partner["enables"]:
                    return {
                        "pathway": "EU_Consortium",
                        "partner_key": key,
                        "partner_name": partner["name"],
                        "partner_type": partner["type"],
                        "note": f"EU consortium via {partner['name']} network",
                    }

        # Foundation affiliate: grant requires nonprofit affiliation
        foundation_indicators = [
            "nonprofit institution", "accredited institution",
            "academic affiliation", "research affiliate",
        ]
        if any(ind in lower for ind in foundation_indicators):
            for key, partner in self.partnerships.items():
                if "foundation_grants" in partner["enables"]:
                    return {
                        "pathway": "Foundation_Affiliate",
                        "partner_key": key,
                        "partner_name": partner["name"],
                        "partner_type": partner["type"],
                        "note": f"Foundation grant via {partner['name']} affiliation",
                    }

        # State grant pathway
        state_indicators = ["colorado", "state of colorado"]
        if any(ind in lower for ind in state_indicators):
            for key, partner in self.partnerships.items():
                if partner.get("location") == "Colorado" and "state_grants" in partner["enables"]:
                    return {
                        "pathway": "State_Partner",
                        "partner_key": key,
                        "partner_name": partner["name"],
                        "partner_type": partner["type"],
                        "note": f"Colorado state grant via {partner['name']}",
                    }

        return None

    def _apply_partnership_override(self, rule_result: dict, partnership: dict) -> dict:
        """Apply partnership pathway to potentially override blockers."""
        if not rule_result["eligible"] and partnership:
            # Partnership can override nonprofit-only blockers
            new_blockers = []
            for blocker in rule_result["blockers"]:
                if "non-profit" in blocker.lower() or "nonprofit" in blocker.lower():
                    rule_result["reasons"].append(
                        f"Nonprofit requirement addressed via {partnership['pathway']} "
                        f"with {partnership['partner_name']}"
                    )
                else:
                    new_blockers.append(blocker)

            rule_result["blockers"] = new_blockers
            if not new_blockers:
                rule_result["eligible"] = True
                rule_result["confidence"] = max(rule_result["confidence"], 0.6)

        return rule_result

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
