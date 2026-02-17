"""Filter grants using Llama 3.2 3B (fast eligibility check).

Runs locally on Surface ARM via Ollama.
Quick pass/fail check — takes ~0.5s per grant.
"""

import json
import sys

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


def check_eligibility_ollama(grant: dict) -> dict:
    """Quick eligibility check using Llama 3.2 3B via Ollama."""
    try:
        import ollama
    except ImportError:
        logger.warning("Ollama not installed, using fallback keyword filter")
        return check_eligibility_fallback(grant)

    title = grant.get("title", "")
    funder = grant.get("funder", "")
    eligibility = grant.get("eligibility", "Not specified")
    amount_min = grant.get("amount_min", 0)
    amount_max = grant.get("amount_max", 0)

    prompt = f"""You are a grant eligibility checker.

Company Profile:
{CORE_ELEMENT_PROFILE}

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

    try:
        response = ollama.chat(
            model="llama3.2:3b",
            messages=[{"role": "user", "content": prompt}],
            format="json",
        )
        result = json.loads(response["message"]["content"])
        return result
    except Exception as e:
        logger.warning("Ollama filter failed: %s — using fallback", e)
        return check_eligibility_fallback(grant)


def check_eligibility_fallback(grant: dict) -> dict:
    """Rule-based fallback when Ollama is unavailable."""
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


def filter_grants(grants: list[dict]) -> list[dict]:
    """Filter grants for eligibility.

    Args:
        grants: List of raw grant dicts.

    Returns:
        List of grants that passed the eligibility check.
    """
    filtered: list[dict] = []

    for i, grant in enumerate(grants, 1):
        title = grant.get("title", "Unknown")[:60]
        print(f"  [{i}/{len(grants)}] Checking: {title}...")

        eligibility = check_eligibility_ollama(grant)
        grant["eligibility_check"] = eligibility

        if eligibility.get("eligible") and eligibility.get("confidence", 0) > 50:
            filtered.append(grant)
            print(f"    PASS - {eligibility.get('reason', '')}")
        else:
            print(f"    SKIP - {eligibility.get('reason', '')}")

    return filtered


if __name__ == "__main__":
    # Test with sample data
    sample = [
        {"title": "SBIR Phase I - Critical Minerals AI", "funder": "DOE",
         "eligibility": "Small business, for-profit", "amount_min": 50000, "amount_max": 250000},
        {"title": "Community Garden Program", "funder": "Local Foundation",
         "eligibility": "Non-profit only", "amount_min": 5000, "amount_max": 10000},
    ]
    results = filter_grants(sample)
    print(f"\n{len(results)}/{len(sample)} grants passed filter")
