"""Analyze grants using LLM cascade: Ollama -> Groq -> Gemini -> rule-based fallback.

Cascade logic:
  1. Try Ollama locally (Llama 3.1 8B) — free, deep analysis
  2. If Ollama unavailable -> try Groq cloud (Llama 3.3 70B) — free tier
  3. If Groq unavailable -> try Gemini Flash (Google) — free tier
  4. If all LLMs down -> rule-based scoring — always works
"""

import json
import os

from src.utils.logger import setup_logger

logger = setup_logger("analyze")

CORE_ELEMENT_PROFILE = {
    "company": "Core Element AI",
    "legal": "S Corporation, Delaware",
    "industry": ["AI", "Mining Technology", "Geological Exploration", "CleanTech"],
    "technology": "Probabilistic AI modeling for geological exploration",
    "focus_minerals": ["Lithium", "Copper", "Cobalt", "Aluminum", "Iron Ore"],
    "value_props": [
        "Reduces exploration time from 7-8 years to weeks",
        "79% reduction in unsuccessful drilling ($1M+ savings per project)",
        "$17M+ total demonstrated savings",
        "±15 meter accuracy in predictions (USA)",
        "Mexico: probability improved from 0.5% to 75%, depth reduced 200m",
        "7 successful projects in a row",
    ],
    "stage": "Series A",
    "funding_ask": "$7.5M",
    "team_size": "4-10",
    "team": "PhD Stanford/MIT, Berkeley Professor, NASA experience, 30+ years mining",
    "markets": ["Kazakhstan", "USA", "Mexico"],
    "partnerships": ["Global ARTbuild 2030", "ERG", "Colorado School of Mines",
                     "Lawrence Berkeley National Lab", "Stanford Mineral-X"],
}


ANALYSIS_PROMPT_TEMPLATE = """You are a grant success analyst. Analyze this grant opportunity for Core Element AI.

COMPANY PROFILE:
{profile}

GRANT OPPORTUNITY:
Title: {title}
Funder: {funder}
Amount: ${amount_min:,} - ${amount_max:,}
Deadline: {deadline}
Requirements: {requirements}
Description: {description}

HISTORICAL PATTERNS FOR THIS FUNDER:
{funder_pattern}

TOP WINNING KEYWORDS:
{top_keywords}

Analyze the match and predict success. Return ONLY valid JSON:
{{
  "pattern_match_score": 0-100,
  "win_probability": 0-100,
  "priority": "copy_now" | "test_first" | "skip",
  "success_factors": {{
    "keywords": ["kw1", "kw2", "kw3"],
    "value_props": ["prop1", "prop2"],
    "partnerships": ["partner1"]
  }},
  "risk_factors": ["risk1", "risk2"],
  "reasoning": "brief explanation"
}}

Rules:
- copy_now: Win probability > 15% AND pattern match > 80%
- test_first: Win probability 8-15% AND pattern match > 60%
- skip: Win probability < 8%"""


def _build_prompt(grant: dict, patterns: dict) -> str:
    """Build the analysis prompt for a grant."""
    funder = grant.get("funder", "")
    funder_pattern = next(
        (p for p in patterns.get("funder_patterns", []) if p["funder"] == funder),
        None,
    )
    return ANALYSIS_PROMPT_TEMPLATE.format(
        profile=json.dumps(CORE_ELEMENT_PROFILE, indent=2),
        title=grant.get("title", ""),
        funder=funder,
        amount_min=grant.get("amount_min", 0),
        amount_max=grant.get("amount_max", 0),
        deadline=grant.get("deadline", "Not specified"),
        requirements=grant.get("requirements", grant.get("eligibility", "Not specified")),
        description=grant.get("description", "")[:1500],
        funder_pattern=json.dumps(funder_pattern, indent=2) if funder_pattern else "No historical data",
        top_keywords=json.dumps(patterns.get("keyword_patterns", [])[:10], indent=2),
    )


