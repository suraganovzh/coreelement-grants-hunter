"""Telegram push notifications (no 24/7 bot — just sends messages).

Lightweight notification system that sends grant summaries
to a Telegram chat. No polling, no always-on process.
"""

import os

import requests

from src.utils.logger import setup_logger
from src.utils.text_processor import TextProcessor

logger = setup_logger("telegram_notify")


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
    """Send daily workflow summary."""
    total_potential = sum(g.get("amount_max", 0) for g in copy_now + test_first)
    potential_str = TextProcessor.format_currency(total_potential)

    message = f"""📊 *Grant Hunter AI Daily Report*

🎯 *HIGH PRIORITY (copy\\_now):* {len(copy_now)}
⚡ *MEDIUM PRIORITY (test\\_first):* {len(test_first)}
💰 *Total Potential:* {potential_str}

{"─" * 30}
"""

    if copy_now:
        message += "\n*🎯 TOP GRANTS:*\n"
        for g in copy_now[:5]:
            analysis = g.get("analysis", {})
            win_prob = analysis.get("win_probability", 0)
            amount = TextProcessor.format_currency(g.get("amount_max"))
            message += f"\n• *{g.get('title', '')[:50]}*"
            message += f"\n  {g.get('funder', '')} | {amount}"
            message += f"\n  Win: {win_prob}% | Deadline: {g.get('deadline', 'TBD')}\n"

    if test_first:
        message += "\n*⚡ MEDIUM PRIORITY:*\n"
        for g in test_first[:3]:
            analysis = g.get("analysis", {})
            win_prob = analysis.get("win_probability", 0)
            message += f"\n• {g.get('title', '')[:50]}"
            message += f"\n  Win: {win_prob}% | {g.get('funder', '')}\n"

    send_message(message)


def send_priority_grants(grants: list[dict]):
    """Send detailed notification for each high-priority grant."""
    for grant in grants:
        analysis = grant.get("analysis", {})
        success_factors = analysis.get("success_factors", {})
        risk_factors = analysis.get("risk_factors", [])

        keywords = ", ".join(success_factors.get("keywords", []))
        risks = "\n".join(f"• {r}" for r in risk_factors[:3])
        amount_min = grant.get("amount_min", 0)
        amount_max = grant.get("amount_max", 0)

        message = f"""🎯 *HIGH-PRIORITY GRANT*

*{grant.get('title', '')}*

💰 Amount: ${amount_min:,} - ${amount_max:,}
🏛 Funder: {grant.get('funder', '')}
📅 Deadline: {grant.get('deadline', 'TBD')}

📊 *ANALYSIS:*
✅ Win Probability: {analysis.get('win_probability', 0)}%
✅ Pattern Match: {analysis.get('pattern_match_score', 0)}%

🔑 *Success Keywords:* {keywords}

⚠️ *Risk Factors:*
{risks}

{"─" * 30}

💡 _Run: python src/local/generate.py --grant-id {grant.get('id', '')} to create draft_"""

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

    message += "_Run daily\\_workflow.py to process_"
    send_message(message)


if __name__ == "__main__":
    # Test notification
    from dotenv import load_dotenv
    load_dotenv()

    send_message("🧪 *Test notification from Grant Hunter AI*\n\nSystem is working!")
    print("Test notification sent (check Telegram)")
