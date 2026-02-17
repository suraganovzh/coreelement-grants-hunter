"""Tests for grant scrapers."""

import pytest
from unittest.mock import patch, MagicMock
from datetime import date, timedelta

from src.scrapers.base_scraper import GrantResult
from src.scrapers.grants_gov import GrantsGovScraper
from src.scrapers.sbir_scraper import SBIRScraper


class TestGrantResult:
    def test_grant_result_defaults(self):
        result = GrantResult(title="Test Grant")
        assert result.title == "Test Grant"
        assert result.currency == "USD"
        assert result.amount_min is None
        assert result.industry_tags == []

    def test_grant_result_full(self):
        result = GrantResult(
            title="AI Mining Grant",
            funder="DOE",
            description="AI for mining",
            amount_min=50000,
            amount_max=250000,
            currency="USD",
            deadline=date.today() + timedelta(days=30),
            url="https://example.com/grant",
            source="grants_gov",
            grant_type="federal",
            industry_tags=["AI", "mining"],
        )
        assert result.funder == "DOE"
        assert result.amount_max == 250000
        assert len(result.industry_tags) == 2


class TestGrantsGovScraper:
    def test_scraper_name(self):
        scraper = GrantsGovScraper()
        assert scraper.name == "grants_gov"

    def test_extract_tags(self):
        tags = GrantsGovScraper._extract_tags(
            "AI for Critical Mineral Exploration",
            "Machine learning approach to geological survey of lithium deposits"
        )
        assert "AI" in tags
        assert "critical minerals" in tags
        assert "geology" in tags

    def test_extract_tags_empty(self):
        tags = GrantsGovScraper._extract_tags("Generic Title", "No relevant content")
        assert len(tags) == 0

    @patch.object(GrantsGovScraper, '_post')
    def test_search_handles_api_error(self, mock_post):
        mock_post.side_effect = Exception("API Error")
        scraper = GrantsGovScraper()
        results = scraper.search(keywords=["test"])
        assert results == []

    @patch.object(GrantsGovScraper, '_post')
    def test_search_parses_results(self, mock_post):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "oppHits": [
                {
                    "id": "12345",
                    "title": "Critical Minerals AI Research",
                    "number": "DE-FOA-0001234",
                    "agencyName": "Department of Energy",
                    "closeDate": "03/15/2026",
                    "awardFloor": 50000,
                    "awardCeiling": 250000,
                    "synopsis": {"synopsisDesc": "AI for critical minerals exploration"},
                }
            ]
        }
        mock_post.return_value = mock_response

        scraper = GrantsGovScraper()
        results = scraper.search(keywords=["critical minerals"])

        assert len(results) == 1
        assert "Critical Minerals" in results[0].title
        assert results[0].funder == "Department of Energy"
        assert results[0].amount_min == 50000


class TestSBIRScraper:
    def test_scraper_name(self):
        scraper = SBIRScraper()
        assert scraper.name == "sbir_sttr"

    def test_phase_amounts_phase_i(self):
        min_amt, max_amt = SBIRScraper._phase_amounts("Phase I")
        assert min_amt == 50000
        assert max_amt == 275000

    def test_phase_amounts_phase_ii(self):
        min_amt, max_amt = SBIRScraper._phase_amounts("Phase II")
        assert min_amt == 500000
        assert max_amt == 1500000

    @patch.object(SBIRScraper, '_fetch')
    def test_search_handles_error(self, mock_fetch):
        mock_fetch.side_effect = Exception("Connection error")
        scraper = SBIRScraper()
        results = scraper.search()
        assert results == []
