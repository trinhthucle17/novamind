"""Tests for the performance analytics module."""

from unittest.mock import patch

from pipeline.analytics import simulate_engagement
from models.metrics import CampaignMetrics


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
