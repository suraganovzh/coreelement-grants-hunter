"""Main Telegram bot — Core Element Grant Hunter."""

import os

from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
)

from src.bot.handlers import BotHandlers
from src.bot.notifications import NotificationService
from src.utils.logger import setup_logger

logger = setup_logger("telegram_bot")


class GrantHunterBot:
    """Core Element Grant Hunter Telegram Bot.

    Provides daily grant notifications, interactive commands,
    and application management through Telegram.
    """

    def __init__(self):
        self.token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
        self.handlers = BotHandlers()
        self.notifications = NotificationService(self.chat_id)

    def build_app(self):
        """Build and configure the Telegram application."""
        if not self.token:
            raise ValueError("TELEGRAM_BOT_TOKEN not set")

        app = ApplicationBuilder().token(self.token).build()

        # Register command handlers
        app.add_handler(CommandHandler("start", self.handlers.cmd_start))
        app.add_handler(CommandHandler("help", self.handlers.cmd_help))
        app.add_handler(CommandHandler("status", self.handlers.cmd_status))
        app.add_handler(CommandHandler("urgent", self.handlers.cmd_urgent))
        app.add_handler(CommandHandler("pipeline", self.handlers.cmd_pipeline))
        app.add_handler(CommandHandler("search", self.handlers.cmd_search))
        app.add_handler(CommandHandler("details", self.handlers.cmd_details))
        app.add_handler(CommandHandler("fit", self.handlers.cmd_fit))
        app.add_handler(CommandHandler("similar", self.handlers.cmd_similar))
        app.add_handler(CommandHandler("stats", self.handlers.cmd_stats))
        app.add_handler(CommandHandler("settings", self.handlers.cmd_settings))
        app.add_handler(CommandHandler("draft", self.handlers.cmd_draft))

        # Register callback query handler for inline buttons
        app.add_handler(CallbackQueryHandler(self.handlers.handle_callback))

        logger.info("Bot configured with all handlers")
        return app

    def run(self):
        """Start the bot in polling mode."""
        logger.info("Starting Grant Hunter Bot...")
        app = self.build_app()
        app.run_polling(drop_pending_updates=True)

    async def send_daily_digest(self, app=None):
        """Send daily grant digest. Called by scheduler."""
        if app is None:
            app = self.build_app()
        await self.notifications.send_daily_digest(app.bot)

    async def send_deadline_reminders(self, app=None):
        """Send deadline reminders. Called by scheduler."""
        if app is None:
            app = self.build_app()
        await self.notifications.send_deadline_reminders(app.bot)


def main():
    """Entry point for the Telegram bot."""
    from dotenv import load_dotenv
    load_dotenv()

    bot = GrantHunterBot()
    bot.run()


if __name__ == "__main__":
    main()
