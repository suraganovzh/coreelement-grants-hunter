"""Tests for state-level grant scrapers."""

import pytest
from unittest.mock import patch, MagicMock

from src.scrapers.state_grants.colorado_scraper import ColoradoScraper
from src.scrapers.state_grants.delaware_scraper import DelawareScraper
from src.scrapers.state_grants.multi_state import MultiStateScraper, PRIORITY_STATES


class TestColoradoScraper:
    def test_scraper_name(self):
        scraper = ColoradoScraper()
        assert scraper.name == "colorado_state"

    def test_known_active_programs(self):
        scraper = ColoradoScraper()
        known = scraper._known_active_programs()
        assert len(known) > 0
        assert any("Proof of Concept" in g.title for g in known)
        assert any("Advanced Industries" in g.title for g in known)

    def test_known_programs_have_amounts(self):
        scraper = ColoradoScraper()
        known = scraper._known_active_programs()
        for g in known:
            assert g.amount_max is not None
            assert g.amount_max > 0
            assert g.funder == "Colorado OEDIT"

    @patch.object(ColoradoScraper, '_fetch')
    def test_search_handles_error(self, mock_fetch):
        mock_fetch.side_effect = Exception("Connection error")
        scraper = ColoradoScraper()
        results = scraper.search()
        # Should still return known active programs even if scraping fails
        assert len(results) > 0

    def test_known_programs_eligibility(self):
        scraper = ColoradoScraper()
        known = scraper._known_active_programs()
        for g in known:
            assert g.eligibility_text
            assert "Colorado" in g.eligibility_text


class TestDelawareScraper:
    def test_scraper_name(self):
        scraper = DelawareScraper()
        assert scraper.name == "delaware_state"

    def test_known_active_programs(self):
        scraper = DelawareScraper()
        known = scraper._known_active_programs()
        assert len(known) > 0
        assert any("EDGE" in g.title for g in known)

    def test_known_programs_source(self):
        scraper = DelawareScraper()
        known = scraper._known_active_programs()
        for g in known:
            assert g.source == "delaware_state"
            assert g.grant_type == "state"

    @patch.object(DelawareScraper, '_fetch')
    def test_search_handles_error(self, mock_fetch):
        mock_fetch.side_effect = Exception("Connection error")
        scraper = DelawareScraper()
        results = scraper.search()
        assert len(results) > 0


class TestMultiStateScraper:
    def test_scraper_name(self):
        scraper = MultiStateScraper()
        assert scraper.name == "multi_state"

    def test_priority_states_count(self):
        assert len(PRIORITY_STATES) == 7

    def test_priority_states_have_required_fields(self):
        for state in PRIORITY_STATES:
            assert "state" in state
            assert "office" in state
            assert "urls" in state
            assert len(state["urls"]) > 0
            assert "focus" in state

    def test_priority_states_include_key_states(self):
        state_names = [s["state"] for s in PRIORITY_STATES]
        assert "Colorado" in state_names
        assert "Delaware" in state_names
        assert "Arizona" in state_names
        assert "Nevada" in state_names

    @patch.object(MultiStateScraper, '_fetch')
    def test_search_handles_all_errors(self, mock_fetch):
        mock_fetch.side_effect = Exception("Network error")
        scraper = MultiStateScraper()
        results = scraper.search()
        assert results == []
