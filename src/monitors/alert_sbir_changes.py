"""Alert on SBIR/STTR status changes via Telegram.

Run after sbir_status check to send Telegram alert if status changed.
"""

import json
import sys

from src.local.telegram_notify import send_message
from src.monitors.sbir_status import SBIRStatusMonitor
from src.utils.logger import setup_logger

logger = setup_logger("alert_sbir")


def main():
    monitor = SBIRStatusMonitor()

    # Check for changes
    changes = monitor.check_for_changes("data/sbir_status.json")

    if changes and changes.get("changed"):
        if changes.get("reauthorized"):
            message = """🚨 *SBIR/STTR REAUTHORIZED!*

Programs are accepting applications again!

📋 *Status Change:*
Previous: {prev}
Current: *{curr}*

⚡ *Action Required:*
1. Review open solicitations
2. Prepare Phase I application for DOE/NSF
3. Check agency-specific deadlines

This is a major opportunity for Core Element AI!""".format(
                prev=changes["previous_status"],
                curr=changes["new_status"],
            )
        else:
            message = """📢 *SBIR/STTR Status Update*

Status changed: {prev} → *{curr}*

{msg}

Monitor for further updates.""".format(
                prev=changes["previous_status"],
                curr=changes["new_status"],
                msg=changes.get("message", ""),
            )

        send_message(message)
        print("Alert sent via Telegram")
    else:
        print("No SBIR status changes — no alert needed")

    # Save current status
    status = monitor.check_status()
    with open("data/sbir_status.json", "w") as f:
        json.dump(status, f, indent=2)

    monitor.close()


if __name__ == "__main__":
    main()
