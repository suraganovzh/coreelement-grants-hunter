"""Budget justification generator for grant applications."""

from pathlib import Path

import yaml

from src.utils.api_clients import GeminiClient
from src.utils.logger import setup_logger

logger = setup_logger("budget_gen")

CONFIG_DIR = Path(__file__).parent.parent.parent / "config"


class BudgetJustificationGenerator:
    """Generate budget justification sections for grant applications."""

    def __init__(self, gemini_client: GeminiClient | None = None):
        self.gemini = gemini_client or GeminiClient()
        with open(CONFIG_DIR / "core_element_profile.yaml") as f:
            self.profile = yaml.safe_load(f)

    def generate(self, grant_title: str, amount: int, duration_months: int = 12, requirements: str = "") -> str:
        """Generate budget justification.

        Args:
            grant_title: Title of the grant.
            amount: Total budget amount in USD.
            duration_months: Project duration in months.
            requirements: Grant-specific budget requirements.

        Returns:
            Generated budget justification text.
        """
        use_of_funds = self.profile.get("funding", {}).get("use_of_funds", [])

        prompt = f"""Write a Budget Justification for a grant application.

GRANT: {grant_title}
TOTAL BUDGET: ${amount:,}
DURATION: {duration_months} months
REQUIREMENTS: {requirements[:1500]}

COMPANY USE OF FUNDS PRIORITIES:
{chr(10).join(f'- {u}' for u in use_of_funds)}

Create a detailed budget justification with these categories:
1. PERSONNEL (typically 50-60% of budget)
   - Key personnel (AI/ML engineers, geologists)
   - Roles and estimated FTE
   - [CUSTOMIZE: specific salary rates]

2. EQUIPMENT & COMPUTING (15-20%)
   - GPU cloud compute for AI training
   - Geological data processing infrastructure
   - [CUSTOMIZE: specific equipment needs]

3. DATA ACQUISITION (10-15%)
   - Geological datasets
   - Satellite/remote sensing data
   - Government geological survey data access

4. TRAVEL (5-10%)
   - Field validation visits
   - Conference presentations
   - Partner meetings

5. OTHER DIRECT COSTS (5-10%)
   - Software licenses
   - Patent filing and IP protection
   - Publication costs

6. INDIRECT COSTS
   - [CUSTOMIZE: rate based on grant allowance]

For each line item provide:
- Amount
- Justification (why it's necessary)
- How it supports project objectives

Mark all items needing customization with [CUSTOMIZE: description].
Total must equal ${amount:,} over {duration_months} months."""

        try:
            result = self.gemini.generate(prompt, temperature=0.3, max_tokens=3000)
            logger.info("Generated budget justification for: %s ($%d)", grant_title[:40], amount)
            return result
        except Exception as e:
            logger.error("Failed to generate budget justification: %s", e)
            return f"Budget justification for ${amount:,} over {duration_months} months — generation failed. Please create manually."
