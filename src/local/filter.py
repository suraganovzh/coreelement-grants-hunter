"""Filter grants using LLM cascade: Ollama -> Groq -> Gemini -> rule-based fallback.

Uses the centralised LLMCascade from llm_cascade.py.
Cascade:
  1. Ollama locally (Llama 3.2 3B) — free, fast, private
  2. Groq cloud (Llama 3.1 8B instant) — free tier
  3. Gemini Flash (Google) — free tier
  4. Rule-based keyword fallback — always works
"""

import json

from src.local.llm_cascade import get_cascade
from src.utils.logger import setup_logger
from src.utils.text_processor import TextProcessor

logger = setup_logger("filter")

CORE_ELEMENT_PROFILE = """Company: Core Element AI
Legal: S Corporation, Delaware
Industry: AI for Mineral Exploration (Probabilistic AI Modeling)
Focus: Critical minerals (Lithium, Copper, Cobalt, Aluminum, Iron Ore)
Technology: Probabilistic AI modeling for geological exploration, TRL 7
Stage: Series A ($7.5M raise)
Team: 4-10 employees, PhD Stanford/MIT, NASA/Berkeley experience
Revenue: Pre-revenue to early revenue
Markets: Kazakhstan, USA, Mexico
Small Business: Yes"""


ELIGIBILITY_PROMPT_TEMPLATE = """You are a grant eligibility checker.

Company Profile:
{profile}

Grant:
Title: {title}
Funder: {funder}
Requirements: {eligibility}
Amount: ${amount_min:,} - ${amount_max:,}

Task: Determine if Core Element AI is ELIGIBLE for this grant.

Check:
1. Legal structure (S-corp allowed?)
2. Industry/sector (mining/AI/tech allowed?)
3. Stage (early-stage allowed?)
4. Geography (Delaware/US company allowed?)

Answer ONLY with JSON:
{{"eligible": true/false, "reason": "brief reason", "confidence": 0-100}}"""


def _build_prompt(grant: dict) -> str:
    """Build the eligibility check prompt for a grant."""
    return ELIGIBILITY_PROMPT_TEMPLATE.format(
        profile=CORE_ELEMENT_PROFILE,
        title=grant.get("title", ""),
        funder=grant.get("funder", ""),
        eligibility=grant.get("eligibility", "Not specified"),
        amount_min=grant.get("amount_min", 0),
        amount_max=grant.get("amount_max", 0),
    )


def check_eligibility_fallback(grant: dict) -> dict:
    """Level 4: Rule-based fallback — always works, no LLM needed."""
    title = grant.get("title", "").lower()
    description = grant.get("description", "").lower()
    eligibility = grant.get("eligibility", "").lower()
    combined = f"{title} {description} {eligibility}"

    # Hard blockers
    blockers = ["non-profit only", "501(c)(3) only", "government only",
                "university only", "academic institution only", "tribal only"]
    for blocker in blockers:
        if blocker in combined:
            return {"eligible": False, "reason": f"Requires: {blocker}", "confidence": 90}

    # Relevance check via keywords
    relevant_keywords = [
        "ai", "artificial intelligence", "machine learning",
        "mining", "mineral", "geology", "exploration",
        "geospatial", "critical mineral", "lithium", "copper", "cobalt",
        "clean energy", "technology", "innovation", "small business",
    ]
    matches = sum(1 for kw in relevant_keywords if kw in combined)
    score = min(100, matches * 15)

    if matches < 2:
        return {"eligible": False, "reason": "Low relevance to Core Element AI", "confidence": 60}

    return {"eligible": True, "reason": f"Relevant ({matches} keyword matches)", "confidence": score}


def check_eligibility(grant: dict) -> dict:
    """Check eligibility using cascade: Ollama -> Groq -> Gemini -> rules.

    Always returns a result dict with keys: eligible, reason, confidence, llm_source.
    """
    prompt = _build_prompt(grant)
    cascade = get_cascade()

    result, source = cascade.chat_safe(
        prompt=prompt,
        task_type="filter",
        system_prompt="You are a grant eligibility checker. Return ONLY valid JSON.",
        temperature=0.0,
        max_tokens=256,
        json_mode=True,
    )

    if result and isinstance(result, dict) and "eligible" in result:
        result["llm_source"] = source
        return result

    # All LLMs failed — rule-based fallback
    result = check_eligibility_fallback(grant)
    result["llm_source"] = "rules"
    return result


def filter_grants(grants: list[dict]) -> list[dict]:
    """Filter grants for eligibility using the LLM cascade.

    Args:
        grants: List of raw grant dicts.

    Returns:
        List of grants that passed the eligibility check.
    """
    filtered: list[dict] = []

    for i, grant in enumerate(grants, 1):
        title = grant.get("title", "Unknown")[:60]
        print(f"  [{i}/{len(grants)}] Checking: {title}...")

        eligibility = check_eligibility(grant)
        grant["eligibility_check"] = eligibility
        source = eligibility.get("llm_source", "?")

        if eligibility.get("eligible") and eligibility.get("confidence", 0) > 50:
            filtered.append(grant)
            print(f"    PASS [{source}] - {eligibility.get('reason', '')}")
        else:
            print(f"    SKIP [{source}] - {eligibility.get('reason', '')}")

    return filtered


if __name__ == "__main__":
    sample = [
        {"title": "SBIR Phase I - Critical Minerals AI", "funder": "DOE",
         "eligibility": "Small business, for-profit", "amount_min": 50000, "amount_max": 250000},
        {"title": "Community Garden Program", "funder": "Local Foundation",
         "eligibility": "Non-profit only", "amount_min": 5000, "amount_max": 10000},
    ]
    results = filter_grants(sample)
    print(f"\n{len(results)}/{len(sample)} grants passed filter")
