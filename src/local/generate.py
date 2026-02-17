"""Generate grant application drafts using LLM cascade (Gemma 2 9B preferred).

Usage:
    python -m src.local.generate --grant-id <id>
    python -m src.local.generate --grant-id <id> --sections summary,approach
    python -m src.local.generate --list          # Show available grants
"""

import argparse
import json
import os
import platform
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from src.local.llm_cascade import get_cascade
from src.utils.logger import setup_logger

logger = setup_logger("generate")

SECTIONS = {
    "summary": {
        "title": "Executive Summary",
        "max_words": 250,
        "prompt": """Write an Executive Summary (max 250 words) for a grant application.

COMPANY: Core Element AI — Probabilistic AI modeling for geological mineral exploration.
KEY METRICS: 79% reduction in unsuccessful drilling, $17M+ savings, 7-8 years to weeks, ±15m accuracy.
TEAM: PhD Stanford/MIT, Berkeley Professor, 30+ years mining, NASA experience.
PARTNERS: ERG, Colorado School of Mines, Stanford Mineral-X, Lawrence Berkeley Lab.
MINERALS: Li, Cu, Co, Al, Fe — critical for green energy transition.

GRANT:
Title: {title}
Funder: {funder}
Amount: ${amount_min:,} - ${amount_max:,}
Requirements: {requirements}

WINNING PATTERNS (from successful applications):
Keywords: {top_keywords}
Value props: {value_props}

Write a compelling Executive Summary that:
1. States the problem (7-8 year exploration timelines, high failure rates)
2. Presents Core Element AI's solution (probabilistic AI modeling)
3. Highlights proven results ($17M+ savings, 79% reduction)
4. Shows alignment with THIS grant's goals
5. Uses winning keywords naturally

Return ONLY the executive summary text, no JSON.""",
    },
    "approach": {
        "title": "Technical Approach",
        "max_words": 400,
        "prompt": """Write a Technical Approach section (max 400 words) for a grant application.

COMPANY: Core Element AI
TECHNOLOGY: Probabilistic AI modeling for subsurface mineral deposit prediction at 1:10,000 scale.
CAPABILITIES:
- Multi-source geological data integration (geophysical, geochemical, remote sensing)
- Probabilistic uncertainty quantification
- Real-time model updating with new drill data
- Drilling target optimization

GRANT:
Title: {title}
Funder: {funder}
Requirements: {requirements}

WINNING PATTERNS:
Keywords: {top_keywords}

Write a Technical Approach that covers:
1. Problem Statement (current exploration inefficiency)
2. Proposed Solution (probabilistic AI framework)
3. Methodology (data acquisition → model training → validation → field testing)
4. Innovation (what makes this novel)
5. Expected Milestones (3-4 milestones with deliverables)

Return ONLY the technical approach text, no JSON.""",
    },
    "impact": {
        "title": "Impact Statement",
        "max_words": 300,
        "prompt": """Write an Impact Statement (max 300 words) for a grant application.

COMPANY: Core Element AI
PROVEN IMPACT:
- Economic: $1M+ savings per project, $17M+ total, 79% less wasted drilling
- Environmental: Fewer drill holes = less land disturbance, supports green energy minerals
- Scientific: Advances probabilistic AI for geological sciences
- Societal: Secures domestic critical mineral supply chains

GRANT:
Title: {title}
Funder: {funder}
Requirements: {requirements}

WINNING PATTERNS:
Keywords: {top_keywords}
Value props: {value_props}

Write an Impact Statement covering:
1. Economic Impact (quantified savings, efficiency gains)
2. Environmental Impact (reduced footprint, clean energy minerals)
3. Scientific/Technological Impact (AI advances)
4. Societal Impact (supply chain security, jobs)
5. Scalability (global deployment potential)

Return ONLY the impact statement text, no JSON.""",
    },
}


