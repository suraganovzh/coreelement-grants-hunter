"""Tests for SBIR status monitor and NOFO tracker."""

import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime

from src.monitors.sbir_status import SBIRStatusMonitor, ACTIVE_KEYWORDS, SUSPENDED_KEYWORDS
from src.scrapers.nofo_tracker import NOFOTracker, KNOWN_IMMINENT_GRANTS


class TestSBIRStatusMonitor:
    def test_monitor_name(self):
        monitor = SBIRStatusMonitor()
        assert monitor.name == "sbir_monitor"

    def test_check_status_returns_structure(self):
        """Test that check_status returns proper structure even without network."""
        monitor = SBIRStatusMonitor()
        with patch.object(monitor, '_fetch', side_effect=Exception("No network")):
            status = monitor.check_status()

        assert "last_checked" in status
        assert "overall_status" in status
        assert "programs" in status
        assert "NSF_SBIR" in status["programs"]
        assert "DOE_SBIR" in status["programs"]
        assert "NIH_SBIR" in status["programs"]
        assert "DoD_SBIR" in status["programs"]

    def test_program_fields(self):
        monitor = SBIRStatusMonitor()
        with patch.object(monitor, '_fetch', side_effect=Exception("No network")):
            status = monitor.check_status()

        for prog_key, prog in status["programs"].items():
            assert "status" in prog
            assert "accepting_apps" in prog
            assert isinstance(prog["accepting_apps"], bool)
            assert "url" in prog

    def test_default_status_is_suspended(self):
        monitor = SBIRStatusMonitor()
        with patch.object(monitor, '_fetch', side_effect=Exception("No network")):
            status = monitor.check_status()

        assert status["overall_status"] == "SUSPENDED"
        for prog in status["programs"].values():
            assert prog["accepting_apps"] is False

    def test_active_keywords_exist(self):
        assert len(ACTIVE_KEYWORDS) > 0
        assert "accepting applications" in ACTIVE_KEYWORDS

    def test_suspended_keywords_exist(self):
        assert len(SUSPENDED_KEYWORDS) > 0
        assert "expired" in SUSPENDED_KEYWORDS

    def test_check_for_changes_no_previous(self):
        """Test change detection with no previous status file."""
        monitor = SBIRStatusMonitor()
        with patch.object(monitor, '_fetch', side_effect=Exception("No network")):
            changes = monitor.check_for_changes("/nonexistent/path.json")

        # Should detect a change from UNKNOWN to SUSPENDED
        assert changes is not None
        assert changes["changed"] is True


class TestNOFOTracker:
    def test_tracker_name(self):
        tracker = NOFOTracker()
        assert tracker.name == "nofo_pipeline"

    def test_known_imminent_grants(self):
        grants = NOFOTracker.get_known_imminent()
        assert len(grants) > 0

    def test_known_grants_have_required_fields(self):
        for grant in KNOWN_IMMINENT_GRANTS:
            assert "title" in grant
            assert "funder" in grant
            assert "amount_max" in grant
            assert "status" in grant
            assert "prepare_now" in grant
            assert grant["prepare_now"] is True

    def test_doe_battery_materials_in_pipeline(self):
        grants = KNOWN_IMMINENT_GRANTS
        doe_battery = [g for g in grants if "Battery Materials" in g["title"]]
        assert len(doe_battery) > 0
        assert doe_battery[0]["funder"] == "DOE MESC"
        assert doe_battery[0]["amount_max"] == 200000000

    def test_known_grants_have_preparation_steps(self):
        for grant in KNOWN_IMMINENT_GRANTS:
            if "preparation_steps" in grant:
                assert len(grant["preparation_steps"]) > 0

    @patch.object(NOFOTracker, '_fetch')
    def test_search_handles_error(self, mock_fetch):
        mock_fetch.side_effect = Exception("Network error")
        tracker = NOFOTracker()
        results = tracker.search()
        assert results == []  # Graceful failure
