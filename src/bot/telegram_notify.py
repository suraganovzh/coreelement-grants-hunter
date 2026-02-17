"""Re-export from src.local.telegram_notify for convenience.

The lightweight push-notification module lives in src/local/ because it is
called by the local daily workflow.  This re-export makes it accessible from
src/bot/ as well, matching the project structure spec.
"""

from src.local.telegram_notify import (
    get_credentials,
    send_message,
    send_summary,
    send_priority_grants,
    send_new_grants_alert,
)

__all__ = [
    "get_credentials",
    "send_message",
    "send_summary",
    "send_priority_grants",
    "send_new_grants_alert",
]
