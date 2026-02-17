"""Extract success patterns from awarded grants.

Analyzes historical winners to identify:
- Winning keywords and themes
- Funder-specific patterns
- Amount range patterns
- Company profile patterns

Used by the local ARM analysis pipeline (Llama 3.1 8B)
to predict win probability for new grants.
"""

import argparse
import json
from collections import Counter
from datetime import datetime
from pathlib import Path

from src.utils.logger import setup_logger

logger = setup_logger("pattern_extractor")


def load_winners() -> list[dict]:
    """Load all winner data from multiple sources."""
    winners: list[dict] = []

    sources = [
        "data/winners_grants_gov.json",
        "data/winners_sbir.json",
    ]

    for source in sources:
        try:
            with open(source) as f:
                data = json.load(f)
                if isinstance(data, list):
                    winners.extend(data)
                elif isinstance(data, dict):
                    winners.append(data)
            logger.info("Loaded %d winners from %s", len(data) if isinstance(data, list) else 1, source)
        except FileNotFoundError:
            logger.debug("Source not found: %s", source)

    return winners


def extract_keyword_patterns(winners: list[dict]) -> list[dict]:
    """Extract most common keywords in winning grants."""
    keyword_counter: Counter = Counter()

    for winner in winners:
        for keyword in winner.get("keywords", []):
            keyword_counter[keyword] += 1

    total = max(len(winners), 1)
    patterns = []

    for keyword, count in keyword_counter.most_common(30):
        patterns.append({
            "keyword": keyword,
            "frequency": round(count / total, 3),
            "count": count,
            "pattern_type": "keyword",
        })

    return patterns


def extract_funder_patterns(winners: list[dict]) -> list[dict]:
    """Extract patterns grouped by funder."""
    funder_groups: dict[str, dict] = {}

    for winner in winners:
        funder = winner.get("funder", "Unknown")

        if funder not in funder_groups:
            funder_groups[funder] = {
                "funder": funder,
                "total_awards": 0,
                "total_amount": 0,
                "keywords": Counter(),
                "companies": [],
                "phases": Counter(),
            }

        group = funder_groups[funder]
        group["total_awards"] += 1

        amount = winner.get("amount", 0)
        if isinstance(amount, (int, float)) and amount > 0:
            group["total_amount"] += amount

        for kw in winner.get("keywords", []):
            group["keywords"][kw] += 1

        company = winner.get("winner", "")
        if company and company not in group["companies"]:
            group["companies"].append(company)

        phase = winner.get("phase")
        if phase:
            group["phases"][str(phase)] += 1

    patterns = []
    for funder, data in funder_groups.items():
        if data["total_awards"] == 0:
            continue

        avg_amount = data["total_amount"] / data["total_awards"] if data["total_awards"] > 0 else 0

        pattern = {
            "funder": funder,
            "total_awards": data["total_awards"],
            "avg_amount": round(avg_amount),
            "top_keywords": [
                {"keyword": kw, "count": count}
                for kw, count in data["keywords"].most_common(10)
            ],
            "sample_companies": data["companies"][:15],
            "phases": dict(data["phases"]),
            "pattern_type": "funder",
        }
        patterns.append(pattern)

    return sorted(patterns, key=lambda x: x["total_awards"], reverse=True)


