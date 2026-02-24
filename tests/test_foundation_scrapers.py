"""Tests for foundation grant scrapers."""

import pytest
from unittest.mock import patch, MagicMock

from src.scrapers.foundations.eqt_foundation import EQTFoundationScraper
from src.scrapers.foundations.sloan_foundation import SloanFoundationScraper


class TestEQTFoundationScraper:
    def test_scraper_name(self):
        scraper = EQTFoundationScraper()
        assert scraper.name == "eqt_foundation"

    def test_known_active_programs(self):
        scraper = EQTFoundationScraper()
        known = scraper._known_active_programs()
        assert len(known) > 0
        assert known[0].funder == "EQT Foundation"
        assert known[0].currency == "EUR"

    def test_eqt_grants_have_focus_areas(self):
        scraper = EQTFoundationScraper()
        known = scraper._known_active_programs()
        for g in known:
            assert len(g.industry_tags) > 0
            assert "critical minerals" in g.industry_tags

    def test_eqt_amounts(self):
        scraper = EQTFoundationScraper()
        known = scraper._known_active_programs()
        for g in known:
            assert g.amount_min == 25000
            assert g.amount_max == 100000

    @patch.object(EQTFoundationScraper, '_fetch')
    def test_search_returns_known_even_on_error(self, mock_fetch):
        mock_fetch.side_effect = Exception("Error")
        scraper = EQTFoundationScraper()
        results = scraper.search()
        assert len(results) > 0  # Known programs should still be returned


class TestSloanFoundationScraper:
    def test_scraper_name(self):
        scraper = SloanFoundationScraper()
        assert scraper.name == "sloan_foundation"

    def test_known_active_programs(self):
        scraper = SloanFoundationScraper()
        known = scraper._known_active_programs()
        assert len(known) > 0
        assert known[0].funder == "Alfred P. Sloan Foundation"
        assert known[0].currency == "USD"

    @patch.object(SloanFoundationScraper, '_fetch')
    def test_search_handles_error(self, mock_fetch):
        mock_fetch.side_effect = Exception("Error")
        scraper = SloanFoundationScraper()
        results = scraper.search()
        assert len(results) > 0
