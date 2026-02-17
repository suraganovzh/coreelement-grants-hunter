"""Technical approach generator for grant applications."""

from pathlib import Path

import yaml

from src.utils.api_clients import GeminiClient
from src.utils.logger import setup_logger

logger = setup_logger("tech_approach_gen")

CONFIG_DIR = Path(__file__).parent.parent.parent / "config"
TEMPLATE_DIR = Path(__file__).parent.parent.parent / "templates"


class TechnicalApproachGenerator:
    """Generate technical approach sections for grant applications."""

    def __init__(self, gemini_client: GeminiClient | None = None):
        self.gemini = gemini_client or GeminiClient()
        with open(CONFIG_DIR / "core_element_profile.yaml") as f:
            self.profile = yaml.safe_load(f)

    def generate(self, grant_title: str, grant_requirements: str, specific_topics: str = "") -> str:
        """Generate a technical approach section.

        Args:
            grant_title: Title of the grant.
            grant_requirements: Grant requirements text.
            specific_topics: Specific technical topics to address.

        Returns:
            Generated technical approach with customization placeholders.
        """
        tech = self.profile.get("technology", {})
        capabilities = "\n".join(f"- {c}" for c in tech.get("capabilities", []))
        minerals = ", ".join(
            m["name"] for m in self.profile.get("focus_minerals", {}).get("primary", [])
        )

        prompt = f"""Write a Technical Approach section for a grant application.

GRANT: {grant_title}
REQUIREMENTS: {grant_requirements[:3000]}
SPECIFIC TOPICS: {specific_topics}

TECHNOLOGY:
- Name: {tech.get('name', 'Probabilistic AI Modeling')}
- Type: {tech.get('type', '')}
- Application: {tech.get('application', '')}
- TRL: {tech.get('trl_level', 7)}
- Capabilities:
{capabilities}
- Target minerals: {minerals}

Write 800-1200 words covering:
1. TECHNICAL PROBLEM STATEMENT
   - Current inefficiency in mineral exploration (7-8 year timelines, high failure rates)
   - Why traditional methods fail (subjective interpretation, limited data integration)

2. PROPOSED SOLUTION
   - Probabilistic AI modeling approach
   - How it integrates multiple geological data sources
   - 1:10,000 scale subsurface prediction capability

3. METHODOLOGY
   - Data acquisition and preprocessing
   - Model architecture (probabilistic framework)
   - Training and validation approach
   - Field validation protocol

4. INNOVATION
   - What makes this approach novel vs. existing methods
   - Objective data-driven vs. subjective interpretation
   - Uncertainty quantification through probabilistic modeling

5. EXPECTED OUTCOMES & MILESTONES
   - [CUSTOMIZE: specific milestones for this grant]
   - Quantifiable metrics (accuracy, time savings, cost reduction)

6. RISK MITIGATION
   - Technical risks and mitigation strategies
   - Data availability and quality assurance

Use technical but accessible language. Reference proven results.
Mark customization points with [CUSTOMIZE: description]."""

        try:
            result = self.gemini.generate(prompt, temperature=0.3, max_tokens=4096)
            logger.info("Generated technical approach for: %s", grant_title[:60])
            return result
        except Exception as e:
            logger.error("Failed to generate technical approach: %s", e)
            return self._load_template()

    def _load_template(self) -> str:
        template_path = TEMPLATE_DIR / "technical_approach.md"
        if template_path.exists():
            return template_path.read_text()
        return "Technical approach template not found."