def extract_amount_patterns(winners: list[dict]) -> list[dict]:
    """Extract patterns grouped by grant amount range."""
    ranges = [
        (0, 50_000, "small", "$0-$50K"),
        (50_000, 250_000, "medium", "$50K-$250K"),
        (250_000, 1_000_000, "large", "$250K-$1M"),
        (1_000_000, float("inf"), "xlarge", "$1M+"),
    ]

    range_data = {
        name: {"count": 0, "keywords": Counter(), "funders": Counter(), "label": label}
        for _, _, name, label in ranges
    }

    for winner in winners:
        amount = winner.get("amount", 0)
        if not isinstance(amount, (int, float)) or amount <= 0:
            continue

        for min_amt, max_amt, name, _ in ranges:
            if min_amt <= amount < max_amt:
                range_data[name]["count"] += 1
                for kw in winner.get("keywords", []):
                    range_data[name]["keywords"][kw] += 1
                funder = winner.get("funder", "")
                if funder:
                    range_data[name]["funders"][funder] += 1
                break

    patterns = []
    for name, data in range_data.items():
        if data["count"] > 0:
            pattern = {
                "size": name,
                "label": data["label"],
                "count": data["count"],
                "top_keywords": [
                    {"keyword": kw, "count": c}
                    for kw, c in data["keywords"].most_common(10)
                ],
                "top_funders": [
                    {"funder": f, "count": c}
                    for f, c in data["funders"].most_common(10)
                ],
                "pattern_type": "amount",
            }
            patterns.append(pattern)

    return patterns


def extract_company_patterns(winners: list[dict]) -> list[dict]:
    """Extract patterns about winning company characteristics."""
    company_counter: Counter = Counter()
    company_amounts: dict[str, list[int]] = {}

    for winner in winners:
        company = winner.get("winner", "").strip()
        if not company:
            continue

        company_counter[company] += 1
        amount = winner.get("amount", 0)
        if isinstance(amount, (int, float)) and amount > 0:
            company_amounts.setdefault(company, []).append(amount)

    patterns = []
    for company, count in company_counter.most_common(20):
        amounts = company_amounts.get(company, [])
        pattern = {
            "company": company,
            "total_wins": count,
            "total_amount": sum(amounts),
            "avg_amount": round(sum(amounts) / len(amounts)) if amounts else 0,
            "pattern_type": "company",
        }
        patterns.append(pattern)

    return patterns


def main():
    parser = argparse.ArgumentParser(description="Extract patterns from awarded grants")
    parser.add_argument("--output", default="data/patterns.json")
    args = parser.parse_args()

    print("Loading winners...")
    winners = load_winners()
    print(f"Loaded {len(winners)} awarded grants")

    if not winners:
        print("No winners found. Run winner scrapers first.")
        # Create empty patterns file so downstream doesn't break
        empty = {"metadata": {"generated_at": datetime.now().isoformat(), "total_winners_analyzed": 0},
                 "keyword_patterns": [], "funder_patterns": [], "amount_patterns": [], "company_patterns": []}
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, "w") as f:
            json.dump(empty, f, indent=2)
        return

    print("\nExtracting patterns...")

    award_dates = [w.get("award_date", "") for w in winners if w.get("award_date")]

    patterns = {
        "metadata": {
            "generated_at": datetime.now().isoformat(),
            "total_winners_analyzed": len(winners),
            "date_range": {
                "earliest": min(award_dates) if award_dates else "",
                "latest": max(award_dates) if award_dates else "",
            },
        },
        "keyword_patterns": extract_keyword_patterns(winners),
        "funder_patterns": extract_funder_patterns(winners),
        "amount_patterns": extract_amount_patterns(winners),
        "company_patterns": extract_company_patterns(winners),
    }

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w") as f:
        json.dump(patterns, f, indent=2)

    print(f"\nPatterns saved to {args.output}")

    print("\nTop 5 keywords:")
    for p in patterns["keyword_patterns"][:5]:
        print(f"  - {p['keyword']}: {p['frequency']*100:.1f}% ({p['count']} grants)")

    print("\nTop 5 funders:")
    for p in patterns["funder_patterns"][:5]:
        print(f"  - {p['funder']}: {p['total_awards']} awards, avg ${p['avg_amount']:,}")

    print("\nTop 5 repeat winners:")
    for p in patterns["company_patterns"][:5]:
        print(f"  - {p['company']}: {p['total_wins']} wins, ${p['total_amount']:,} total")


if __name__ == "__main__":
    main()
