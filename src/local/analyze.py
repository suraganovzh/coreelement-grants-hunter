"""Analyze grants using Llama 3.1 8B (deep analysis + success prediction).

Runs locally on Surface ARM via Ollama.
Takes ~3s per grant for deep analysis.
"""

import json

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


def analyze_grant_ollama(grant: dict, patterns: dict) -> dict:
    """Deep analysis using Llama 3.1 8B."""
    try:
        import ollama
    except ImportError:
        logger.warning("Ollama not installed, using fallback analysis")
        return analyze_grant_fallback(grant, patterns)

    funder = grant.get("funder", "")
    funder_pattern = next(
        (p for p in patterns.get("funder_patterns", []) if p["funder"] == funder),
        None,
    )

    prompt = f"""You are a grant success analyst. Analyze this grant opportunity for Core Element AI.

COMPANY PROFILE:
{json.dumps(CORE_ELEMENT_PROFILE, indent=2)}

GRANT OPPORTUNITY:
Title: {grant.get('title', '')}
Funder: {funder}
Amount: ${grant.get('amount_min', 0):,} - ${grant.get('amount_max', 0):,}
Deadline: {grant.get('deadline', 'Not specified')}
Requirements: {grant.get('requirements', grant.get('eligibility', 'Not specified'))}
Description: {grant.get('description', '')[:1500]}

HISTORICAL PATTERNS FOR THIS FUNDER:
{json.dumps(funder_pattern, indent=2) if funder_pattern else 'No historical data'}

TOP WINNING KEYWORDS:
{json.dumps(patterns.get('keyword_patterns', [])[:10], indent=2)}

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

    try:
        response = ollama.chat(
            model="llama3.1:8b",
            messages=[{"role": "user", "content": prompt}],
            format="json",
            options={"temperature": 0.3},
        )
        analysis = json.loads(response["message"]["content"])
        return analysis
    except Exception as e:
        logger.warning("Ollama analysis failed: %s — using fallback", e)
        return analyze_grant_fallback(grant, patterns)


def analyze_grant_fallback(grant: dict, patterns: dict) -> dict:
    """Rule-based fallback analysis when Ollama is unavailable."""
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

    # Win probability estimate from fit score
    # Base rate ~5%, adjust up for high fit
    win_prob = max(1, min(50, int(fit_score * 0.4)))

    if fit_score >= 80 and win_prob >= 15:
        priority = "copy_now"
    elif fit_score >= 60 and win_prob >= 8:
        priority = "test_first"
    else:
        priority = "skip"

    # Extract relevant keywords from patterns
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
        "risk_factors": ["Fallback analysis — Ollama unavailable"],
        "reasoning": f"Rule-based fit score: {fit_score}%, estimated win: {win_prob}%",
    }


def analyze_grants(grants: list[dict], patterns: dict) -> list[dict]:
    """Analyze all filtered grants.

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

        analysis = analyze_grant_ollama(grant, patterns)
        grant["analysis"] = analysis
        analyzed.append(grant)

        priority = analysis.get("priority", "skip")
        win_prob = analysis.get("win_probability", 0)

        emoji = {"copy_now": "🎯", "test_first": "⚡", "skip": "➖"}.get(priority, "❓")
        print(f"    {emoji} {priority.upper()} - Win: {win_prob}%")

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
