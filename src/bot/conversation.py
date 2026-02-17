"""Conversation flows for multi-step bot interactions."""

from telegram import Update
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

from src.utils.logger import setup_logger

logger = setup_logger("conversation")

# Conversation states
AWAITING_KEYWORD = 0
AWAITING_NOTE = 1
AWAITING_FEEDBACK = 2


async def search_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start interactive search conversation."""
    await update.message.reply_text(
        "🔍 Interactive Search\n\n"
        "Enter keywords to search for grants.\n"
        "Examples: 'lithium AI', 'critical minerals DOE', 'mining innovation'\n\n"
        "Send /cancel to stop."
    )
    return AWAITING_KEYWORD


async def search_keyword(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Process search keyword from conversation."""
    keyword = update.message.text

    from src.database.queries import GrantQueries
    db = GrantQueries()
    try:
        grants = db.search_grants(keyword)
        if grants:
            lines = [f"Found {len(grants)} grants for '{keyword}':\n"]
            for g in grants[:5]:
                lines.append(f"  [{g.id}] {g.title[:55]}")
                lines.append(f"      Fit: {g.fit_score}% | /details {g.id}")
            lines.append("\nEnter another keyword or /cancel to stop.")
            await update.message.reply_text("\n".join(lines))
        else:
            await update.message.reply_text(f"No results for '{keyword}'. Try different keywords or /cancel.")
    finally:
        db.close()

    return AWAITING_KEYWORD


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel conversation."""
    await update.message.reply_text("Search cancelled.")
    return ConversationHandler.END


def get_search_conversation() -> ConversationHandler:
    """Build the search conversation handler."""
    return ConversationHandler(
        entry_points=[CommandHandler("isearch", search_start)],
        states={
            AWAITING_KEYWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, search_keyword)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
