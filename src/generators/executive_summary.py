"""Executive summary generator for grant applications."""

from pathlib import Path

import yaml

from src.utils.api_clients import GeminiClient
from src.utils.logger import setup_logger

logger = setup_logger("exec_summary_gen")

CONFIG_DIR = Path(__file__).parent.parent.parent / "config"
TEMPLATE_DIR = Path(__file__).parent.parent.parent / "templates"


class ExecutiveSummaryGenerator:
    """Generate executive summaries tailored to specific grants."""

    def __init__(self, gemini_client: GeminiClient | None = None):
        self.gemini = gemini_client or GeminiClient()
        with open(CONFIG_DIR / "core_element_profile.yaml") as f:
            self.profile = yaml.safe_load(f)

    def generate(self, grant_title: str, grant_requirements: str, grant_focus: str = "") -> str:
        """Generate an executive summary for a grant application.

        Args:
            grant_title: Title of the grant.
            grant_requirements: Grant requirements/description text.
            grant_focus: Specific focus areas of the grant.

        Returns:
            Generated executive summary with customization placeholders.
        """
        profile_text = self._build_profile_text()
        template = self._load_template()

        prompt = f"""You are an expert grant writer. Write a compelling executive summary for:

GRANT: {grant_title}
REQUIREMENTS: {grant_requirements[:3000]}
FOCUS AREAS: {grant_focus}

COMPANY PROFILE:
{profile_text}

TEMPLATE STRUCTURE:
{template}

Write a 500-700 word executive summary that:
1. Opens with the critical challenge (mineral exploration inefficiency)
2. Introduces Core Element AI's probabilistic AI solution
3. Highlights proven results ($17M+ savings, 79% drilling reduction, ±15m accuracy)
4. Directly addresses the grant's specific focus areas and evaluation criteria
5. Closes with potential impact and alignment with grant mission

Use professional grant writing tone. Be specific with numbers.
Mark any sections needing manual review with [CUSTOMIZE: description].
Do NOT use generic filler — every sentence should add value."""

        try:
            result = self.gemini.generate(prompt, temperature=0.4, max_tokens=2048)
            logger.info("Generated executive summary for: %s", grant_title[:60])
            return result
        except Exception as e:
            logger.error("Failed to generate executive summary: %s", e)
            return template

    def _build_profile_text(self) -> str:
        vp = self.profile.get("value_propositions", {})
        team = self.profile.get("team", {})
        company = self.profile.get("company", {})

        metrics = "\n".join(
            f"- {m['metric']}: {m['value']} — {m['description']}"
            for m in vp.get("key_metrics", [])
        )
        diffs = "\n".join(f"- {d}" for d in vp.get("differentiators", []))
        team_info = "\n".join(
            f"- {t['role']}: {t['background']}"
            for t in team.get("highlights", [])
        )

        return f"""Company: {company.get('name')} ({company.get('legal_structure')}, {company.get('incorporation_state')})
Industries: {', '.join(company.get('industries', []))}
Technology: {self.profile.get('technology', {}).get('name', '')}
TRL Level: {self.profile.get('technology', {}).get('trl_level', '')}

KEY METRICS:
{metrics}

DIFFERENTIATORS:
{diffs}

TEAM:
{team_info}

PARTNERSHIPS: {', '.join(p['name'] for p in self.profile.get('partnerships', {}).get('strategic', []))}"""

    def _load_template(self) -> str:
        template_path = TEMPLATE_DIR / "executive_summary.md"
        if template_path.exists():
            return template_path.read_text()
        return "Executive Summary template not found. Generate from scratch."
