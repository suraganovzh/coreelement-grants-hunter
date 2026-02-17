"""Telegram bot command handlers."""

from telegram import Update
from telegram.ext import ContextTypes

from src.bot.keyboards import Keyboards
from src.bot.notifications import NotificationService
from src.database.queries import GrantQueries
from src.utils.logger import setup_logger
from src.utils.text_processor import TextProcessor
from src.utils.date_utils import DateUtils

logger = setup_logger("bot_handlers")


class BotHandlers:
    """Handle all Telegram bot commands and callbacks."""

    def __init__(self):
        self.keyboards = Keyboards()

    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command."""
        await update.message.reply_text(
            "Welcome to Core Element Grant Hunter AI!\n\n"
            "I automatically find and analyze grants for Core Element AI's "
            "probabilistic mineral exploration technology.\n\n"
            "Commands:\n"
            "/status - Current grants in progress\n"
            "/urgent - Urgent deadlines (<7 days)\n"
            "/pipeline - Full grant pipeline\n"
            "/search <keyword> - Search grants\n"
            "/details <id> - Grant details\n"
            "/fit <id> - Fit analysis\n"
            "/similar <id> - Find similar grants\n"
            "/stats - Statistics\n"
            "/draft <id> - Start application draft\n"
            "/settings - Notification settings\n"
            "/help - Help"
        )

    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command."""
        await update.message.reply_text(
            "Grant Hunter AI - Help\n\n"
            "SEARCH & DISCOVERY:\n"
            "/pipeline - View all grants by urgency\n"
            "/urgent - Grants with deadlines <7 days\n"
            "/search <keyword> - Search by keyword\n"
            "/similar <id> - Find similar grants\n\n"
            "ANALYSIS:\n"
            "/details <id> - Full grant details\n"
            "/fit <id> - Detailed fit analysis\n\n"
            "APPLICATION:\n"
            "/draft <id> - Generate application draft\n"
            "/status - Track application statuses\n\n"
            "REPORTING:\n"
            "/stats - Overall statistics\n\n"
            "SETTINGS:\n"
            "/settings - Configure notifications\n\n"
            "Daily digest is sent automatically at 09:00 UTC."
        )

    async def cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /status command — show grants in progress."""
        db = GrantQueries()
        try:
            pipeline = db.get_pipeline()
            total = sum(len(v) for v in pipeline.values())

            if total == 0:
                await update.message.reply_text("No active grants in pipeline. Run a search first!")
                return

            lines = [f"Grant Pipeline Status — {total} active grants\n"]

            for level, emoji in [("urgent", "🔴"), ("important", "🟡"), ("planning", "🟢")]:
                grants = pipeline[level]
                if grants:
                    lines.append(f"\n{emoji} {level.upper()} ({len(grants)}):")
                    for g in grants[:5]:
                        fit = f"Fit: {g.fit_score}%" if g.fit_score else ""
                        deadline = DateUtils.format_deadline(g.deadline) if g.deadline else "No deadline"
                        lines.append(f"  • {g.title[:60]}")
                        lines.append(f"    {g.funder} | {g.amount_display} | {fit}")
                        lines.append(f"    {deadline}")

            await update.message.reply_text("\n".join(lines))
        finally:
            db.close()

    async def cmd_urgent(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /urgent command — show grants with <7 day deadlines."""
        db = GrantQueries()
        try:
            grants = db.get_urgent_grants(days=7)

            if not grants:
                await update.message.reply_text("No urgent grants (deadline <7 days). Check /pipeline for upcoming.")
                return

            lines = ["🔴 URGENT GRANTS (deadline within 7 days):\n"]
            for g in grants:
                days = g.days_until_deadline
                lines.append(f"• {g.title[:70]}")
                lines.append(f"  {g.funder} | {g.amount_display}")
                lines.append(f"  Fit: {g.fit_score}% | Complexity: {g.complexity_score}/10")
                lines.append(f"  Deadline: {days} day(s) left")
                lines.append(f"  /details {g.id}")
                lines.append("")

            await update.message.reply_text(
                "\n".join(lines),
                reply_markup=self.keyboards.urgent_actions(grants),
            )
        finally:
            db.close()

    async def cmd_pipeline(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /pipeline command — show full pipeline."""
        db = GrantQueries()
        try:
            pipeline = db.get_pipeline()
            stats = db.get_stats()

            lines = ["📊 Grant Pipeline\n"]

            total_potential = stats.get("total_potential_usd", 0)
            lines.append(f"Total potential: {TextProcessor.format_currency(total_potential)}\n")

            for level, emoji, label in [
                ("urgent", "🔴", "URGENT (<7 days)"),
                ("important", "🟡", "IMPORTANT (7-30 days)"),
                ("planning", "🟢", "PLANNING (30+ days)"),
            ]:
                grants = pipeline[level]
                lines.append(f"\n{emoji} {label} — {len(grants)} grants:")
                for g in grants[:10]:
                    fit = f"{g.fit_score}%" if g.fit_score else "N/A"
                    lines.append(f"  [{g.id}] {g.title[:55]}")
                    lines.append(f"      {g.amount_display} | Fit: {fit} | /details {g.id}")

            lines.append(f"\nPipeline: {len(pipeline['urgent'])} urgent, "
                        f"{len(pipeline['important'])} important, "
                        f"{len(pipeline['planning'])} planning")

            await update.message.reply_text("\n".join(lines))
        finally:
            db.close()

    async def cmd_search(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /search <keyword> command."""
        if not context.args:
            await update.message.reply_text("Usage: /search <keyword>\nExample: /search lithium")
            return

        keyword = " ".join(context.args)
        db = GrantQueries()
        try:
            grants = db.search_grants(keyword)

            if not grants:
                await update.message.reply_text(f"No grants found for '{keyword}'. Try different keywords.")
                return

            lines = [f"🔍 Search results for '{keyword}' — {len(grants)} grants:\n"]
            for g in grants[:10]:
                fit = f"Fit: {g.fit_score}%" if g.fit_score else ""
                lines.append(f"  [{g.id}] {g.title[:60]}")
                lines.append(f"      {g.funder} | {g.amount_display} | {fit}")
                lines.append(f"      /details {g.id}")
                lines.append("")

            await update.message.reply_text("\n".join(lines))
        finally:
            db.close()

    async def cmd_details(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /details <grant_id> command."""
        if not context.args:
            await update.message.reply_text("Usage: /details <grant_id>\nExample: /details 1")
            return

        try:
            grant_id = int(context.args[0])
        except ValueError:
            await update.message.reply_text("Invalid grant ID. Use a number.")
            return

        db = GrantQueries()
        try:
            grant = db.get_grant(grant_id)
            if not grant:
                await update.message.reply_text(f"Grant #{grant_id} not found.")
                return

            deadline_str = DateUtils.format_deadline(grant.deadline) if grant.deadline else "No deadline"
            emoji = DateUtils.urgency_emoji(grant.deadline) if grant.deadline else "⚪"

            lines = [
                f"{emoji} Grant #{grant.id}: {grant.title}\n",
                f"Funder: {grant.funder}",
                f"Type: {grant.grant_type}",
                f"Amount: {grant.amount_display}",
                f"Deadline: {deadline_str}",
                f"Source: {grant.source}",
                f"\nFit Score: {grant.fit_score}%",
                f"Complexity: {grant.complexity_score}/10",
                f"Est. Prep Time: {grant.estimated_prep_hours}h",
                f"\nTags: {', '.join(grant.industry_tags or [])}",
            ]

            if grant.description:
                desc = TextProcessor.truncate(grant.description, 500)
                lines.append(f"\nDescription:\n{desc}")

            if grant.eligibility_text:
                lines.append(f"\nEligibility: {grant.eligibility_text[:300]}")

            if grant.url:
                lines.append(f"\nURL: {grant.url}")

            await update.message.reply_text(
                "\n".join(lines),
                reply_markup=self.keyboards.grant_actions(grant_id),
            )
        finally:
            db.close()

    async def cmd_fit(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /fit <grant_id> — detailed fit analysis."""
        if not context.args:
            await update.message.reply_text("Usage: /fit <grant_id>")
            return

        try:
            grant_id = int(context.args[0])
        except ValueError:
            await update.message.reply_text("Invalid grant ID.")
            return

        db = GrantQueries()
        try:
            grant = db.get_grant(grant_id)
            if not grant:
                await update.message.reply_text(f"Grant #{grant_id} not found.")
                return

            from src.analyzers.fit_scorer import FitScorer
            scorer = FitScorer()
            result = scorer.score(
                title=grant.title,
                description=grant.description or "",
                funder=grant.funder or "",
                grant_type=grant.grant_type or "",
                eligibility_text=grant.eligibility_text or "",
                amount_min=grant.amount_min,
                amount_max=grant.amount_max,
                deadline_days=grant.days_until_deadline,
                complexity=grant.complexity_score,
            )

            breakdown = result.get("breakdown", {})
            lines = [
                f"📊 Fit Analysis — Grant #{grant_id}\n",
                f"Title: {grant.title[:60]}\n",
                f"OVERALL FIT: {result['overall']}%\n",
                "Breakdown:",
            ]
            for key, val in breakdown.items():
                label = key.replace("_", " ").title()
                bar = "█" * (val // 10) + "░" * (10 - val // 10)
                lines.append(f"  {label}: {bar} {val}%")

            lines.append(f"\n{result['recommendation']}")

            await update.message.reply_text("\n".join(lines))
        finally:
            db.close()

    async def cmd_similar(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /similar <grant_id>."""
        if not context.args:
            await update.message.reply_text("Usage: /similar <grant_id>")
            return

        try:
            grant_id = int(context.args[0])
        except ValueError:
            await update.message.reply_text("Invalid grant ID.")
            return

        from src.analyzers.similar_finder import SimilarFinder
        finder = SimilarFinder()
        try:
            similar = finder.find_similar(grant_id, limit=5)
            if not similar:
                await update.message.reply_text("No similar grants found.")
                return

            lines = [f"🔗 Grants similar to #{grant_id}:\n"]
            for s in similar:
                lines.append(f"  [{s['id']}] {s['title'][:55]}")
                lines.append(f"      Similarity: {s['similarity']}% | Fit: {s['fit_score']}%")
                lines.append(f"      {s['amount']} | /details {s['id']}")
                lines.append("")

            await update.message.reply_text("\n".join(lines))
        finally:
            finder.close()

    async def cmd_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /stats command."""
        db = GrantQueries()
        try:
            stats = db.get_stats()
            lines = [
                "📈 Grant Hunter Statistics\n",
                f"Total grants found: {stats['total_found']}",
                f"Qualified: {stats['qualified']}",
                f"Active (not expired): {stats['active']}",
                f"Applications submitted: {stats['submitted']}",
                f"Grants won: {stats['won']}",
                f"\nTotal potential: {TextProcessor.format_currency(stats['total_potential_usd'])}",
                f"Total won: {TextProcessor.format_currency(stats['total_won_usd'])}",
            ]
            await update.message.reply_text("\n".join(lines))
        finally:
            db.close()

    async def cmd_settings(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /settings command."""
        await update.message.reply_text(
            "⚙️ Settings\n\n"
            "Daily digest: 09:00 UTC\n"
            "Reminder days: 14, 7, 3, 1\n"
            "Min fit score: 40%\n\n"
            "To change settings, edit config/filters.yaml"
        )

    async def cmd_draft(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /draft <grant_id> — start application draft."""
        if not context.args:
            await update.message.reply_text("Usage: /draft <grant_id>")
            return

        try:
            grant_id = int(context.args[0])
        except ValueError:
            await update.message.reply_text("Invalid grant ID.")
            return

        db = GrantQueries()
        try:
            grant = db.get_grant(grant_id)
            if not grant:
                await update.message.reply_text(f"Grant #{grant_id} not found.")
                return

            await update.message.reply_text(
                f"✍️ Starting draft for: {grant.title[:60]}\n\n"
                "Generating application sections with AI...\nThis may take a moment."
            )

            # Create application record
            app = db.create_application(grant_id=grant_id, status="draft")

            # Generate sections
            from src.generators.executive_summary import ExecutiveSummaryGenerator
            gen = ExecutiveSummaryGenerator()
            exec_summary = gen.generate(
                grant.title,
                grant.requirements_text or grant.description or "",
                ", ".join(grant.industry_tags or []),
            )

            db.update_application(app.id, executive_summary=exec_summary)

            await update.message.reply_text(
                f"📝 Draft created! Application #{app.id}\n\n"
                f"Executive Summary (preview):\n{exec_summary[:500]}...\n\n"
                "Use /details to review. More sections can be generated on demand."
            )
        except Exception as e:
            logger.error("Draft generation failed: %s", e)
            await update.message.reply_text("Failed to generate draft. Check logs.")
        finally:
            db.close()

    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle inline button callbacks."""
        query = update.callback_query
        await query.answer()

        data = query.data or ""
        parts = data.split(":")

        if len(parts) < 2:
            return

        action = parts[0]
        grant_id = parts[1]

        if action == "details":
            context.args = [grant_id]
            await self.cmd_details(update, context)
        elif action == "fit":
            context.args = [grant_id]
            await self.cmd_fit(update, context)
        elif action == "draft":
            context.args = [grant_id]
            await self.cmd_draft(update, context)
        elif action == "similar":
            context.args = [grant_id]
            await self.cmd_similar(update, context)
        elif action == "priority":
            db = GrantQueries()
            try:
                db.update_grant(int(grant_id), status="qualified")
                await query.edit_message_text(f"⭐ Grant #{grant_id} marked as HIGH PRIORITY")
            finally:
                db.close()
        elif action == "dismiss":
            db = GrantQueries()
            try:
                db.update_grant(int(grant_id), status="not_relevant")
                await query.edit_message_text(f"❌ Grant #{grant_id} dismissed")
            finally:
                db.close()
