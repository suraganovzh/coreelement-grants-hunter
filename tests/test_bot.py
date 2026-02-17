"""Tests for Telegram bot utilities."""

import pytest
from datetime import date, timedelta

from src.utils.text_processor import TextProcessor
from src.utils.date_utils import DateUtils


class TestTextProcessor:
    def test_clean_html(self):
        result = TextProcessor.clean_html("<p>Hello <b>world</b></p>")
        assert result == "Hello world"

    def test_extract_amount_usd(self):
        min_a, max_a, cur = TextProcessor.extract_amount("Award: $50,000 - $150,000")
        assert min_a == 50000
        assert max_a == 150000
        assert cur == "USD"

    def test_extract_amount_millions(self):
        min_a, max_a, cur = TextProcessor.extract_amount("Up to $2M in funding")
        assert max_a == 2000000

    def test_extract_amount_euros(self):
        min_a, max_a, cur = TextProcessor.extract_amount("€500K to €1M available")
        assert cur == "EUR"
        assert min_a == 500000
        assert max_a == 1000000

    def test_extract_amount_none(self):
        min_a, max_a, cur = TextProcessor.extract_amount("No amount specified")
        assert min_a is None
        assert max_a is None

    def test_format_currency(self):
        assert TextProcessor.format_currency(1500000) == "$1.5M"
        assert TextProcessor.format_currency(250000) == "$250K"
        assert TextProcessor.format_currency(None) == "N/A"
        assert TextProcessor.format_currency(500000, "EUR") == "€500K"

    def test_keyword_match_score(self):
        text = "AI for mining and mineral exploration using machine learning"
        keywords = ["AI", "mining", "exploration", "robotics"]
        score = TextProcessor.keyword_match_score(text, keywords)
        assert 0.5 < score < 1.0  # 3 out of 4 match

    def test_keyword_match_score_empty(self):
        score = TextProcessor.keyword_match_score("some text", [])
        assert score == 0.0

    def test_extract_eligibility_keywords(self):
        text = "Open to small business concerns and for-profit organizations"
        keywords = TextProcessor.extract_eligibility_keywords(text)
        assert "Small Business" in keywords
        assert "For-Profit" in keywords

    def test_truncate(self):
        text = "a " * 100
        result = TextProcessor.truncate(text, 20)
        assert len(result) <= 23  # 20 + "..."
        assert result.endswith("...")


class TestDateUtils:
    def test_days_until_future(self):
        future = date.today() + timedelta(days=10)
        assert DateUtils.days_until(future) == 10

    def test_days_until_past(self):
        past = date.today() - timedelta(days=5)
        assert DateUtils.days_until(past) == -5

    def test_urgency_level(self):
        assert DateUtils.urgency_level(date.today() + timedelta(days=3)) == "urgent"
        assert DateUtils.urgency_level(date.today() + timedelta(days=15)) == "important"
        assert DateUtils.urgency_level(date.today() + timedelta(days=60)) == "planning"
        assert DateUtils.urgency_level(date.today() - timedelta(days=1)) == "expired"

    def test_urgency_emoji(self):
        assert DateUtils.urgency_emoji(date.today() + timedelta(days=3)) == "🔴"
        assert DateUtils.urgency_emoji(date.today() + timedelta(days=15)) == "🟡"
        assert DateUtils.urgency_emoji(date.today() + timedelta(days=60)) == "🟢"

    def test_format_deadline(self):
        tomorrow = date.today() + timedelta(days=1)
        result = DateUtils.format_deadline(tomorrow)
        assert "TOMORROW" in result

    def test_should_remind(self):
        deadline_7 = date.today() + timedelta(days=7)
        msg = DateUtils.should_remind(deadline_7)
        assert msg is not None
        assert "URGENT" in msg

        deadline_10 = date.today() + timedelta(days=10)
        msg = DateUtils.should_remind(deadline_10)
        assert msg is None  # 10 is not in [14, 7, 3, 1]

    def test_is_within_range(self):
        assert DateUtils.is_within_range(date.today() + timedelta(days=30))
        assert not DateUtils.is_within_range(date.today() + timedelta(days=1), min_days=3)
        assert not DateUtils.is_within_range(date.today() + timedelta(days=400), max_days=365)

    def test_estimated_start_date(self):
        deadline = date.today() + timedelta(days=30)
        start = DateUtils.estimated_start_date(deadline, prep_hours=20)
        assert start < deadline
        assert start > date.today() - timedelta(days=1)

    def test_parse_date(self):
        assert DateUtils.parse_date("2026-03-15") == date(2026, 3, 15)
        assert DateUtils.parse_date("March 15, 2026") == date(2026, 3, 15)
        assert DateUtils.parse_date("invalid") is None
        assert DateUtils.parse_date("") is None
