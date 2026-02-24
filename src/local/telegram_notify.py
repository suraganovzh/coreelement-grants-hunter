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


def send_urgent_grant_alert(grant: dict):
    """Send URGENT alert for grants with <7 day deadlines."""
    from src.utils.date_utils import DateUtils

    deadline = grant.get("deadline", "")
    days_left = DateUtils.days_until(deadline)
    if days_left is None:
        days_left = "?"

    currency = grant.get("currency", "USD")
    amount_min = grant.get("amount_min", 0)
    amount_max = grant.get("amount_max", 0)
    amount_str = TextProcessor.format_currency(amount_max or amount_min, currency)

    message = f"""🚨 *URGENT GRANT — {days_left} DAYS LEFT!*

*{grant.get('title', '')}*

💰 Amount: {amount_str}
📅 Deadline: *{deadline}*
🏛 Funder: {grant.get('funder', '')}
📂 Source: {grant.get('source_type', grant.get('source', 'unknown'))}
"""

    # Partnership info
    pathway = grant.get("eligibility_pathway", {})
    if pathway.get("partnership_path"):
        message += f"""
⚠️ *Partnership Required:*
Pathway: {pathway['partnership_path']}
Contact: {pathway.get('recommended_partner', 'TBD')}
"""

    urgency = grant.get("urgency", {})
    action = urgency.get("action_required", "immediate")
    message += f"""
⚡ *Action:* {action}

[Apply Now]({grant.get('url', '')})
[View Details]({DASHBOARD_URL})"""

    send_message(message)


def send_imminent_nofo_alert(grant: dict):
    """Alert for upcoming NOFOs (prepare now)."""
    currency = grant.get("currency", "USD")
    amount_max = grant.get("amount_max", 0)
    amount_str = TextProcessor.format_currency(amount_max, currency)
    expected = grant.get("expected_release", "TBD")

    message = f"""📢 *PREPARE NOW — NOFO Expected {expected}*

*{grant.get('title', '')}*

💰 Amount: Up to {amount_str}
📋 Status: {grant.get('status', 'Notice of Intent released')}
⏰ Expected: {expected}
"""

    steps = grant.get("preparation_steps", [])
    if steps:
        message += "\n*Start preparing:*\n"
        for i, step in enumerate(steps[:5], 1):
            message += f"{i}. {step}\n"

    message += f"\n[More Info]({grant.get('url', '')})"

    send_message(message)


def send_sbir_status_alert(status: dict):
    """Send SBIR/STTR status summary."""
    overall = status.get("overall_status", "UNKNOWN")

    if overall == "REAUTHORIZED":
        emoji = "🟢"
        action = "Programs reopened! Check for new solicitations."
    elif overall == "SUSPENDED":
        emoji = "🔴"
        action = "Programs suspended. Monitor for reauthorization."
    else:
        emoji = "🟡"
        action = "Status unclear. Check sbir.gov for updates."

    message = f"""{emoji} *SBIR/STTR Status: {overall}*

"""
    programs = status.get("programs", {})
    for key, prog in programs.items():
        accepting = "✅" if prog.get("accepting_apps") else "❌"
        message += f"{accepting} {key}: {prog.get('status', 'UNKNOWN')}\n"

    message += f"\n*Action:* {action}"
    message += f"\n\n[Open Dashboard]({DASHBOARD_URL})"

    send_message(message)


def send_daily_enhanced_report(grants: list[dict], sbir_status: dict | None = None):
    """Send enhanced daily report with all source types."""
    from src.utils.date_utils import DateUtils

    # Categorize grants
    urgent: list[dict] = []
    high_priority: list[dict] = []
    state_grants: list[dict] = []
    foundation_grants: list[dict] = []
    nofo_pipeline: list[dict] = []

    for g in grants:
        source_type = g.get("source_type", g.get("source", ""))
        urgency = g.get("urgency", {})
        priority = g.get("analysis", {}).get("priority", "")

        days = DateUtils.days_until(g.get("deadline", ""))
        if days is not None and 0 <= days <= 7:
            urgent.append(g)

        if priority == "copy_now":
            high_priority.append(g)
        if source_type == "state":
            state_grants.append(g)
        if source_type == "private_foundation":
            foundation_grants.append(g)
        if source_type == "nofo_pipeline":
            nofo_pipeline.append(g)

    total_potential = sum(g.get("amount_max", 0) for g in grants)
    potential_str = TextProcessor.format_currency(total_potential)

    message = f"""📊 *Grant Hunter AI — Enhanced Daily Report*

🎯 High Priority: {len(high_priority)}
🚨 Urgent (<7 days): {len(urgent)}
🏛 State Grants: {len(state_grants)}
🏦 Foundation Grants: {len(foundation_grants)}
📋 NOFO Pipeline: {len(nofo_pipeline)}
💰 Total Potential: {potential_str}
"""

    if sbir_status:
        overall = sbir_status.get("overall_status", "UNKNOWN")
        message += f"📌 SBIR/STTR: {overall}\n"

    message += f"\n{'─' * 30}\n"

    # Urgent grants
    if urgent:
        message += "\n🚨 *URGENT — ACT NOW:*\n"
        for g in urgent[:5]:
            days = DateUtils.days_until(g.get("deadline", ""))
            amount = TextProcessor.format_currency(g.get("amount_max"))
            message += f"\n• *{g.get('title', '')[:45]}*"
            message += f"\n  {g.get('funder', '')} | {amount} | {days}d left\n"

    # NOFO pipeline
    if nofo_pipeline:
        message += "\n📋 *PREPARE NOW — Upcoming NOFOs:*\n"
        for g in nofo_pipeline[:3]:
            amount = TextProcessor.format_currency(g.get("amount_max"))
            message += f"\n• {g.get('title', '')[:45]}"
            message += f"\n  {amount} | Expected: {g.get('expected_release', 'TBD')}\n"

    message += f"\n[Open Dashboard]({DASHBOARD_URL})"

    send_message(message)


if __name__ == "__main__":
    # Test notification
    from dotenv import load_dotenv
    load_dotenv()

    send_message("🧪 *Test notification from Grant Hunter AI*\n\nSystem is working!")
    print("Test notification sent (check Telegram)")