def load_grant(grant_id: str) -> dict | None:
    """Load a specific grant from analyzed.json by ID."""
    analyzed_file = Path("data/analyzed.json")
    if not analyzed_file.exists():
        print("ERROR: data/analyzed.json not found. Run daily_workflow first.")
        return None

    with open(analyzed_file) as f:
        data = json.load(f)

    grants = data if isinstance(data, list) else data.get("grants", [])

    for grant in grants:
        if grant.get("id") == grant_id:
            return grant

    print(f"ERROR: Grant '{grant_id}' not found in analyzed.json")
    print(f"Available IDs: {[g.get('id', '?') for g in grants[:10]]}")
    return None


def load_patterns() -> dict:
    """Load success patterns."""
    patterns_file = Path("data/patterns.json")
    if patterns_file.exists():
        with open(patterns_file) as f:
            return json.load(f)
    return {"keyword_patterns": [], "funder_patterns": []}


def list_grants():
    """Show all analyzed grants available for draft generation."""
    analyzed_file = Path("data/analyzed.json")
    if not analyzed_file.exists():
        print("No analyzed grants found. Run daily_workflow first.")
        return

    with open(analyzed_file) as f:
        data = json.load(f)

    grants = data if isinstance(data, list) else data.get("grants", [])

    if not grants:
        print("No grants in analyzed.json")
        return

    print(f"\nAvailable grants ({len(grants)} total):\n")
    print(f"{'ID':<15} {'Priority':<12} {'Win%':<6} {'Title':<50}")
    print("-" * 83)

    for g in sorted(grants, key=lambda x: x.get("analysis", {}).get("win_probability", 0), reverse=True):
        analysis = g.get("analysis", {})
        priority = analysis.get("priority", "skip")
        win_prob = analysis.get("win_probability", 0)
        emoji = {"copy_now": ">>", "test_first": "**", "skip": "--"}.get(priority, "??")
        title = g.get("title", "Unknown")[:50]
        print(f"{g.get('id', '?'):<15} {emoji} {priority:<9} {win_prob:>3}%   {title}")


def generate_section(grant: dict, patterns: dict, section_key: str) -> str:
    """Generate one section of the application draft."""
    section = SECTIONS[section_key]

    top_keywords = [p["keyword"] for p in patterns.get("keyword_patterns", [])[:10]]
    funder = grant.get("funder", "")
    funder_pattern = next(
        (p for p in patterns.get("funder_patterns", []) if p.get("funder") == funder),
        None,
    )
    value_props = []
    if funder_pattern:
        value_props = funder_pattern.get("top_keywords", [])[:5]

    prompt = section["prompt"].format(
        title=grant.get("title", ""),
        funder=funder,
        amount_min=grant.get("amount_min", 0),
        amount_max=grant.get("amount_max", 0),
        requirements=grant.get("requirements", grant.get("eligibility", "Not specified")),
        top_keywords=", ".join(top_keywords) if top_keywords else "critical minerals, AI, exploration",
        value_props=", ".join(value_props) if value_props else "$17M+ savings, 79% drilling reduction",
    )

    cascade = get_cascade()
    try:
        result, source = cascade.chat(
            prompt=prompt,
            task_type="generate",
            system_prompt="You are an expert grant writer. Write clear, compelling, technically accurate text.",
            temperature=0.4,
            max_tokens=2048,
            json_mode=False,
        )
        logger.info("Generated %s via %s", section_key, source)
        return str(result)
    except RuntimeError:
        logger.warning("All LLMs failed for %s — returning template placeholder", section_key)
        return f"[TODO: Write {section['title']} — all LLMs were unavailable]\n"


def generate_keywords_checklist(grant: dict, patterns: dict) -> str:
    """Generate a checklist of keywords to include."""
    analysis = grant.get("analysis", {})
    success_factors = analysis.get("success_factors", {})

    keywords = success_factors.get("keywords", [])
    top_patterns = [p["keyword"] for p in patterns.get("keyword_patterns", [])[:15]]

    all_keywords = list(dict.fromkeys(keywords + top_patterns))

    lines = ["## Keywords Checklist\n"]
    lines.append("Ensure these keywords appear naturally in your final application:\n")
    for kw in all_keywords[:20]:
        lines.append(f"- [ ] {kw}")
    return "\n".join(lines)


