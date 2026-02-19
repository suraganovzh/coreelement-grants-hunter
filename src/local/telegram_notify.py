"""Telegram push notifications (no 24/7 bot — just sends messages).

Lightweight notification system that sends grant summaries
to a Telegram chat. No polling, no always-on process.

Enhanced with winner analysis data and dashboard links.
"""

import os

import requests

from src.utils.logger import setup_logger
from src.utils.text_processor import TextProcessor

logger = setup_logger("telegram_notify")

DASHBOARD_URL = os.getenv(
    "DASHBOARD_URL",
    "https://suraganovzh.github.io/coreelement-grants-hunter",
)


def get_credentials() -> tuple[str, str]:
    """Load Telegram credentials from environment."""
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
    return token, chat_id


def send_message(text: str, parse_mode: str = "Markdown") -> bool:
    """Send a Telegram message.

    Args:
        text: Message text (Markdown or plain).
        parse_mode: 'Markdown' or 'HTML'.

    Returns:
        True if sent successfully.
    """
    token, chat_id = get_credentials()

    if not token or not chat_id:
        logger.warning("Telegram credentials not set (TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID)")
        print(f"[TELEGRAM] Would send:\n{text[:500]}")
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": True,
    }

    try:
        response = requests.post(url, json=data, timeout=10)
        if response.ok:
            logger.info("Telegram message sent (%d chars)", len(text))
            return True
        else:
            logger.error("Telegram API error: %s", response.text[:200])
            return False
    except Exception as e:
        logger.error("Failed to send Telegram message: %s", e)
        return False


def send_summary(copy_now: list[dict], test_first: list[dict]):
    """Send daily workflow summary with dashboard link."""
    total_potential = sum(g.get("amount_max", 0) for g in copy_now + test_first)
    potential_str = TextProcessor.format_currency(total_potential)

    total_winners = sum(
        len(g.get("analysis", {}).get("similar_winners", []))
        for g in copy_now + test_first
    )

    message = f"""📊 *Grant Hunter AI Daily Report*

🎯 *HIGH PRIORITY (copy\\_now):* {len(copy_now)}
⚡ *MEDIUM PRIORITY (test\\_first):* {len(test_first)}
💰 *Total Potential:* {potential_str}
🏆 *Similar Winners Found:* {total_winners}

{"─" * 30}
"""

    if copy_now:
        message += "\n*🎯 TOP GRANTS:*\n"
        for g in copy_now[:5]:
            analysis = g.get("analysis", {})
            win_prob = analysis.get("win_probability", 0)
            amount = TextProcessor.format_currency(g.get("amount_max"))
            winners = analysis.get("similar_winners", [])
            winner_text = f" | 🏆 {len(winners)} winners" if winners else ""
            message += f"\n• *{g.get('title', '')[:50]}*"
            message += f"\n  {g.get('funder', '')} | {amount}"
            message += f"\n  Win: {win_prob}% | Deadline: {g.get('deadline', 'TBD')}{winner_text}\n"

    if test_first:
        message += "\n*⚡ MEDIUM PRIORITY:*\n"
        for g in test_first[:3]:
            analysis = g.get("analysis", {})
            win_prob = analysis.get("win_probability", 0)
            message += f"\n• {g.get('title', '')[:50]}"
            message += f"\n  Win: {win_prob}% | {g.get('funder', '')}\n"

    message += f"\n[Open Dashboard]({DASHBOARD_URL})"

    send_message(message)


def send_priority_grants(grants: list[dict]):
    """Send detailed notification for each high-priority grant with winners."""
    for grant in grants:
        analysis = grant.get("analysis", {})
        success_factors = analysis.get("success_factors", {})
        risk_factors = analysis.get("risk_factors", [])
        winners = analysis.get("similar_winners", [])

        keywords = ", ".join(success_factors.get("keywords", []))
        risks = "\n".join(f"• {r}" for r in risk_factors[:3])
        amount_min = grant.get("amount_min", 0)
        amount_max = grant.get("amount_max", 0)
        grant_id = grant.get("id", "")

        message = f"""🎯 *HIGH-PRIORITY GRANT*

*{grant.get('title', '')}*

💰 Amount: ${amount_min:,} - ${amount_max:,}
🏛 Funder: {grant.get('funder', '')}
📅 Deadline: {grant.get('deadline', 'TBD')}

📊 *ANALYSIS:*
✅ Win Probability: {analysis.get('win_probability', 0)}%
✅ Pattern Match: {analysis.get('pattern_match_score', 0)}%

🔑 *Success Keywords:* {keywords}
"""

        if winners:
            message += f"\n🏆 *{len(winners)} SIMILAR WINNERS:*\n"
            for i, w in enumerate(winners[:3], 1):
                amt = TextProcessor.format_currency(w.get("amount"))
                year = w.get("year", "")
                year_str = f" ({year})" if year else ""
                reasons = ", ".join(w.get("match_reasons", [])[:2])
                message += f"\n{i}. *{w.get('company', 'Unknown')[:40]}*"
                message += f"\n   {w.get('funder', '')} | {amt}{year_str}"
                message += f"\n   Match: {reasons}\n"

        if risks:
            message += f"\n⚠️ *Risk Factors:*\n{risks}\n"

        message += f"\n{"─" * 30}\n"

        if winners:
            message += f"[View Winners]({DASHBOARD_URL}/winners.html?grant={grant_id}) | "
        message += f"[View Details]({DASHBOARD_URL}/grant.html?id={grant_id})"

        send_message(message)


def send_new_grants_alert(count: int, top_grant: dict | None = None):
    """Send alert about newly scraped grants."""
    message = f"""🔔 *New Grants Scraped*

{count} new grants found and ready for analysis.

"""
    if top_grant:
        message += f"""*Top match:*
• {top_grant.get('title', '')[:60]}
• {top_grant.get('funder', '')}
• ${top_grant.get('amount_max', 0):,}

"""

    message += f"[Open Dashboard]({DASHBOARD_URL})"
    send_message(message)


if __name__ == "__main__":
    # Test notification
    from dotenv import load_dotenv
    load_dotenv()

    send_message("🧪 *Test notification from Grant Hunter AI*\n\nSystem is working!")
    print("Test notification sent (check Telegram)")
