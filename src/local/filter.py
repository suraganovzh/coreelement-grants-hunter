"""Filter grants using LLM cascade: Ollama -> Groq -> Gemini -> rule-based fallback.

Cascade logic:
  1. Try Ollama locally (Llama 3.2 3B) — free, fast, private
  2. If Ollama unavailable -> try Groq cloud (Llama 3.3 70B) — free tier
  3. If Groq unavailable -> try Gemini Flash (Google) — free tier
  4. If all LLMs down -> rule-based keyword fallback — always works
"""

import json
import os
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


def _try_ollama(prompt: str) -> dict | None:
    """Level 1: Ollama locally. Returns None if unavailable."""
    try:
        import ollama
        response = ollama.chat(
            model="llama3.2:3b",
            messages=[{"role": "user", "content": prompt}],
            format="json",
        )
        result = json.loads(response["message"]["content"])
        logger.debug("Ollama filter OK")
        return result
    except ImportError:
        logger.debug("Ollama not installed")
        return None
    except Exception as e:
        logger.debug("Ollama unavailable: %s", e)
        return None


def _try_groq(prompt: str) -> dict | None:
    """Level 2: Groq cloud (free tier). Returns None if unavailable."""
    api_key = os.getenv("GROQ_API_KEY", "")
    if not api_key:
        logger.debug("GROQ_API_KEY not set")
        return None

    try:
        from groq import Groq
        client = Groq(api_key=api_key)
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": "You are a grant eligibility checker. Return ONLY valid JSON."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.0,
            max_tokens=256,
            response_format={"type": "json_object"},
        )
        text = response.choices[0].message.content or ""
        result = json.loads(text)
        logger.debug("Groq filter OK")
        return result
    except ImportError:
        logger.debug("groq package not installed")
        return None
    except Exception as e:
        logger.debug("Groq unavailable: %s", e)
        return None


def _try_gemini(prompt: str) -> dict | None:
    """Level 3: Google Gemini Flash (free tier). Returns None if unavailable."""
    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        logger.debug("GEMINI_API_KEY not set")
        return None

    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-2.0-flash")
        response = model.generate_content(
            prompt,
            generation_config={
                "temperature": 0.0,
                "max_output_tokens": 256,
                "response_mime_type": "application/json",
            },
        )
        text = response.text or ""
        result = json.loads(text)
        logger.debug("Gemini filter OK")
        return result
    except ImportError:
        logger.debug("google-generativeai not installed")
        return None
    except Exception as e:
        logger.debug("Gemini unavailable: %s", e)
        return None


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

    # Level 1: Local Ollama
    result = _try_ollama(prompt)
    if result and "eligible" in result:
        result["llm_source"] = "ollama"
        return result

    # Level 2: Groq cloud (free)
    result = _try_groq(prompt)
    if result and "eligible" in result:
        result["llm_source"] = "groq"
        return result

    # Level 3: Gemini Flash (free)
    result = _try_gemini(prompt)
    if result and "eligible" in result:
        result["llm_source"] = "gemini"
        return result

    # Level 4: Rule-based fallback
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
