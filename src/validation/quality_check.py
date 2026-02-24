"""Data quality validation for grant records."""

import json
from datetime import datetime
from pathlib import Path

from src.utils.logger import setup_logger

logger = setup_logger("quality_check")

REQUIRED_FIELDS = ["id", "title", "funder", "url"]
RECOMMENDED_FIELDS = ["deadline", "amount_max", "source", "grant_type"]


def validate_grant(grant: dict) -> tuple[bool, list[str]]:
    """Validate a single grant record.

    Returns:
        Tuple of (is_valid, list_of_issues).
    """
    issues: list[str] = []

    # Check required fields
    for field in REQUIRED_FIELDS:
        if not grant.get(field):
            issues.append(f"Missing required field: {field}")

    # Check recommended fields
    for field in RECOMMENDED_FIELDS:
        if not grant.get(field):
            issues.append(f"Missing recommended field: {field}")

    # Validate deadline format
    deadline = grant.get("deadline", "")
    if deadline:
        try:
            if isinstance(deadline, str) and deadline:
                datetime.fromisoformat(deadline.replace("Z", "+00:00"))
        except ValueError:
            # Try other common formats
            try:
                datetime.strptime(deadline, "%Y-%m-%d")
            except ValueError:
                issues.append(f"Invalid deadline format: {deadline}")

    # Validate amounts
    amount_min = grant.get("amount_min", 0) or 0
    amount_max = grant.get("amount_max", 0) or 0
    if amount_min and amount_max and amount_min > amount_max:
        issues.append(f"amount_min ({amount_min}) > amount_max ({amount_max})")

    # Validate URL format
    url = grant.get("url", "")
    if url and not url.startswith(("http://", "https://")):
        issues.append(f"Invalid URL format: {url}")

    # Validate currency
    valid_currencies = {"USD", "EUR", "GBP", "CAD", "AUD", "CHF", "KZT"}
    currency = grant.get("currency", "USD")
    if currency and currency not in valid_currencies:
        issues.append(f"Unknown currency: {currency}")

    is_valid = not any("Missing required" in i for i in issues)
    return is_valid, issues


def validate_dataset(grants: list[dict]) -> dict:
    """Validate an entire dataset of grants.

    Returns:
        Summary dict with counts and per-grant issues.
    """
    total = len(grants)
    valid_count = 0
    invalid_count = 0
    all_issues: list[dict] = []

    for grant in grants:
        is_valid, issues = validate_grant(grant)
        if is_valid:
            valid_count += 1
        else:
            invalid_count += 1

        if issues:
            all_issues.append({
                "grant_id": grant.get("id", "unknown"),
                "title": grant.get("title", "")[:60],
                "issues": issues,
            })

    return {
        "total": total,
        "valid": valid_count,
        "invalid": invalid_count,
        "quality_score": round(valid_count / total * 100, 1) if total else 0,
        "issues": all_issues,
        "checked_at": datetime.now().isoformat(),
    }


def main():
    """Run quality check on analyzed.json."""
    import argparse

    parser = argparse.ArgumentParser(description="Validate grant data quality")
    parser.add_argument("--input", default="data/analyzed.json")
    parser.add_argument("--output", default="data/quality_report.json")
    args = parser.parse_args()

    try:
        with open(args.input) as f:
            data = json.load(f)
            grants = data.get("grants", []) if isinstance(data, dict) else data
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error loading {args.input}: {e}")
        return

    report = validate_dataset(grants)

    print(f"Quality Report for {args.input}")
    print(f"  Total grants: {report['total']}")
    print(f"  Valid: {report['valid']}")
    print(f"  Invalid: {report['invalid']}")
    print(f"  Quality score: {report['quality_score']}%")

    if report["issues"]:
        print(f"\n  Issues found in {len(report['issues'])} grants:")
        for item in report["issues"][:10]:
            print(f"    - {item['title']}: {', '.join(item['issues'][:3])}")

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w") as f:
        json.dump(report, f, indent=2)

    print(f"\n  Full report saved to {args.output}")


if __name__ == "__main__":
    main()
