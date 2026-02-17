"""Requirements parser — extracts and structures grant requirements."""

from src.utils.logger import setup_logger
from src.utils.api_clients import GroqClient
from src.utils.text_processor import TextProcessor

logger = setup_logger("requirements_parser")


class RequirementsParser:
    """Parse grant requirements into structured format."""

    def __init__(self, groq_client: GroqClient | None = None):
        self.groq = groq_client or GroqClient()

    def parse(self, grant_title: str, grant_text: str) -> dict:
        """Parse grant text to extract structured requirements.

        Args:
            grant_title: Title of the grant.
            grant_text: Full grant description text.

        Returns:
            Structured dict with parsed requirements.
        """
        # First, try rule-based extraction
        basic = self._rule_based_parse(grant_text)

        # Then enhance with AI
        try:
            ai_result = self._ai_parse(grant_title, grant_text)
            return self._merge(basic, ai_result)
        except Exception as e:
            logger.error("AI requirements parsing failed: %s", e)
            return basic

    def _rule_based_parse(self, text: str) -> dict:
        """Extract basic requirements using pattern matching."""
        result = {
            "amounts": {},
            "deadline": None,
            "eligibility_keywords": [],
            "required_documents": [],
            "evaluation_criteria": [],
        }

        # Extract amounts
        amount_min, amount_max, currency = TextProcessor.extract_amount(text)
        result["amounts"] = {
            "min": amount_min,
            "max": amount_max,
            "currency": currency,
        }

        # Extract deadline
        result["deadline"] = TextProcessor.extract_deadline(text)

        # Extract eligibility keywords
        result["eligibility_keywords"] = TextProcessor.extract_eligibility_keywords(text)

        # Look for common document requirements
        lower = text.lower()
        doc_patterns = {
            "Letter of Intent": ["letter of intent", "loi"],
            "Business Plan": ["business plan"],
            "Budget": ["budget", "financial plan", "cost proposal"],
            "Technical Proposal": ["technical proposal", "technical plan", "technical narrative"],
            "Resume/CV": ["resume", "curriculum vitae", "cv", "biographical sketch"],
            "References": ["references", "letters of support"],
            "Financial Statements": ["financial statement", "audit", "balance sheet"],
            "Pitch Deck": ["pitch deck", "presentation"],
            "Data Management Plan": ["data management plan"],
            "Environmental Impact": ["environmental impact", "environmental assessment"],
        }
        for doc, patterns in doc_patterns.items():
            if any(p in lower for p in patterns):
                result["required_documents"].append(doc)

        return result

    def _ai_parse(self, title: str, text: str) -> dict:
        """AI-enhanced requirements parsing."""
        prompt = f"""Extract ALL requirements from this grant opportunity:

Title: {title}
Text: {text[:3000]}

Return a JSON object:
{{
    "eligibility": {{
        "organization_types": ["list of eligible org types"],
        "geographic_restrictions": ["any location requirements"],
        "size_requirements": "employee/revenue requirements if any",
        "other_requirements": ["any other eligibility criteria"]
    }},
    "application": {{
        "required_documents": ["list of all required documents"],
        "optional_documents": ["any optional supporting documents"],
        "page_limits": "any page/word limits mentioned",
        "format_requirements": "any format requirements"
    }},
    "evaluation": {{
        "criteria": ["list of evaluation criteria"],
        "weights": "any scoring weights mentioned"
    }},
    "timeline": {{
        "deadline": "deadline date if mentioned",
        "review_period": "expected review timeline if mentioned",
        "award_date": "expected award date if mentioned",
        "project_duration": "expected project duration"
    }},
    "funding": {{
        "amount_range": "funding amount range",
        "cost_sharing": "any cost-sharing requirements",
        "indirect_costs": "indirect cost rate limits if any"
    }}
}}

Return ONLY valid JSON."""

        response = self.groq.analyze(prompt, temperature=0.0)
        result = TextProcessor.extract_json_from_text(response)
        return result or {}

    def _merge(self, basic: dict, ai: dict) -> dict:
        """Merge rule-based and AI results."""
        merged = {**basic}

        if ai.get("eligibility"):
            merged["eligibility_details"] = ai["eligibility"]

        if ai.get("application"):
            ai_docs = ai["application"].get("required_documents", [])
            existing = set(merged.get("required_documents", []))
            for doc in ai_docs:
                if doc not in existing:
                    merged.setdefault("required_documents", []).append(doc)
            merged["format_requirements"] = ai["application"].get("format_requirements")
            merged["page_limits"] = ai["application"].get("page_limits")

        if ai.get("evaluation"):
            merged["evaluation_criteria"] = ai["evaluation"].get("criteria", [])
            merged["evaluation_weights"] = ai["evaluation"].get("weights")

        if ai.get("timeline"):
            merged["timeline"] = ai["timeline"]
            if not merged.get("deadline") and ai["timeline"].get("deadline"):
                merged["deadline"] = ai["timeline"]["deadline"]

        if ai.get("funding"):
            merged["funding_details"] = ai["funding"]

        return merged