def generate_draft(grant: dict, patterns: dict, section_keys: list[str] | None = None) -> str:
    """Generate a full draft for one grant."""
    if section_keys is None:
        section_keys = list(SECTIONS.keys())

    analysis = grant.get("analysis", {})
    funder = grant.get("funder", "")
    amount_min = grant.get("amount_min", 0)
    amount_max = grant.get("amount_max", 0)

    lines = [
        f"# Grant Application Draft",
        f"",
        f"**Grant:** {grant.get('title', '')}",
        f"**Funder:** {funder}",
        f"**Amount:** ${amount_min:,} - ${amount_max:,}",
        f"**Deadline:** {grant.get('deadline', 'TBD')}",
        f"**Win Probability:** {analysis.get('win_probability', 0)}%",
        f"**Pattern Match:** {analysis.get('pattern_match_score', 0)}%",
        f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"**LLM Source:** cascade (Ollama > Groq > Gemini)",
        f"",
        f"---",
        f"",
    ]

    for key in section_keys:
        if key not in SECTIONS:
            print(f"  WARNING: Unknown section '{key}', skipping")
            continue

        section = SECTIONS[key]
        print(f"  Generating: {section['title']}...")
        text = generate_section(grant, patterns, key)

        lines.append(f"## {section['title']}")
        lines.append(f"")
        lines.append(text.strip())
        lines.append(f"")
        lines.append(f"---")
        lines.append(f"")

    lines.append(generate_keywords_checklist(grant, patterns))
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("*This is an AI-generated draft. Review, edit, and customize before submission.*")
    lines.append(f"*Generated by Grant Hunter AI for Core Element AI*")

    return "\n".join(lines)


def save_draft(grant: dict, content: str) -> Path:
    """Save draft to drafts/ directory."""
    Path("drafts").mkdir(exist_ok=True)

    grant_id = grant.get("id", "unknown")
    funder = grant.get("funder", "unknown").replace(" ", "_").replace("/", "_")[:30]
    filename = f"grant_{grant_id}_{funder}.md"
    filepath = Path("drafts") / filename

    with open(filepath, "w") as f:
        f.write(content)

    return filepath


def open_in_editor(filepath: Path):
    """Try to open the draft in the default editor."""
    system = platform.system()
    try:
        if system == "Windows":
            os.startfile(str(filepath))
        elif system == "Darwin":
            subprocess.run(["open", str(filepath)], check=False)
        else:
            subprocess.run(["xdg-open", str(filepath)], check=False)
    except Exception as e:
        logger.debug("Could not open editor: %s", e)


def main():
    parser = argparse.ArgumentParser(description="Generate grant application drafts")
    parser.add_argument("--grant-id", type=str, help="Grant ID from analyzed.json")
    parser.add_argument("--sections", type=str, default=None,
                        help="Comma-separated sections: summary,approach,impact")
    parser.add_argument("--list", action="store_true", help="List available grants")
    parser.add_argument("--no-open", action="store_true", help="Don't open file in editor")
    args = parser.parse_args()

    if args.list:
        list_grants()
        return

    if not args.grant_id:
        print("ERROR: --grant-id required. Use --list to see available grants.")
        parser.print_help()
        sys.exit(1)

    # Load .env
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    print(f"Grant Draft Generator")
    print(f"=" * 60)

    # Load grant
    grant = load_grant(args.grant_id)
    if not grant:
        sys.exit(1)

    print(f"Grant: {grant.get('title', '')}")
    print(f"Funder: {grant.get('funder', '')}")
    print(f"Amount: ${grant.get('amount_min', 0):,} - ${grant.get('amount_max', 0):,}")
    print()

    # Load patterns
    patterns = load_patterns()

    # Parse sections
    section_keys = None
    if args.sections:
        section_keys = [s.strip() for s in args.sections.split(",")]

    # Generate
    print("Generating draft (this may take 30-90 seconds)...")
    print("-" * 60)
    draft = generate_draft(grant, patterns, section_keys)

    # Save
    filepath = save_draft(grant, draft)
    print(f"\nDraft saved: {filepath}")

    # Open in editor
    if not args.no_open:
        open_in_editor(filepath)
        print("Opened in editor")

    print(f"\nDone! Edit the draft at: {filepath}")


if __name__ == "__main__":
    main()
