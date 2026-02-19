"""
GitHub Actions Telegram Notifications
Sends push notifications without requiring 24/7 bot process.
"""
import json
import os
import requests
from datetime import datetime, timedelta
from pathlib import Path

BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')
DASHBOARD_URL = os.environ.get('DASHBOARD_URL', 'https://suraganovzh.github.io/coreelement-grants-hunter')


def send_message(text, parse_mode='Markdown', reply_markup=None):
    """Send message via Telegram Bot API."""
    if not BOT_TOKEN or not CHAT_ID:
        print("⚠️ Telegram credentials not set")
        return False

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    data = {
        'chat_id': CHAT_ID,
        'text': text,
        'parse_mode': parse_mode,
        'disable_web_page_preview': False
    }

    if reply_markup:
        data['reply_markup'] = json.dumps(reply_markup)

    try:
        response = requests.post(url, json=data, timeout=10)
        response.raise_for_status()
        return True
    except Exception as e:
        print(f"❌ Error sending message: {e}")
        return False


def load_grants():
    """Load analyzed grants."""
    try:
        with open('data/analyzed.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
            if isinstance(data, dict):
                return data.get('grants', [])
            return data
    except FileNotFoundError:
        print("⚠️ data/analyzed.json not found")
        return []
    except json.JSONDecodeError:
        print("⚠️ Invalid JSON in analyzed.json")
        return []


def days_until(deadline_str):
    """Calculate days until deadline."""
    if not deadline_str:
        return 999
    try:
        from dateutil import parser as dp
        deadline = dp.parse(deadline_str)
        today = datetime.now(deadline.tzinfo)
        return (deadline - today).days
    except Exception:
        return 999


def format_money(amount):
    """Format money amount."""
    if not amount:
        return "$0"
    if amount >= 1_000_000:
        return f"${amount/1_000_000:.1f}M"
    if amount >= 1_000:
        return f"${amount/1_000:.0f}K"
    return f"${amount}"


def get_new_high_priority_grants(grants):
    """Find new copy_now grants from last 24 hours."""
    cutoff = datetime.now() - timedelta(hours=24)

    new_grants = []
    for grant in grants:
        if grant.get('analysis', {}).get('priority') != 'copy_now':
            continue

        found_date = grant.get('analysis', {}).get('found_date')
        if found_date:
            try:
                from dateutil import parser as dp
                found = dp.parse(found_date)
                if found.replace(tzinfo=None) > cutoff:
                    new_grants.append(grant)
            except Exception:
                pass

    return new_grants


def get_urgent_grants(grants):
    """Find grants with <7 days until deadline."""
    urgent = []
    for grant in grants:
        days = days_until(grant.get('deadline'))
        if 0 <= days <= 7:
            urgent.append(grant)

    urgent.sort(key=lambda g: days_until(g.get('deadline')))
    return urgent


def send_daily_digest(grants):
    """Send daily summary."""
    copy_now = [g for g in grants if g.get('analysis', {}).get('priority') == 'copy_now']
    test_first = [g for g in grants if g.get('analysis', {}).get('priority') == 'test_first']
    urgent = get_urgent_grants(grants)

    total_potential = sum(g.get('amount_max', 0) for g in copy_now + test_first)

    message = f"""☀️ *GRANT HUNTER DAILY DIGEST*

📊 *Pipeline Overview:*
- 🎯 High Priority: {len(copy_now)}
- ⚡ Medium Priority: {len(test_first)}
- 💰 Total Potential: {format_money(total_potential)}
- 🔥 Urgent (<7 days): {len(urgent)}

"""

    if urgent:
        message += "⚠️ *URGENT DEADLINES:*\n"
        for grant in urgent[:3]:
            days = days_until(grant.get('deadline'))
            message += f"• {grant.get('title', '')[:40]}... - *{days} days*\n"
        message += "\n"

    message += f"[📊 Open Dashboard]({DASHBOARD_URL})"

    send_message(message)


def send_new_grant_notification(grant):
    """Send notification about new high-priority grant."""
    analysis = grant.get('analysis', {})
    winners = analysis.get('similar_winners', [])
    days = days_until(grant.get('deadline'))

    urgency_emoji = "🔴" if days <= 7 else "🟡" if days <= 14 else "🟢"

    message = f"""{urgency_emoji} *NEW HIGH-PRIORITY GRANT*

*{grant.get('title', '')}*

💰 Amount: {format_money(grant.get('amount_min', 0))} - {format_money(grant.get('amount_max', 0))}
📅 Deadline: {grant.get('deadline', 'TBD')} ({days} days)
🏛 Funder: {grant.get('funder', 'Unknown')}

📊 *Success Analysis:*
✅ Win Probability: {analysis.get('win_probability', 0)}%
✅ Pattern Match: {analysis.get('pattern_match_score', 0)}%
"""

    if winners:
        message += f"\n🏆 *{len(winners)} Similar Winners Found:*\n"
        for i, winner in enumerate(winners[:3], 1):
            message += f"{i}. *{winner.get('company', 'Unknown')}* → {format_money(winner.get('amount', 0))} ({winner.get('year', 'N/A')})\n"
            match_reasons = ', '.join(winner.get('match_reasons', [])[:2])
            message += f"   {winner.get('funder', '')} • Match: {match_reasons}\n"
    else:
        message += "\n⚠️ No similar winners found - higher risk\n"

    grant_id = grant.get('id', '')
    message += f"\n[📋 View Full Details]({DASHBOARD_URL}/grant.html?id={grant_id})"

    keyboard = {
        'inline_keyboard': [
            [
                {'text': '📊 Open Dashboard', 'url': DASHBOARD_URL},
                {'text': '🏆 View Winners', 'url': f"{DASHBOARD_URL}/winners.html?grant={grant_id}"}
            ]
        ]
    }

    send_message(message, reply_markup=keyboard)


def send_deadline_reminder(grant, days_left):
    """Send deadline reminder."""
    if days_left == 1:
        emoji = "🚨"
        urgency = "FINAL DAY"
    elif days_left <= 3:
        emoji = "🔴"
        urgency = "CRITICAL"
    elif days_left <= 7:
        emoji = "🟡"
        urgency = "URGENT"
    else:
        emoji = "🟢"
        urgency = "REMINDER"

    status = grant.get('status', 'inbox')
    progress = grant.get('progress', {}).get('percentage', 0)

    message = f"""{emoji} *DEADLINE {urgency}*

*{grant.get('title', '')}*

⏰ *{days_left} days left* until {grant.get('deadline')}
📊 Status: {status.upper()} ({progress}% complete)
💰 Amount: {format_money(grant.get('amount_max', 0))}

"""

    if status == 'inbox':
        message += "❌ *Not started yet!* Time to begin.\n"
    elif status == 'drafting' and progress < 50:
        message += f"⚠️ *Only {progress}% done.* Need to accelerate.\n"
    elif status == 'drafting' and progress < 90:
        message += "📝 *Almost there!* Final push needed.\n"
    elif status == 'review':
        message += "👀 *In review.* Ready to submit?\n"

    grant_id = grant.get('id', '')
    message += f"\n[📋 Open Grant]({DASHBOARD_URL}/grant.html?id={grant_id})\n"

    send_message(message)


def main():
    """Main notification logic."""
    print("🤖 Starting Telegram notifications...")

    grants = load_grants()
    if not grants:
        print("No grants to process")
        return

    print(f"Loaded {len(grants)} grants")

    # 1. Check for new high-priority grants
    new_grants = get_new_high_priority_grants(grants)
    if new_grants:
        print(f"📬 Sending {len(new_grants)} new grant notifications...")
        for grant in new_grants:
            send_new_grant_notification(grant)

    # 2. Check for urgent deadlines
    urgent = get_urgent_grants(grants)
    if urgent:
        print(f"⏰ Sending {len(urgent)} deadline reminders...")
        for grant in urgent:
            days = days_until(grant.get('deadline'))
            if days in [7, 3, 1]:
                send_deadline_reminder(grant, days)

    # 3. Send daily digest (if scheduled or manual)
    if os.environ.get('GITHUB_EVENT_NAME') in ('schedule', 'workflow_dispatch'):
        print("📊 Sending daily digest...")
        send_daily_digest(grants)

    print("✅ Notifications sent successfully")


if __name__ == '__main__':
    main()
