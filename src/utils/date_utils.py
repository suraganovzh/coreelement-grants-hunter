"""Date utilities for deadline management."""

from datetime import datetime, date, timedelta

from dateutil import parser as date_parser

from src.utils.logger import setup_logger

logger = setup_logger("date_utils")


class DateUtils:
    """Utilities for date parsing and deadline calculations."""

    @staticmethod
    def parse_date(date_str: str) -> date | None:
        """Parse various date formats to a date object."""
        if not date_str:
            return None
        try:
            return date_parser.parse(date_str, fuzzy=True).date()
        except (ValueError, TypeError):
            logger.debug("Could not parse date: %s", date_str)
            return None

    @staticmethod
    def days_until(target: date | str) -> int | None:
        """Calculate days until a target date.

        Args:
            target: Target date or date string.

        Returns:
            Number of days (negative if past), or None if unparseable.
        """
        if isinstance(target, str):
            target = DateUtils.parse_date(target)
        if target is None:
            return None
        return (target - date.today()).days

    @staticmethod
    def urgency_level(deadline: date | str) -> str:
        """Determine urgency level based on deadline.

        Returns:
            'expired', 'urgent', 'important', or 'planning'.
        """
        days = DateUtils.days_until(deadline)
        if days is None:
            return "planning"
        if days < 0:
            return "expired"
        if days <= 7:
            return "urgent"
        if days <= 30:
            return "important"
        return "planning"

    @staticmethod
    def urgency_emoji(deadline: date | str) -> str:
        """Get emoji for urgency level."""
        level = DateUtils.urgency_level(deadline)
        return {
            "expired": "⚫",
            "urgent": "🔴",
            "important": "🟡",
            "planning": "🟢",
        }.get(level, "⚪")

    @staticmethod
    def format_deadline(deadline: date | str) -> str:
        """Format deadline with days remaining."""
        if isinstance(deadline, str):
            deadline = DateUtils.parse_date(deadline)
        if deadline is None:
            return "No deadline"

        days = (deadline - date.today()).days
        date_str = deadline.strftime("%b %d, %Y")

        if days < 0:
            return f"{date_str} (EXPIRED {abs(days)} days ago)"
        if days == 0:
            return f"{date_str} (TODAY!)"
        if days == 1:
            return f"{date_str} (TOMORROW!)"
        if days <= 7:
            return f"{date_str} ({days} days left - URGENT)"
        if days <= 30:
            return f"{date_str} ({days} days left)"
        return f"{date_str} ({days} days left)"

    @staticmethod
    def should_remind(deadline: date, reminder_days: list[int] | None = None) -> str | None:
        """Check if a reminder should be sent today.

        Args:
            deadline: The deadline date.
            reminder_days: Days before deadline to remind. Default: [14, 7, 3, 1].

        Returns:
            Reminder message if today is a reminder day, None otherwise.
        """
        if reminder_days is None:
            reminder_days = [14, 7, 3, 1]

        days = (deadline - date.today()).days

        if days not in reminder_days:
            return None

        messages = {
            14: "Time to start preparing your application",
            7: "URGENT! One week until deadline",
            3: "CRITICAL! Only 3 days remaining",
            1: "LAST DAY! Deadline is tomorrow",
        }

        return messages.get(days, f"{days} days until deadline")

    @staticmethod
    def estimated_start_date(deadline: date, prep_hours: int) -> date:
        """Calculate recommended start date based on prep hours.

        Assumes 4 productive hours per day on grant applications.
        """
        prep_days = max(1, (prep_hours + 3) // 4)  # Ceiling division by 4
        buffer_days = max(2, prep_days // 3)  # 33% buffer
        return deadline - timedelta(days=prep_days + buffer_days)

    @staticmethod
    def is_within_range(
        deadline: date | str,
        min_days: int = 3,
        max_days: int = 365,
    ) -> bool:
        """Check if deadline is within acceptable range."""
        days = DateUtils.days_until(deadline)
        if days is None:
            return True  # Allow grants with no clear deadline
        return min_days <= days <= max_days
