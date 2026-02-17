"""Generate grant application drafts using Gemma 2 9B.

Runs locally on Surface ARM via Ollama.
Generates: executive summary, technical approach, impact statement.
"""

import argparse
import json
from datetime import datetime
from pathlib import Path

from src.utils.logger import setup_logger

logger = setup_logger("generate")


def _generate_with_ollama(prompt: str, model: str = "gemma2:9b", temperature: float = 0.7) -> str:
    """Generate text with Ollama, falling back to template if unavailable."""
    try:
        import ollama
        response = ollama.chat(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            options={"temperature": temperature},
        )
        return response["message"]["content"]
    except ImportError:
        logger.warning("Ollama not installed — returning template placeholder")
        return "[OLLAMA UNAVAILABLE — Fill in manually using the template structure above]"
    except Exception as e:
        logger.error("Ollama generation failed: %s", e)
        return f"[GENERATION FAILED: {e}. Fill in manually.]"


def generate_executive_summary(grant: dict, patterns: dict) -> str:
    """Generate executive summary using Gemma 2 9B."""
    success_factors = grant.get("analysis", {}).get("success_factors", {})
    keywords = ", ".join(success_factors.get("keywords", ["critical minerals", "AI", "exploration"]))

    prompt = f"""You are an expert grant writer. Generate a compelling executive summary.

GRANT:
Title: {grant.get('title', '')}
Funder: {grant.get('funder', '')}
Amount: ${grant.get('amount_max', 0):,}

COMPANY — Core Element AI:
- AI-powered geological exploration technology
- Reduces mineral exploration time from 7-8 years to weeks
- 79% reduction in unsuccessful drilling
- $17M+ demonstrated savings across 7 projects
- ±15 meter prediction accuracy
- Focus: Critical minerals (Li, Cu, Co, Al, Fe) for green transition
- Team: PhD Stanford/MIT, NASA/Berkeley experience

WINNING KEYWORDS (use naturally): {keywords}

Write a 250-word executive summary:
1. Open with the problem (expensive, slow, subjective mineral exploration)
2. Present the solution (probabilistic AI modeling at 1:10,000 scale)
3. Highlight impact (time/cost savings, critical minerals for clean energy)
4. Use winning keywords naturally
5. End with the ask

Professional, confident tone. Measurable outcomes. No filler."""

    return _generate_with_ollama(prompt)


def generate_technical_approach(grant: dict, patterns: dict) -> str:
    """Generate technical approach section."""
    prompt = f"""You are an expert grant writer. Generate a technical approach section.

GRANT: {grant.get('title', '')}

OUR TECHNOLOGY — Core Element AI:
- Probabilistic AI modeling (NOT single 3D model like competitors)
- Operates at 1:10,000 scale for subsurface prediction
- Integrates: satellite imagery, seismic, magnetic, gravity, geological maps
- Generates multiple equally probable scenarios to quantify risk
- Track record: 7 successful projects, ±15m accuracy (USA), 75% hit rate (Mexico)
- Objective data-driven modeling vs subjective human interpretation

Write a 400-word technical approach:
1. Methodology (data integration → probabilistic modeling → risk quantification)
2. Differentiation from traditional subjective interpretation
3. Validation (7 projects, measurable accuracy)
4. Connection to grant objectives
5. Specific technical details (scale, data types, outputs)

Technical but accessible language."""

    return _generate_with_ollama(prompt)


def generate_impact_statement(grant: dict) -> str:
    """Generate impact statement."""
    prompt = f"""You are an expert grant writer. Generate an impact statement.

GRANT: {grant.get('title', '')}
FOCUS: Critical minerals, AI, mining technology

OUR IMPACT:
- Direct: $1M+ savings per project, 79% reduction in dry wells
- Industry: Addressing $10-12B annual global losses from failed exploration
- National security: Securing critical mineral supply chains (Li, Cu, Co for batteries)
- Environmental: Reducing unnecessary drilling and environmental disturbance
- Market: Kazakhstan ($550M exploration spend), US, Mexico markets

Write a 300-word impact statement:
1. Quantify economic impact (savings, efficiency gains)
2. Address national/strategic importance (critical minerals, supply chains)
3. Environmental benefits (fewer dry wells = less disturbance)
4. Market transformation potential
5. Align with funder's mission

Specific numbers. No generic statements."""

    return _generate_with_ollama(prompt)


