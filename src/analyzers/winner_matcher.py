"""Winner matcher — finds similar awarded grants for a new grant opportunity.

Given a grant and a pool of historical winners, returns the top 5 most
similar awarded grants ranked by a weighted similarity score.

Used in the analysis pipeline to:
- Boost win probability when similar winners exist
- Show users successful precedents for each grant
"""

import re
from collections import Counter

from src.utils.logger import setup_logger

logger = setup_logger("winner_matcher")


def extract_year(date_string: str) -> int:
    """Extract year from various date formats."""
    if not date_string:
        return 0
    match = re.search(r"(20\d{2})", str(date_string))
    return int(match.group(1)) if match else 0


def _extract_words(text: str) -> set[str]:
    """Extract significant words (len > 3) from text."""
    stop = {"the", "and", "for", "with", "that", "this", "from", "will", "have",
            "been", "their", "which", "through", "about", "into", "than", "other",
            "more", "also", "between", "over", "such", "after", "these", "upon"}
    words = set(re.findall(r"[a-z]{4,}", text.lower()))
    return words - stop


def find_similar_winners(
    grant: dict,
    all_winners: list[dict],
    patterns: dict | None = None,
) -> list[dict]:
    """Find 3-5 most similar awarded grants.

    Matching criteria (100-point scale):
      1. Same funder             — up to 40 points
      2. Keyword / text overlap  — up to 30 points
      3. Similar amount range    — up to 10 points
      4. Same technology / tags  — up to 10 points
      5. Recency bonus           — up to 10 points

    Args:
        grant: The new grant opportunity dict.
        all_winners: List of historically awarded grant dicts.
        patterns: Optional patterns dict (unused currently, reserved).

    Returns:
        List of top-5 matches, each containing winner data + score + reasons.
    """
    if not all_winners:
        return []

    grant_funder = (grant.get("funder") or "").lower()
    grant_title = grant.get("title", "")
    grant_desc = grant.get("description", "")
    grant_text = f"{grant_title} {grant_desc}"
    grant_words = _extract_words(grant_text)
    grant_keywords = set(kw.lower() for kw in grant.get("keywords", grant.get("industry_tags", [])))
    grant_amt = grant.get("amount_max") or grant.get("amount_min") or 0

    similar: list[dict] = []

    for winner in all_winners:
        score = 0
        reasons: list[str] = []

        winner_funder = (winner.get("funder") or "").lower()
        winner_title = winner.get("title") or winner.get("award_title") or ""
        winner_abstract = winner.get("abstract") or winner.get("description") or ""
        winner_text = f"{winner_title} {winner_abstract}"
        winner_company = winner.get("winner") or winner.get("recipient") or winner.get("pi") or ""

        # 1. Funder match (40 pts)
        if grant_funder and winner_funder:
            if grant_funder == winner_funder:
                score += 40
                reasons.append("same funder")
            elif grant_funder in winner_funder or winner_funder in grant_funder:
                score += 30
                reasons.append("related funder")

        # 2. Text / keyword overlap (30 pts)
        winner_keywords = set(kw.lower() for kw in winner.get("keywords", []))
        keyword_overlap = len(grant_keywords & winner_keywords) if grant_keywords and winner_keywords else 0

        winner_words = _extract_words(winner_text)
        word_overlap = len(grant_words & winner_words) if grant_words and winner_words else 0

        text_score = 0
        if keyword_overlap > 0:
            text_score += min(20, keyword_overlap * 7)
            reasons.append(f"{keyword_overlap} keyword matches")
        if word_overlap >= 3:
            text_score += min(15, word_overlap * 2)
            if keyword_overlap == 0:
                reasons.append(f"{word_overlap} word overlaps")

        score += min(30, text_score)

        # 3. Amount similarity (10 pts)
        winner_amt = winner.get("amount") or winner.get("award_amount") or 0
        if isinstance(winner_amt, str):
            try:
                winner_amt = int(re.sub(r"[^\d]", "", winner_amt))
            except (ValueError, TypeError):
                winner_amt = 0

        if grant_amt > 0 and winner_amt > 0:
            ratio = min(grant_amt, winner_amt) / max(grant_amt, winner_amt)
            amt_pts = int(ratio * 10)
            score += amt_pts
            if ratio > 0.5:
                reasons.append("similar amount")

        # 4. Technology / tag overlap (10 pts)
        grant_tags = set(t.lower() for t in grant.get("industry_tags", []))
        winner_tags = set(t.lower() for t in winner.get("tags", winner.get("keywords", [])))
        if grant_tags and winner_tags:
            tag_overlap = len(grant_tags & winner_tags)
            tag_pts = min(10, tag_overlap * 4)
            score += tag_pts
            if tag_overlap > 0 and "keyword matches" not in " ".join(reasons):
                reasons.append(f"{tag_overlap} tag matches")

        # 5. Recency bonus (10 pts)
        winner_year = extract_year(winner.get("award_date", ""))
        if winner_year >= 2024:
            score += 10
            reasons.append("recent (2024+)")
        elif winner_year >= 2023:
            score += 7
            reasons.append("recent (2023)")
        elif winner_year >= 2021:
            score += 3

        # Threshold: only include if score >= 25
        if score >= 25:
            similar.append({
                "winner": winner,
                "company": winner_company,
                "funder": winner.get("funder", ""),
                "amount": winner_amt,
                "year": winner_year,
                "title": winner_title[:120],
                "abstract": winner_abstract[:500],
                "keywords": list(winner_keywords)[:8],
                "similarity_score": score,
                "match_reasons": reasons,
            })

    similar.sort(key=lambda x: x["similarity_score"], reverse=True)
    return similar[:5]


def load_all_winners() -> list[dict]:
    """Load all winners from data files."""
    import json
    from pathlib import Path

    winners: list[dict] = []
    data_dir = Path("data")

    for path in sorted(data_dir.glob("winners_*.json")):
        try:
            with open(path) as f:
                data = json.load(f)
                items = data if isinstance(data, list) else data.get("awards", data.get("winners", []))
                winners.extend(items)
                logger.info("Loaded %d winners from %s", len(items), path.name)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.debug("Skipping %s: %s", path.name, e)

    return winners


if __name__ == "__main__":
    import json

    sample_grant = {
        "title": "AI for Critical Mineral Exploration",
        "funder": "Department of Energy",
        "description": "Machine learning for lithium and copper deposit prediction",
        "amount_max": 250000,
        "industry_tags": ["AI", "mining", "critical minerals"],
    }

    winners = load_all_winners()
    print(f"Loaded {len(winners)} total winners")

    results = find_similar_winners(sample_grant, winners)
    print(f"Found {len(results)} similar winners:")
    for r in results:
        print(f"  [{r['similarity_score']}] {r['company']} - {r['title'][:60]}")
        print(f"       Reasons: {', '.join(r['match_reasons'])}")

    if not results:
        print("  (no winners data available yet - run winner scrapers first)")
