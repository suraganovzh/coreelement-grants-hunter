"""Tests for grant analyzers."""

import pytest
from src.analyzers.fit_scorer import FitScorer
from src.analyzers.complexity_scorer import ComplexityScorer
from src.analyzers.winner_matcher import find_similar_winners, extract_year


class TestFitScorer:
    def setup_method(self):
        self.scorer = FitScorer()

    def test_high_fit_grant(self):
        result = self.scorer.score(
            title="AI for Critical Mineral Exploration",
            description="Develop machine learning models for lithium and copper deposit prediction using geological survey data.",
            funder="Department of Energy",
            grant_type="federal",
            eligibility_text="Open to small businesses and for-profit organizations",
            amount_min=100000,
            amount_max=500000,
            deadline_days=30,
        )
        assert result["overall"] >= 60
        assert "RECOMMENDED" in result["recommendation"].upper()

    def test_low_fit_grant(self):
        result = self.scorer.score(
            title="Community Garden Project",
            description="Fund community gardens in urban areas for food security.",
            funder="Local Foundation",
            grant_type="private",
            eligibility_text="Non-profit organizations only",
            amount_min=5000,
            amount_max=10000,
            deadline_days=30,
        )
        assert result["overall"] < 50

    def test_score_with_missing_data(self):
        result = self.scorer.score(
            title="Unknown Grant",
            description="",
        )
        assert 0 <= result["overall"] <= 100
        assert "breakdown" in result

    def test_recommendation_tiers(self):
        assert "HIGHLY" in FitScorer._recommendation(95).upper()
        assert "STRONGLY" in FitScorer._recommendation(85).upper()
        assert "RECOMMENDED" in FitScorer._recommendation(75).upper()
        assert "NOT RECOMMENDED" in FitScorer._recommendation(20).upper()


class TestComplexityScorer:
    def setup_method(self):
        self.scorer = ComplexityScorer()

    def test_simple_grant(self):
        result = self.scorer.score(
            grant_text="Simple online application form. Submit a pitch deck and one-page executive summary.",
            grant_type="private",
            amount=50000,
        )
        assert result["score"] <= 4
        assert "Simple" in result["classification"]

    def test_complex_grant(self):
        result = self.scorer.score(
            grant_text="Full proposal required with detailed budget, matching funds, partnership letters, "
                       "environmental assessment, data management plan, milestone deliverables, and peer review.",
            grant_type="federal",
            amount=2000000,
        )
        assert result["score"] >= 7
        assert "Complex" in result["classification"]

    def test_estimated_hours_range(self):
        result = self.scorer.score("Simple form", "private", 10000)
        assert 4 <= result["estimated_hours"] <= 100

    def test_classification(self):
        assert "Simple" in ComplexityScorer._classify(2)
        assert "Medium" in ComplexityScorer._classify(5)
        assert "Complex" in ComplexityScorer._classify(9)


class TestWinnerMatcher:
    def setup_method(self):
        self.grant = {
            "title": "AI for Critical Mineral Exploration",
            "funder": "Department of Energy",
            "description": "Machine learning for lithium deposit prediction",
            "amount_max": 250000,
            "industry_tags": ["AI", "mining", "critical minerals"],
        }
        self.winners = [
            {
                "title": "AI-Driven Subsurface Mineral Prediction",
                "funder": "Department of Energy",
                "winner": "GeoTech AI Inc",
                "amount": 200000,
                "award_date": "2024-06-15",
                "keywords": ["AI", "mining", "geological"],
                "abstract": "Using machine learning to predict mineral deposits.",
            },
            {
                "title": "Urban Garden Automation",
                "funder": "USDA",
                "winner": "FarmBot LLC",
                "amount": 50000,
                "award_date": "2023-01-10",
                "keywords": ["agriculture", "automation"],
                "abstract": "Automating urban garden management.",
            },
            {
                "title": "Critical Minerals Supply Chain Analysis",
                "funder": "Department of Energy",
                "winner": "MineralChain Corp",
                "amount": 300000,
                "award_date": "2024-03-01",
                "keywords": ["critical minerals", "supply chain"],
                "abstract": "Analyzing critical minerals supply chain risks.",
            },
        ]

    def test_finds_similar_winners(self):
        results = find_similar_winners(self.grant, self.winners)
        assert len(results) >= 1
        # GeoTech AI should be the top match (same funder + keyword overlap)
        assert results[0]["company"] == "GeoTech AI Inc"

    def test_same_funder_ranks_higher(self):
        results = find_similar_winners(self.grant, self.winners)
        companies = [r["company"] for r in results]
        # DOE-funded winners should appear before USDA
        assert "FarmBot LLC" not in companies or companies.index("GeoTech AI Inc") < companies.index("FarmBot LLC")

    def test_returns_max_5(self):
        # Create many winners
        many_winners = self.winners * 10
        results = find_similar_winners(self.grant, many_winners)
        assert len(results) <= 5

    def test_empty_winners(self):
        results = find_similar_winners(self.grant, [])
        assert results == []

    def test_result_structure(self):
        results = find_similar_winners(self.grant, self.winners)
        if results:
            r = results[0]
            assert "company" in r
            assert "similarity_score" in r
            assert "match_reasons" in r
            assert isinstance(r["similarity_score"], int)
            assert isinstance(r["match_reasons"], list)

    def test_extract_year(self):
        assert extract_year("2024-06-15") == 2024
        assert extract_year("March 15, 2023") == 2023
        assert extract_year("") == 0
        assert extract_year(None) == 0

    def test_similarity_score_range(self):
        results = find_similar_winners(self.grant, self.winners)
        for r in results:
            assert r["similarity_score"] >= 25  # Minimum threshold
