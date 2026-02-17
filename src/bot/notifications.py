"""Notification service — formats and sends grant alerts via Telegram."""

import os
from datetime import date

from telegram import Bot

from src.bot.keyboards import Keyboards
from src.database.queries import GrantQueries
from src.utils.logger import setup_logger
from src.utils.text_processor import TextProcessor
from src.utils.date_utils import DateUtils

logger = setup_logger("notifications")


class NotificationService:
    """Format and send grant notifications via Telegram."""

    def __init__(self, chat_id: str | None = None):
        self.chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID", "")
        self.keyboards = Keyboards()

    async def send_daily_digest(self, bot: Bot):
        """Send daily grant digest to configured chat."""
        if not self.chat_id:
            logger.error("TELEGRAM_CHAT_ID not configured")
            return

        db = GrantQueries()
        try:
            pipeline = db.get_pipeline()
            stats = db.get_stats()

            today = date.today().strftime("%b %d, %Y")
            lines = [f"📊 Daily Grant Report — {today}\n"]

            # Urgent
            urgent = pipeline["urgent"]
            if urgent:
                lines.append(f"🔴 URGENT ({len(urgent)} — deadline <7 days):")
                for g in urgent[:5]:
                    days = g.days_until_deadline or 0
                    fit = f"Fit: {g.fit_score}%" if g.fit_score else ""
                    cx = f"Complexity: {g.complexity_score}/10" if g.complexity_score else ""
                    prep = f"Prep: {g.estimated_prep_hours}h" if g.estimated_prep_hours else ""
                    lines.append(f"  • {g.title[:60]}")
                    lines.append(f"    {g.funder} — {g.amount_display}")
                    lines.append(f"    {fit} | {cx} | {prep}")
                    lines.append(f"    Deadline: {days}d left | /details {g.id}")
                lines.append("")

            # Important
            important = pipeline["important"]
            if important:
                lines.append(f"🟡 IMPORTANT ({len(important)} — 7-30 days):")
                for g in important[:5]:
                    days = g.days_until_deadline or 0
                    lines.append(f"  • {g.title[:60]}")
                    lines.append(f"    {g.funder} — {g.amount_display} | Fit: {g.fit_score}%")
                    lines.append(f"    Deadline: {days}d | /details {g.id}")
                lines.append("")

            # Planning
            planning = pipeline["planning"]
            if planning:
                lines.append(f"🟢 PLANNING ({len(planning)} — 30+ days):")
                for g in planning[:3]:
                    lines.append(f"  • {g.title[:60]}")
                    lines.append(f"    {g.amount_display} | Fit: {g.fit_score}% | /details {g.id}")
                lines.append("")

            # Summary
            total = len(urgent) + len(important) + len(planning)
            potential = TextProcessor.format_currency(stats.get("total_potential_usd", 0))
            lines.append(f"📈 Pipeline: {len(urgent)} urgent, {len(important)} important, {len(planning)} planning")
            lines.append(f"💰 Total potential: {potential}")

            message = "\n".join(lines)
            keyboard = self.keyboards.digest_actions(pipeline)

            await bot.send_message(
                chat_id=self.chat_id,
                text=message,
                reply_markup=keyboard,
            )
            logger.info("Daily digest sent: %d grants", total)

        except Exception as e:
            logger.error("Failed to send daily digest: %s", e)
        finally:
            db.close()

    async def send_deadline_reminders(self, bot: Bot):
        """Send reminders for grants approaching deadlines."""
        if not self.chat_id:
            return

        db = GrantQueries()
        try:
            grants = db.get_grants_needing_reminder()

            for grant in grants:
                days = grant.days_until_deadline or 0
                reminder_msg = DateUtils.should_remind(grant.deadline)
                if not reminder_msg:
                    continue

                emoji = "🚨" if days <= 1 else "⚠️" if days <= 3 else "⏰" if days <= 7 else "📅"

                message = (
                    f"{emoji} DEADLINE REMINDER\n\n"
                    f"{grant.title[:70]}\n"
                    f"Funder: {grant.funder}\n"
                    f"Amount: {grant.amount_display}\n"
                    f"Deadline: {days} day(s) left\n\n"
                    f"{reminder_msg}\n\n"
                    f"/details {grant.id}"
                )

                keyboard = self.keyboards.reminder_actions(grant.id)
                await bot.send_message(
                    chat_id=self.chat_id,
                    text=message,
                    reply_markup=keyboard,
                )

                db.create_alert(
                    grant_id=grant.id,
                    alert_type="deadline_warning",
                    urgency="urgent" if days <= 3 else "important",
                    message=reminder_msg,
                )

            if grants:
                logger.info("Sent %d deadline reminders", len(grants))

        except Exception as e:
            logger.error("Failed to send reminders: %s", e)
        finally:
            db.close()

    async def notify_new_grants(self, bot: Bot, new_grants: list):
        """Notify about newly found high-fit grants."""
        if not self.chat_id or not new_grants:
            return

        # Only notify for high-fit grants
        notable = [g for g in new_grants if (g.get("fit_score") or 0) >= 70]
        if not notable:
            return

        lines = [f"🆕 {len(notable)} new high-fit grants found!\n"]
        for g in notable[:5]:
            lines.append(f"  • {g.get('title', '')[:60]}")
            lines.append(f"    Fit: {g.get('fit_score', 'N/A')}% | {g.get('amount_display', 'N/A')}")
            lines.append(f"    /details {g.get('id', '')}")
            lines.append("")

        try:
            await bot.send_message(chat_id=self.chat_id, text="\n".join(lines))
            logger.info("Notified about %d new grants", len(notable))
        except Exception as e:
            logger.error("Failed to notify new grants: %s", e)
