"""Impact statement generator for grant applications."""

from pathlib import Path

import yaml

from src.utils.api_clients import GeminiClient
from src.utils.logger import setup_logger

logger = setup_logger("impact_gen")

CONFIG_DIR = Path(__file__).parent.parent.parent / "config"


class ImpactStatementGenerator:
    """Generate impact statements tailored to specific grants."""

    def __init__(self, gemini_client: GeminiClient | None = None):
        self.gemini = gemini_client or GeminiClient()
        with open(CONFIG_DIR / "core_element_profile.yaml") as f:
            self.profile = yaml.safe_load(f)

    def generate(self, grant_title: str, grant_requirements: str, impact_focus: str = "") -> str:
        """Generate an impact statement.

        Args:
            grant_title: Title of the grant.
            grant_requirements: Grant requirements text.
            impact_focus: Specific impact areas to address.

        Returns:
            Generated impact statement.
        """
        vp = self.profile.get("value_propositions", {})
        metrics = "\n".join(
            f"- {m['metric']}: {m['value']}" for m in vp.get("key_metrics", [])
        )
        markets = ", ".join(
            m["country"] for m in self.profile.get("markets", {}).get("primary", [])
        )

        prompt = f"""Write a compelling Impact Statement for a grant application.

GRANT: {grant_title}
REQUIREMENTS: {grant_requirements[:2000]}
IMPACT FOCUS: {impact_focus}

PROVEN METRICS:
{metrics}

MARKETS: {markets}
PARTNERSHIPS: {', '.join(p['name'] for p in self.profile.get('partnerships', {}).get('strategic', []))}

Write a 400-600 word impact statement covering:

1. ECONOMIC IMPACT
   - $1M+ savings per exploration project
   - 79% reduction in unsuccessful drilling
   - Reduced exploration timelines from years to weeks
   - Job creation in clean energy supply chain

2. ENVIRONMENTAL IMPACT
   - Fewer unnecessary drill holes = less land disturbance
   - Targeted exploration reduces environmental footprint
   - Supports green energy transition through critical mineral discovery
   - ESG-aligned responsible exploration

3. SCIENTIFIC/TECHNOLOGICAL IMPACT
   - Advances in probabilistic AI for geological sciences
   - Novel data integration methodology
   - Open-science potential (if applicable)

4. SOCIETAL IMPACT
   - Securing critical mineral supply for clean energy transition
   - Reducing dependence on foreign mineral sources
   - Supporting domestic mining industry modernization

5. SCALABILITY
   - Technology applicable globally across mineral types
   - Platform approach enables rapid deployment
   - [CUSTOMIZE: specific scalability for this grant]

Use specific numbers. Connect impact to the grant's mission.
Mark customization points with [CUSTOMIZE: description]."""

        try:
            result = self.gemini.generate(prompt, temperature=0.4, max_tokens=2048)
            logger.info("Generated impact statement for: %s", grant_title[:60])
            return result
        except Exception as e:
            logger.error("Failed to generate impact statement: %s", e)
            return "Impact statement generation failed. Please create manually."