def generate_budget_justification(grant: dict) -> str:
    """Generate budget justification."""
    amount = grant.get("amount_max", 250000)

    prompt = f"""Generate a budget justification for a ${amount:,} grant application.

COMPANY: Core Element AI (AI geological exploration)

Allocate the ${amount:,} across standard categories:
1. Personnel (50-60%): AI/ML engineers, geologists
2. Equipment/Computing (15-20%): GPU cloud, data processing
3. Data Acquisition (10-15%): Geological datasets, satellite data
4. Travel (5%): Field validation, conferences
5. Other (5%): Software licenses, patent filing

For each: amount, justification, relevance to project.
Format as a professional budget narrative. Total must equal ${amount:,}."""

    return _generate_with_ollama(prompt)


def generate_drafts(grant: dict, patterns: dict) -> str:
    """Generate all draft sections for a grant application.

    Args:
        grant: Grant dict with analysis results.
        patterns: Success patterns from winners.

    Returns:
        Path to the saved draft file.
    """
    grant_id = grant.get("id", "unknown")
    title = grant.get("title", "Unknown Grant")
    funder = grant.get("funder", "Unknown")

    print(f"  Generating draft for: {title[:60]}...")

    Path("drafts").mkdir(exist_ok=True)

    print("    - Executive Summary...")
    exec_summary = generate_executive_summary(grant, patterns)

    print("    - Technical Approach...")
    tech_approach = generate_technical_approach(grant, patterns)

    print("    - Impact Statement...")
    impact = generate_impact_statement(grant)

    print("    - Budget Justification...")
    budget = generate_budget_justification(grant)

    analysis = grant.get("analysis", {})
    success_factors = analysis.get("success_factors", {})

    draft_content = f"""# {title}

**Funder:** {funder}
**Amount:** ${grant.get('amount_min', 0):,} - ${grant.get('amount_max', 0):,}
**Deadline:** {grant.get('deadline', 'TBD')}
**Win Probability:** {analysis.get('win_probability', 'N/A')}%
**Pattern Match:** {analysis.get('pattern_match_score', 'N/A')}%

---

## Executive Summary

{exec_summary}

---

## Technical Approach

{tech_approach}

---

## Impact Statement

{impact}

---

## Budget Justification

{budget}

---

## Success Factors (from analysis)

**Keywords to emphasize:** {', '.join(success_factors.get('keywords', []))}

**Value props to highlight:**
{chr(10).join('- ' + vp for vp in success_factors.get('value_props', []))}

**Partnerships to mention:**
{chr(10).join('- ' + p for p in success_factors.get('partnerships', []))}

**Risk factors to address:**
{chr(10).join('- ' + r for r in analysis.get('risk_factors', []))}

---

*Generated by Grant Hunter AI on {datetime.now().strftime('%Y-%m-%d %H:%M')}*
*Review and customize before submission*
"""

    safe_funder = funder.replace(" ", "_").replace("/", "-")[:30]
    filename = f"drafts/grant_{grant_id}_{safe_funder}.md"
    with open(filename, "w", encoding="utf-8") as f:
        f.write(draft_content)

    print(f"    Draft saved: {filename}")
    return filename


def main():
    parser = argparse.ArgumentParser(description="Generate grant application draft")
    parser.add_argument("--grant-id", required=True, help="Grant ID to generate draft for")
    parser.add_argument("--data", default="data/analyzed.json", help="Path to analyzed grants")
    parser.add_argument("--patterns", default="data/patterns.json", help="Path to patterns file")
    args = parser.parse_args()

    # Load analyzed grants
    try:
        with open(args.data) as f:
            grants = json.load(f)
            if isinstance(grants, dict):
                grants = grants.get("grants", [])
    except FileNotFoundError:
        print(f"File not found: {args.data}")
        return

    # Find the target grant
    grant = next((g for g in grants if str(g.get("id")) == str(args.grant_id)), None)
    if not grant:
        print(f"Grant {args.grant_id} not found in {args.data}")
        return

    # Load patterns
    try:
        with open(args.patterns) as f:
            patterns = json.load(f)
    except FileNotFoundError:
        patterns = {}

    filename = generate_drafts(grant, patterns)
    print(f"\nDraft generated: {filename}")


if __name__ == "__main__":
    main()
