"""API client wrappers for Groq and Gemini."""

import os
from typing import Any

from tenacity import retry, stop_after_attempt, wait_exponential

from src.utils.logger import setup_logger
from src.utils.rate_limiter import RateLimiter

logger = setup_logger("api_clients")


class GroqClient:
    """Client for Groq LPU API — fast inference for analysis tasks."""

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.getenv("GROQ_API_KEY", "")
        self._client = None
        self._limiter = RateLimiter(calls=30, period=60)

    @property
    def client(self):
        if self._client is None:
            from groq import Groq
            self._client = Groq(api_key=self.api_key)
        return self._client

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=4, max=30))
    def analyze(
        self,
        prompt: str,
        system_prompt: str = "You are a grant analysis expert. Be concise and precise.",
        model: str = "llama-3.3-70b-versatile",
        temperature: float = 0.1,
        max_tokens: int = 2048,
    ) -> str:
        """Send an analysis request to Groq.

        Args:
            prompt: The user prompt.
            system_prompt: System context.
            model: Model identifier.
            temperature: Sampling temperature.
            max_tokens: Max response tokens.

        Returns:
            Model response text.
        """
        self._limiter.acquire()
        logger.debug("Groq request: model=%s, tokens=%d", model, max_tokens)

        response = self.client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )

        text = response.choices[0].message.content or ""
        logger.debug("Groq response: %d chars", len(text))
        return text

    def check_eligibility(self, grant_text: str, profile_summary: str) -> dict[str, Any]:
        """Quick eligibility check using Groq."""
        prompt = f"""Analyze this grant for eligibility match with the company profile.

GRANT:
{grant_text[:3000]}

COMPANY PROFILE:
{profile_summary}

Return a JSON object with:
- "eligible": true/false
- "fit_score": 0-100
- "reasons": ["reason1", "reason2"]
- "blockers": ["blocker1"] or []
- "key_requirements": ["req1", "req2"]
- "complexity_score": 1-10

Return ONLY valid JSON, no other text."""

        result = self.analyze(prompt, temperature=0.0)
        import json
        try:
            return json.loads(result)
        except json.JSONDecodeError:
            logger.error("Failed to parse Groq eligibility response: %s", result[:200])
            return {"eligible": False, "fit_score": 0, "reasons": [], "blockers": ["Parse error"]}

    def classify_grant(self, title: str, description: str) -> dict[str, Any]:
        """Classify a grant by category and relevance."""
        prompt = f"""Classify this grant opportunity:

Title: {title}
Description: {description[:2000]}

Return JSON:
- "categories": ["mining", "AI", "cleantech", etc.]
- "relevance": "high"/"medium"/"low"
- "grant_type": "federal"/"private"/"international"/etc.
- "summary": "one-line summary"

Return ONLY valid JSON."""

        result = self.analyze(prompt, temperature=0.0)
        import json
        try:
            return json.loads(result)
        except json.JSONDecodeError:
            return {"categories": [], "relevance": "low", "grant_type": "unknown", "summary": title}


class GeminiClient:
    """Client for Google Gemini Pro API — long-form generation tasks."""

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY", "")
        self._model = None
        self._limiter = RateLimiter(calls=15, period=60)

    @property
    def model(self):
        if self._model is None:
            import google.generativeai as genai
            genai.configure(api_key=self.api_key)
            self._model = genai.GenerativeModel("gemini-2.0-flash")
        return self._model

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=4, max=30))
    def generate(
        self,
        prompt: str,
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> str:
        """Generate text with Gemini.

        Args:
            prompt: The prompt text.
            temperature: Sampling temperature.
            max_tokens: Max response tokens.

        Returns:
            Generated text.
        """
        self._limiter.acquire()
        logger.debug("Gemini request: tokens=%d", max_tokens)

        response = self.model.generate_content(
            prompt,
            generation_config={
                "temperature": temperature,
                "max_output_tokens": max_tokens,
            },
        )

        text = response.text or ""
        logger.debug("Gemini response: %d chars", len(text))
        return text

    def generate_executive_summary(
        self, grant_requirements: str, company_profile: str
    ) -> str:
        """Generate an executive summary tailored to a specific grant."""
        prompt = f"""Write a compelling executive summary for a grant application.

GRANT REQUIREMENTS:
{grant_requirements[:3000]}

COMPANY PROFILE:
{company_profile}

Write a 500-word executive summary that:
1. Opens with the problem (mineral exploration is costly and slow)
2. Presents Core Element AI's solution (probabilistic AI modeling)
3. Highlights key metrics ($17M+ savings, 79% drilling reduction, ±15m accuracy)
4. Aligns with the grant's specific focus areas
5. Closes with impact potential

Use professional grant writing tone. Include specific numbers and achievements.
Mark sections that need manual customization with [CUSTOMIZE: description]."""

        return self.generate(prompt, temperature=0.4, max_tokens=2048)

    def generate_technical_approach(
        self, grant_requirements: str, company_profile: str
    ) -> str:
        """Generate a technical approach section."""
        prompt = f"""Write a Technical Approach section for a grant application.

GRANT REQUIREMENTS:
{grant_requirements[:3000]}

COMPANY PROFILE:
{company_profile}

Write a detailed technical approach (800-1000 words) that covers:
1. Technical Problem Statement
2. Proposed Solution (Probabilistic AI Modeling)
3. Methodology (data collection, model training, validation)
4. Innovation (what makes this approach novel)
5. Expected Outcomes and Milestones
6. Risk Mitigation

Use technical but accessible language. Reference specific capabilities.
Mark sections needing customization with [CUSTOMIZE: description]."""

        return self.generate(prompt, temperature=0.3, max_tokens=4096)

    def deep_analysis(self, grant_text: str, company_profile: str) -> str:
        """Deep analysis of grant requirements and fit."""
        prompt = f"""Perform a detailed analysis of this grant opportunity for Core Element AI.

GRANT DETAILS:
{grant_text[:4000]}

COMPANY PROFILE:
{company_profile}

Provide:
1. ELIGIBILITY ANALYSIS
   - Required vs. our status for each criterion
   - Any disqualifying factors

2. FIT ASSESSMENT (score each 0-100)
   - Technology alignment
   - Industry match
   - Stage match
   - Geographic match
   - Overall fit

3. APPLICATION STRATEGY
   - Key themes to emphasize
   - Metrics to highlight
   - Partnerships to mention
   - Potential weaknesses to address

4. REQUIRED DOCUMENTS (checklist)

5. TIMELINE ESTIMATE
   - Hours to prepare
   - Recommended start date
   - Key milestones

6. RISK FACTORS
   - Competition level
   - Probability of success (%)"""

        return self.generate(prompt, temperature=0.2, max_tokens=4096)
