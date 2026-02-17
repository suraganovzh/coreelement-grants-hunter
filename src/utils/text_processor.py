"""Text processing utilities for grant data."""

import re
import html
from typing import Any


class TextProcessor:
    """Utilities for cleaning and processing grant text data."""

    @staticmethod
    def clean_html(text: str) -> str:
        """Remove HTML tags and decode entities."""
        text = html.unescape(text)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    @staticmethod
    def extract_amount(text: str) -> tuple[int | None, int | None, str]:
        """Extract funding amount range from text.

        Returns:
            Tuple of (min_amount, max_amount, currency).
        """
        currency = "USD"
        if "€" in text or "EUR" in text:
            currency = "EUR"
        elif "£" in text or "GBP" in text:
            currency = "GBP"
        elif "CAD" in text:
            currency = "CAD"
        elif "AUD" in text:
            currency = "AUD"

        # Match patterns like "$50,000 - $150,000" or "up to $1M" or "$500K"
        amounts: list[int] = []

        # Millions
        for match in re.finditer(r"[\$€£]?\s*([\d,.]+)\s*[Mm](?:illion)?", text):
            val = float(match.group(1).replace(",", ""))
            amounts.append(int(val * 1_000_000))

        # Thousands with K
        for match in re.finditer(r"[\$€£]?\s*([\d,.]+)\s*[Kk]", text):
            val = float(match.group(1).replace(",", ""))
            amounts.append(int(val * 1_000))

        # Plain numbers with currency
        for match in re.finditer(r"[\$€£]\s*([\d,]+(?:\.\d{2})?)", text):
            val = float(match.group(1).replace(",", ""))
            if val >= 1000:
                amounts.append(int(val))

        if not amounts:
            return None, None, currency

        amounts.sort()
        if len(amounts) == 1:
            return amounts[0], amounts[0], currency
        return amounts[0], amounts[-1], currency

    @staticmethod
    def extract_deadline(text: str) -> str | None:
        """Extract deadline date string from text."""
        patterns = [
            r"[Dd]eadline[:\s]+(\w+ \d{1,2},?\s*\d{4})",
            r"[Dd]ue [Dd]ate[:\s]+(\w+ \d{1,2},?\s*\d{4})",
            r"[Cc]losing [Dd]ate[:\s]+(\w+ \d{1,2},?\s*\d{4})",
            r"[Ss]ubmission [Dd]eadline[:\s]+(\w+ \d{1,2},?\s*\d{4})",
            r"(\d{1,2}/\d{1,2}/\d{4})",
            r"(\d{4}-\d{2}-\d{2})",
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1)
        return None

    @staticmethod
    def extract_eligibility_keywords(text: str) -> list[str]:
        """Extract eligibility-related keywords from text."""
        keywords: list[str] = []
        lower = text.lower()

        eligibility_markers = {
            "for-profit": "For-Profit",
            "nonprofit": "Non-Profit",
            "non-profit": "Non-Profit",
            "501(c)(3)": "501(c)(3)",
            "small business": "Small Business",
            "s-corp": "S-Corp",
            "c-corp": "C-Corp",
            "university": "University",
            "academic": "Academic",
            "government": "Government",
            "tribal": "Tribal",
            "minority": "Minority-Owned",
            "woman-owned": "Woman-Owned",
            "veteran": "Veteran-Owned",
            "hubzone": "HUBZone",
            "us-based": "US-Based",
            "domestic": "Domestic",
            "international": "International",
        }

        for marker, label in eligibility_markers.items():
            if marker in lower:
                keywords.append(label)

        return keywords

    @staticmethod
    def truncate(text: str, max_length: int = 4000, suffix: str = "...") -> str:
        """Truncate text to max_length preserving word boundaries."""
        if len(text) <= max_length:
            return text
        truncated = text[: max_length - len(suffix)]
        last_space = truncated.rfind(" ")
        if last_space > max_length * 0.8:
            truncated = truncated[:last_space]
        return truncated + suffix

    @staticmethod
    def keyword_match_score(text: str, keywords: list[str]) -> float:
        """Calculate keyword match score (0.0-1.0).

        Args:
            text: Text to search.
            keywords: Keywords to look for.

        Returns:
            Fraction of keywords found in text.
        """
        if not keywords:
            return 0.0
        lower = text.lower()
        matched = sum(1 for kw in keywords if kw.lower() in lower)
        return matched / len(keywords)

    @staticmethod
    def format_currency(amount: int | None, currency: str = "USD") -> str:
        """Format amount as currency string."""
        if amount is None:
            return "N/A"
        symbols = {"USD": "$", "EUR": "€", "GBP": "£", "CAD": "C$", "AUD": "A$"}
        symbol = symbols.get(currency, currency + " ")
        if amount >= 1_000_000:
            return f"{symbol}{amount / 1_000_000:.1f}M"
        if amount >= 1_000:
            return f"{symbol}{amount / 1_000:.0f}K"
        return f"{symbol}{amount:,}"

    @staticmethod
    def extract_json_from_text(text: str) -> dict[str, Any] | None:
        """Extract first JSON object from text that may contain other content."""
        import json
        # Try direct parse first
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        # Try to find JSON in the text
        match = re.search(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
        return None
