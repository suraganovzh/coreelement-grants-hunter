"""Tests for grant analyzers."""

import pytest
from src.analyzers.fit_scorer import FitScorer
from src.analyzers.complexity_scorer import ComplexityScorer


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