def _try_ollama(prompt: str) -> dict | None:
    """Level 1: Ollama locally (Llama 3.1 8B). Returns None if unavailable."""
    try:
        import ollama
        response = ollama.chat(
            model="llama3.1:8b",
            messages=[{"role": "user", "content": prompt}],
            format="json",
            options={"temperature": 0.3},
        )
        result = json.loads(response["message"]["content"])
        logger.debug("Ollama analysis OK")
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
                {"role": "system", "content": "You are a grant success analyst. Return ONLY valid JSON."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
            max_tokens=1024,
            response_format={"type": "json_object"},
        )
        text = response.choices[0].message.content or ""
        result = json.loads(text)
        logger.debug("Groq analysis OK")
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
                "temperature": 0.1,
                "max_output_tokens": 1024,
                "response_mime_type": "application/json",
            },
        )
        text = response.text or ""
        result = json.loads(text)
        logger.debug("Gemini analysis OK")
        return result
    except ImportError:
        logger.debug("google-generativeai not installed")
        return None
    except Exception as e:
        logger.debug("Gemini unavailable: %s", e)
        return None


def analyze_grant_fallback(grant: dict, patterns: dict) -> dict:
    """Level 4: Rule-based fallback — always works, no LLM needed."""
    from src.analyzers.fit_scorer import FitScorer

    scorer = FitScorer()
    fit = scorer.score(
        title=grant.get("title", ""),
        description=grant.get("description", ""),
        funder=grant.get("funder", ""),
        grant_type=grant.get("grant_type", ""),
        eligibility_text=grant.get("eligibility", ""),
        amount_min=grant.get("amount_min"),
        amount_max=grant.get("amount_max"),
    )

    fit_score = fit["overall"]
    win_prob = max(1, min(50, int(fit_score * 0.4)))

    if fit_score >= 80 and win_prob >= 15:
        priority = "copy_now"
    elif fit_score >= 60 and win_prob >= 8:
        priority = "test_first"
    else:
        priority = "skip"

    top_keywords = [p["keyword"] for p in patterns.get("keyword_patterns", [])[:5]]

    return {
        "pattern_match_score": fit_score,
        "win_probability": win_prob,
        "priority": priority,
        "success_factors": {
            "keywords": top_keywords[:3],
            "value_props": ["$17M+ savings", "79% drilling reduction"],
            "partnerships": ["Colorado School of Mines"],
        },
        "risk_factors": ["Rule-based analysis (LLM unavailable)"],
        "reasoning": f"Rule-based fit score: {fit_score}%, estimated win: {win_prob}%",
    }


def analyze_grant(grant: dict, patterns: dict) -> dict:
    """Analyze a grant using cascade: Ollama -> Groq -> Gemini -> rules.

    Always returns an analysis dict.
    """
    prompt = _build_prompt(grant, patterns)

    # Level 1: Local Ollama
    result = _try_ollama(prompt)
    if result and "priority" in result:
        result["llm_source"] = "ollama"
        return result

    # Level 2: Groq cloud (free)
    result = _try_groq(prompt)
    if result and "priority" in result:
        result["llm_source"] = "groq"
        return result

    # Level 3: Gemini Flash (free)
    result = _try_gemini(prompt)
    if result and "priority" in result:
        result["llm_source"] = "gemini"
        return result

    # Level 4: Rule-based fallback
    result = analyze_grant_fallback(grant, patterns)
    result["llm_source"] = "rules"
    return result


def analyze_grants(grants: list[dict], patterns: dict) -> list[dict]:
    """Analyze all filtered grants using the LLM cascade.

    Args:
        grants: Filtered grants to analyze.
        patterns: Success patterns from winners.

    Returns:
        Grants with analysis results added.
    """
    analyzed: list[dict] = []

    for i, grant in enumerate(grants, 1):
        title = grant.get("title", "Unknown")[:60]
        print(f"  [{i}/{len(grants)}] Analyzing: {title}...")

        analysis = analyze_grant(grant, patterns)
        grant["analysis"] = analysis
        analyzed.append(grant)

        priority = analysis.get("priority", "skip")
        win_prob = analysis.get("win_probability", 0)
        source = analysis.get("llm_source", "?")

        emoji = {"copy_now": ">>", "test_first": "**", "skip": "--"}.get(priority, "??")
        print(f"    {emoji} {priority.upper()} [{source}] - Win: {win_prob}%")

    return analyzed


if __name__ == "__main__":
    sample_grant = {
        "title": "SBIR Phase I - AI for Critical Mineral Exploration",
        "funder": "DOE SBIR Phase 1",
        "amount_min": 50000, "amount_max": 250000,
        "description": "AI-driven approaches for critical minerals discovery",
    }
    empty_patterns = {"keyword_patterns": [], "funder_patterns": [], "amount_patterns": []}
    result = analyze_grants([sample_grant], empty_patterns)
    print(json.dumps(result[0]["analysis"], indent=2))
