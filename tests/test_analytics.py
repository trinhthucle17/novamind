"""Tests for the performance analytics module."""

from unittest.mock import patch

from pipeline.analytics import (
    _build_lightweight_recommendations,
    generate_performance_summary,
    simulate_engagement,
)
from models.metrics import CampaignMetrics, PersonaMetrics


@patch("pipeline.analytics.save_metrics")
def test_simulate_engagement(mock_save):
    send_results = {
        "send_date": "2026-04-14T12:00:00",
        "segments": [
            {"persona": "creative_professionals", "persona_name": "Creative Professionals", "recipients": 50},
            {"persona": "brand_strategists", "persona_name": "Brand Strategists", "recipients": 50},
            {"persona": "account_managers", "persona_name": "Account Managers", "recipients": 50},
        ],
    }

    metrics = simulate_engagement("test_camp", "Test Blog", send_results)

    assert isinstance(metrics, CampaignMetrics)
    assert metrics.campaign_id == "test_camp"
    assert len(metrics.persona_metrics) == 3
    assert metrics.total_recipients == 150

    for pm in metrics.persona_metrics:
        assert 0 <= pm.open_rate <= 100
        assert 0 <= pm.click_rate <= 100
        assert 0 <= pm.unsubscribe_rate <= 100
        assert pm.opens <= pm.recipients
        assert pm.clicks <= pm.recipients

    mock_save.assert_called_once()


def test_lightweight_recommendations_are_data_backed():
    metrics = CampaignMetrics(
        campaign_id="camp_test",
        blog_title="Test Blog",
        persona_metrics=[
            PersonaMetrics(
                persona_id="creative_professionals",
                persona_name="Creative Professionals",
                recipients=10,
                opens=5,
                clicks=2,
                unsubscribes=0,
            ),
            PersonaMetrics(
                persona_id="brand_strategists",
                persona_name="Brand Strategists",
                recipients=10,
                opens=3,
                clicks=1,
                unsubscribes=1,
            ),
            PersonaMetrics(
                persona_id="account_managers",
                persona_name="Account Managers",
                recipients=10,
                opens=4,
                clicks=0,
                unsubscribes=0,
            ),
        ],
    )
    baselines = {
        "creative_professionals": {"click_rate": 12.0},
    }

    recs = _build_lightweight_recommendations(metrics, baselines)
    assert len(recs) >= 3
    assert any("Creative Professionals" in r for r in recs)
    assert any("Brand Strategists" in r or "Account Managers" in r for r in recs)


@patch("pipeline.analytics.get_historical_metrics", return_value=[])
@patch("pipeline.analytics.config.OPENAI_API_KEY", "")
def test_generate_performance_summary_fallback_is_deterministic(_mock_history):
    metrics = CampaignMetrics(
        campaign_id="camp_test",
        blog_title="Deterministic Summary Blog",
        persona_metrics=[
            PersonaMetrics(
                persona_id="creative_professionals",
                persona_name="Creative Professionals",
                recipients=8,
                opens=4,
                clicks=1,
                unsubscribes=0,
            ),
            PersonaMetrics(
                persona_id="brand_strategists",
                persona_name="Brand Strategists",
                recipients=12,
                opens=3,
                clicks=0,
                unsubscribes=1,
            ),
        ],
    )

    summary = generate_performance_summary(metrics)
    assert "Deterministic Summary Blog" in summary
    assert "20 recipients" in summary
    assert "Recommendations:" in summary
