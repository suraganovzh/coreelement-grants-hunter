"""Main orchestrator for Grant Hunter AI.

Usage:
    python -m src.main --mode=scrape      # Run all scrapers
    python -m src.main --mode=analyze     # Analyze found grants
    python -m src.main --mode=notify      # Send notifications
    python -m src.main --mode=full        # Full pipeline
    python -m src.main --mode=bot         # Start Telegram bot
"""

import argparse
import time
import json
from datetime import datetime

from dotenv import load_dotenv

from src.database.models import init_db, get_session, Grant
from src.database.queries import GrantQueries
from src.scrapers import ALL_SCRAPERS
from src.analyzers.eligibility_checker import EligibilityChecker
from src.analyzers.fit_scorer import FitScorer
from src.analyzers.complexity_scorer import ComplexityScorer
from src.utils.api_clients import GroqClient
from src.utils.logger import setup_logger
from src.utils.date_utils import DateUtils

logger = setup_logger("main")


def run_scrapers() -> list[dict]:
    """Run all enabled scrapers and store results in database."""
    logger.info("=== Starting grant scraping ===")
    db = GrantQueries()
    new_grants = []
    total_found = 0

    for scraper_class in ALL_SCRAPERS:
        scraper_name = scraper_class.__name__
        start = time.monotonic()

        try:
            with scraper_class() as scraper:
                logger.info("Running scraper: %s", scraper.name)
                results = scraper.search()
                total_found += len(results)

                for result in results:
                    # Skip duplicates
                    if result.url and db.grant_exists(result.url):
                        continue

                    # Skip expired grants (deadline already passed)
                    if result.deadline:
                        days = DateUtils.days_until(result.deadline)
                        if days is not None and days < 0:
                            logger.debug("Skipping expired grant: %s (deadline: %s)", result.title, result.deadline)
                            continue

                    grant = db.add_grant(
                        title=result.title,
                        funder=result.funder,
                        description=result.description,
                        amount_min=result.amount_min,
                        amount_max=result.amount_max,
                        currency=result.currency,
                        deadline=result.deadline,
                        url=result.url,
                        source=result.source,
                        grant_type=result.grant_type,
                        industry_tags=result.industry_tags,
                        eligibility_text=result.eligibility_text,
                        requirements_text=result.requirements_text,
                        evaluation_criteria=result.evaluation_criteria,
                    )
                    new_grants.append({
                        "id": grant.id,
                        "title": grant.title,
                        "funder": grant.funder,
                        "amount_display": grant.amount_display,
                    })

                elapsed = time.monotonic() - start
                db.log_search(
                    source=scraper.name,
                    query="scheduled_daily",
                    results=len(results),
                    new_found=len([r for r in results if r.url and not db.grant_exists(r.url)]),
                    duration=elapsed,
                )
                logger.info("[%s] Found %d grants (%d new) in %.1fs",
                           scraper.name, len(results), len(new_grants), elapsed)

        except Exception as e:
            logger.error("Scraper %s failed: %s", scraper_name, e)
            db.log_search(source=scraper_name, query="scheduled_daily",
                         results=0, new_found=0, duration=0, errors=str(e))

    db.close()
    logger.info("=== Scraping complete: %d total found, %d new ===", total_found, len(new_grants))
    return new_grants


def run_analysis():
    """Analyze all unscored grants."""
    logger.info("=== Starting grant analysis ===")
    db = GrantQueries()
    fit_scorer = FitScorer()
    complexity_scorer = ComplexityScorer()
    eligibility_checker = EligibilityChecker()

    # Get grants that need analysis (no fit_score yet)
    session = db.session
    unscored = session.query(Grant).filter(
        Grant.fit_score.is_(None),
        Grant.status.in_(["found"]),
    ).all()

    logger.info("Analyzing %d unscored grants", len(unscored))
    analyzed = 0

    for grant in unscored:
        try:
            # Fit scoring
            fit_result = fit_scorer.score(
                title=grant.title,
                description=grant.description or "",
                funder=grant.funder or "",
                grant_type=grant.grant_type or "",
                eligibility_text=grant.eligibility_text or "",
                amount_min=grant.amount_min,
                amount_max=grant.amount_max,
                deadline_days=grant.days_until_deadline,
            )
            grant.fit_score = fit_result["overall"]

            # Complexity scoring
            cx_result = complexity_scorer.score(
                grant_text=f"{grant.description or ''} {grant.requirements_text or ''} {grant.eligibility_text or ''}",
                grant_type=grant.grant_type or "",
                amount=grant.amount_max,
            )
            grant.complexity_score = cx_result["score"]
            grant.estimated_prep_hours = cx_result["estimated_hours"]

            # Urgency
            if grant.deadline:
                grant.urgency = DateUtils.urgency_level(grant.deadline)

            # Eligibility check (AI-powered for high-fit grants)
            if fit_result["overall"] >= 50:
                elig = eligibility_checker.check(
                    grant.title,
                    f"{grant.description or ''}\n{grant.eligibility_text or ''}",
                    grant.grant_type or "",
                )
                grant.ai_analysis = json.dumps(elig)
                if elig.get("eligible") and fit_result["overall"] >= 70:
                    grant.status = "qualified"

            grant.updated_at = datetime.utcnow()
            analyzed += 1

        except Exception as e:
            logger.error("Failed to analyze grant %d: %s", grant.id, e)

    session.commit()
    db.close()
    logger.info("=== Analysis complete: %d grants analyzed ===", analyzed)


async def run_notifications():
    """Send Telegram notifications."""
    logger.info("=== Sending notifications ===")
    from src.bot.telegram_bot import GrantHunterBot
    bot = GrantHunterBot()
    app = bot.build_app()

    async with app:
        await bot.send_daily_digest(app)
        await bot.send_deadline_reminders(app)

    logger.info("=== Notifications sent ===")


async def run_full_pipeline():
    """Run the complete pipeline: scrape -> analyze -> notify."""
    logger.info("========== FULL PIPELINE START ==========")

    # Step 1: Scrape
    new_grants = run_scrapers()

    # Step 2: Analyze
    run_analysis()

    # Step 3: Notify
    await run_notifications()

    logger.info("========== FULL PIPELINE COMPLETE ==========")
    return new_grants


def run_bot():
    """Start the Telegram bot in polling mode."""
    from src.bot.telegram_bot import GrantHunterBot
    bot = GrantHunterBot()
    bot.run()


def main():
    load_dotenv()
    init_db()

    parser = argparse.ArgumentParser(description="Grant Hunter AI")
    parser.add_argument(
        "--mode",
        choices=["scrape", "analyze", "notify", "full", "bot"],
        default="full",
        help="Operation mode",
    )
    parser.add_argument("--test", action="store_true", help="Run in test mode")
    args = parser.parse_args()

    if args.test:
        logger.info("Running in TEST mode")

    if args.mode == "scrape":
        run_scrapers()
    elif args.mode == "analyze":
        run_analysis()
    elif args.mode == "notify":
        import asyncio
        asyncio.run(run_notifications())
    elif args.mode == "full":
        import asyncio
        asyncio.run(run_full_pipeline())
    elif args.mode == "bot":
        run_bot()


if __name__ == "__main__":
    main()
