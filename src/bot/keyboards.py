"""Inline keyboard layouts for the Telegram bot."""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup


class Keyboards:
    """Inline keyboard factories for grant bot interactions."""

    @staticmethod
    def grant_actions(grant_id: int) -> InlineKeyboardMarkup:
        """Keyboard for individual grant details view."""
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton("📊 Fit Analysis", callback_data=f"fit:{grant_id}"),
                InlineKeyboardButton("✍️ Start Draft", callback_data=f"draft:{grant_id}"),
            ],
            [
                InlineKeyboardButton("🔗 Similar Grants", callback_data=f"similar:{grant_id}"),
                InlineKeyboardButton("⭐ High Priority", callback_data=f"priority:{grant_id}"),
            ],
            [
                InlineKeyboardButton("❌ Not Relevant", callback_data=f"dismiss:{grant_id}"),
            ],
        ])

    @staticmethod
    def urgent_actions(grants: list) -> InlineKeyboardMarkup:
        """Keyboard for urgent grants list."""
        buttons = []
        for grant in grants[:5]:
            buttons.append([
                InlineKeyboardButton(
                    f"📋 #{grant.id}: {grant.title[:30]}...",
                    callback_data=f"details:{grant.id}",
                ),
            ])
        return InlineKeyboardMarkup(buttons)

    @staticmethod
    def digest_actions(grants_by_urgency: dict) -> InlineKeyboardMarkup:
        """Keyboard for daily digest notification."""
        buttons = []

        for level in ["urgent", "important"]:
            for grant in grants_by_urgency.get(level, [])[:3]:
                emoji = "🔴" if level == "urgent" else "🟡"
                buttons.append([
                    InlineKeyboardButton(
                        f"{emoji} {grant.title[:35]}...",
                        callback_data=f"details:{grant.id}",
                    ),
                ])

        if buttons:
            buttons.append([
                InlineKeyboardButton("📊 Full Pipeline", callback_data="pipeline:all"),
            ])

        return InlineKeyboardMarkup(buttons) if buttons else None

    @staticmethod
    def reminder_actions(grant_id: int) -> InlineKeyboardMarkup:
        """Keyboard for deadline reminder."""
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton("📋 Details", callback_data=f"details:{grant_id}"),
                InlineKeyboardButton("✍️ Draft", callback_data=f"draft:{grant_id}"),
            ],
            [
                InlineKeyboardButton("❌ Skip", callback_data=f"dismiss:{grant_id}"),
            ],
        ])
