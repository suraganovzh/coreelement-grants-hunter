"""Tests for enhanced eligibility checker with partnership pathways."""

import pytest
from unittest.mock import patch, MagicMock

from src.analyzers.eligibility_checker import EligibilityChecker, COMPANY_PARTNERSHIPS


class TestPartnershipData:
    def test_partnerships_exist(self):
        assert len(COMPANY_PARTNERSHIPS) > 0

    def test_csm_partnership(self):
        csm = COMPANY_PARTNERSHIPS["colorado_school_of_mines"]
        assert csm["type"] == "university"
        assert csm["location"] == "Colorado"
        assert "STTR" in csm["enables"]
        assert "state_grants" in csm["enables"]

    def test_stanford_partnership(self):
        stanford = COMPANY_PARTNERSHIPS["stanford_mineral_x"]
        assert stanford["type"] == "research_center"
        assert "STTR" in stanford["enables"]

    def test_berkeley_partnership(self):
        lbl = COMPANY_PARTNERSHIPS["lawrence_berkeley_lab"]
        assert lbl["type"] == "national_lab"
        assert "DOE_partnerships" in lbl["enables"]
        assert "EU_connections" in lbl["enables"]


class TestPartnershipPathways:
    @patch('src.analyzers.eligibility_checker.GroqClient')
    def test_sttr_pathway_detected(self, mock_groq):
        mock_groq.return_value = MagicMock()
        checker = EligibilityChecker(groq_client=mock_groq.return_value)

        text = "This grant requires a research institution partner via STTR"
        result = checker._check_partnership_pathways(text, "federal")

        assert result is not None
        assert result["pathway"] == "STTR"
        assert "Mines" in result["partner_name"] or "Berkeley" in result["partner_name"]

    @patch('src.analyzers.eligibility_checker.GroqClient')
    def test_eu_consortium_detected(self, mock_groq):
        mock_groq.return_value = MagicMock()
        checker = EligibilityChecker(groq_client=mock_groq.return_value)

        text = "Requires a European consortium partner"
        result = checker._check_partnership_pathways(text, "international")

        assert result is not None
        assert result["pathway"] == "EU_Consortium"

    @patch('src.analyzers.eligibility_checker.GroqClient')
    def test_foundation_affiliate_detected(self, mock_groq):
        mock_groq.return_value = MagicMock()
        checker = EligibilityChecker(groq_client=mock_groq.return_value)

        text = "Only for scientists at accredited nonprofit institution"
        result = checker._check_partnership_pathways(text, "private")

        assert result is not None
        assert result["pathway"] == "Foundation_Affiliate"

    @patch('src.analyzers.eligibility_checker.GroqClient')
    def test_colorado_state_pathway(self, mock_groq):
        mock_groq.return_value = MagicMock()
        checker = EligibilityChecker(groq_client=mock_groq.return_value)

        text = "Colorado Advanced Industries state grant program"
        result = checker._check_partnership_pathways(text, "state")

        assert result is not None
        assert result["pathway"] == "State_Partner"
        assert "Colorado" in result["partner_name"]

    @patch('src.analyzers.eligibility_checker.GroqClient')
    def test_no_pathway_for_generic_text(self, mock_groq):
        mock_groq.return_value = MagicMock()
        checker = EligibilityChecker(groq_client=mock_groq.return_value)

        text = "Open to all US small businesses for AI research"
        result = checker._check_partnership_pathways(text, "federal")

        assert result is None

    @patch('src.analyzers.eligibility_checker.GroqClient')
    def test_partnership_overrides_nonprofit_blocker(self, mock_groq):
        mock_groq.return_value = MagicMock()
        checker = EligibilityChecker(groq_client=mock_groq.return_value)

        rule_result = {
            "eligible": False,
            "reasons": [],
            "blockers": ["Requires: Non-profit only"],
            "confidence": 0.8,
        }
        partnership = {
            "pathway": "STTR",
            "partner_key": "colorado_school_of_mines",
            "partner_name": "Colorado School of Mines",
            "partner_type": "university",
        }

        result = checker._apply_partnership_override(rule_result, partnership)
        assert result["eligible"] is True
        assert len(result["blockers"]) == 0


class TestQualityCheck:
    def test_validate_valid_grant(self):
        from src.validation.quality_check import validate_grant

        grant = {
            "id": "test-123",
            "title": "Test Grant",
            "funder": "Test Funder",
            "url": "https://example.com",
            "deadline": "2026-03-15",
            "amount_max": 100000,
        }
        is_valid, issues = validate_grant(grant)
        assert is_valid is True

    def test_validate_invalid_grant(self):
        from src.validation.quality_check import validate_grant

        grant = {"title": ""}  # Missing required fields
        is_valid, issues = validate_grant(grant)
        assert is_valid is False
        assert any("Missing required" in i for i in issues)

    def test_validate_bad_deadline(self):
        from src.validation.quality_check import validate_grant

        grant = {
            "id": "test-123",
            "title": "Test",
            "funder": "Test",
            "url": "https://example.com",
            "deadline": "not-a-date",
        }
        _, issues = validate_grant(grant)
        assert any("deadline" in i.lower() for i in issues)
