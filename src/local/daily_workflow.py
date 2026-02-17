"""Main local workflow for Surface ARM.

Runs: git pull -> filter -> analyze -> notify -> save -> git push

LLM cascade (automatic fallback):
  1. Ollama local (Llama 3.2 3B / 3.1 8B) — if computer is on
  2. Groq cloud free tier (Llama 3.3 70B) — if computer is off / Ollama down
  3. Rule-based keywords — always works, no API needed

Usage:
    python -m src.local.daily_workflow          # Full daily pipeline
    python -m src.local.daily_workflow --skip-pull   # Skip git pull
"""

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from src.local.filter import filter_grants
from src.local.analyze import analyze_grants
from src.local.telegram_notify import send_summary, send_priority_grants
from src.utils.logger import setup_logger

logger = setup_logger("daily_workflow")


def git_pull() -> bool:
    """Pull latest data from GitHub."""
    print("Pulling latest data from GitHub...")
    result = subprocess.run(["git", "pull"], capture_output=True, text=True)
    if result.returncode == 0:
        print(f"   {result.stdout.strip()}")
        return True
    else:
        print(f"   Git pull failed: {result.stderr.strip()}")
        return False


def git_push(message: str):
    """Commit and push results to GitHub."""
    print("Pushing results to GitHub...")
    subprocess.run(["git", "add", "data/"], capture_output=True)

    # Check if there are changes to commit
    status = subprocess.run(["git", "diff", "--cached", "--quiet"], capture_output=True)
    if status.returncode == 0:
        print("   No changes to commit")
        return

    subprocess.run(["git", "commit", "-m", message], capture_output=True)
    result = subprocess.run(["git", "push"], capture_output=True, text=True)
    if result.returncode == 0:
        print("   Pushed successfully")
    else:
        print(f"   Push failed: {result.stderr.strip()}")


def load_data() -> tuple[list[dict], dict, set[str]]:
    """Load grants and patterns from data directory.

    Returns:
        Tuple of (new_grants, patterns, processed_ids).
    """
    # Load grants
    grants_data: dict = {}
    grants_file = Path("data/grants.json")
    if grants_file.exists():
        with open(grants_file) as f:
            grants_data = json.load(f)

    all_grants = grants_data.get("grants", []) if isinstance(grants_data, dict) else grants_data

    # Load patterns
    patterns: dict = {}
    patterns_file = Path("data/patterns.json")
    if patterns_file.exists():
        with open(patterns_file) as f:
            patterns = json.load(f)

    # Load processed IDs
    processed_ids: set[str] = set()
    processed_file = Path("data/processed_ids.json")
    if processed_file.exists():
        with open(processed_file) as f:
            processed_ids = set(json.load(f))

    # Filter to only unprocessed grants
    new_grants = [g for g in all_grants if g.get("id") not in processed_ids]

    print(f"Loaded {len(new_grants)} new grants (of {len(all_grants)} total)")
    return new_grants, patterns, processed_ids


def save_processed_ids(processed_ids: set[str]):
    """Save processed grant IDs to avoid re-processing."""
    Path("data").mkdir(exist_ok=True)
    with open("data/processed_ids.json", "w") as f:
        json.dump(sorted(processed_ids), f)


def save_analyzed(analyzed: list[dict]):
    """Save analyzed grants."""
    Path("data").mkdir(exist_ok=True)

    # Load existing analyzed
    existing: list[dict] = []
    analyzed_file = Path("data/analyzed.json")
    if analyzed_file.exists():
        try:
            with open(analyzed_file) as f:
                data = json.load(f)
                existing = data if isinstance(data, list) else data.get("grants", [])
        except (json.JSONDecodeError, FileNotFoundError):
            pass

    existing.extend(analyzed)

    with open("data/analyzed.json", "w") as f:
        json.dump(existing, f, indent=2)


def main():
    parser = argparse.ArgumentParser(description="Grant Hunter AI - Daily Local Workflow")
    parser.add_argument("--skip-pull", action="store_true", help="Skip git pull")
    parser.add_argument("--skip-push", action="store_true", help="Skip git push")
    args = parser.parse_args()

    print("Starting Grant Hunter AI Daily Workflow")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # Step 1: Pull latest data
    if not args.skip_pull:
        if not git_pull():
            print("WARNING: Git pull failed, continuing with local data...")

    # Step 2: Load data
    new_grants, patterns, processed_ids = load_data()

    if not new_grants:
        print("No new grants to process")
        return

    # Step 3: Filter (cascade: Ollama -> Groq -> rules)
    print(f"\nSTEP 1: Filtering {len(new_grants)} grants")
    print("-" * 60)
    filtered_grants = filter_grants(new_grants)
    print(f"Result: {len(filtered_grants)} grants passed filter")

    if not filtered_grants:
        for grant in new_grants:
            processed_ids.add(grant.get("id", ""))
        save_processed_ids(processed_ids)
        if not args.skip_push:
            git_push(f"Daily: {len(new_grants)} grants filtered, none qualified")
        return

    # Step 4: Analyze (cascade: Ollama -> Groq -> rules)
    print(f"\nSTEP 2: Analyzing {len(filtered_grants)} grants")
    print("-" * 60)
    analyzed_grants = analyze_grants(filtered_grants, patterns)

    copy_now = [g for g in analyzed_grants if g.get("analysis", {}).get("priority") == "copy_now"]
    test_first = [g for g in analyzed_grants if g.get("analysis", {}).get("priority") == "test_first"]

    print(f"\nAnalysis complete:")
    print(f"   >> copy_now:   {len(copy_now)} grants")
    print(f"   ** test_first: {len(test_first)} grants")
    print(f"   -- skip:       {len(analyzed_grants) - len(copy_now) - len(test_first)} grants")

    # Step 5: Send Telegram notification
    print(f"\nSTEP 3: Sending Telegram summary")
    print("-" * 60)
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    send_summary(copy_now, test_first)
    if copy_now:
        send_priority_grants(copy_now[:3])

    # Step 6: Save results
    print(f"\nSaving results")
    print("-" * 60)
    save_analyzed(analyzed_grants)

    for grant in new_grants:
        processed_ids.add(grant.get("id", ""))
    save_processed_ids(processed_ids)

    # Step 7: Push to GitHub
    if not args.skip_push:
        commit_msg = (
            f"Daily workflow: {len(copy_now)} copy_now, "
            f"{len(test_first)} test_first "
            f"({datetime.now().strftime('%Y-%m-%d')})"
        )
        git_push(commit_msg)

    # Summary
    print(f"\n{'=' * 60}")
    print(f"Workflow complete!")
    print(f"   Processed: {len(new_grants)} grants")
    print(f"   Qualified: {len(filtered_grants)} grants")
    print(f"   High priority: {len(copy_now)} grants")
    print(f"   Medium priority: {len(test_first)} grants")

    total_potential = sum(g.get("amount_max", 0) for g in copy_now + test_first)
    if total_potential > 0:
        print(f"   Total potential: ${total_potential:,}")


if __name__ == "__main__":
    main()
