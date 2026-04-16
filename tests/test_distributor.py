"""Tests for the newsletter distribution module."""

from unittest.mock import patch

from models.content import Newsletter
from pipeline.distributor import send_newsletters


@patch("pipeline.distributor.get_contacts_by_persona")
def test_send_newsletters(mock_contacts):
    mock_contacts.side_effect = [
        [{"email": "a@test.com"}, {"email": "b@test.com"}],
        [{"email": "c@test.com"}],
        [{"email": "d@test.com"}, {"email": "e@test.com"}, {"email": "f@test.com"}],
    ]

    newsletters = [
        Newsletter(
            persona_id="creative_professionals",
            persona_name="Creative Professionals",
            subject_line="Subject 1",
            body="Body 1",
        ),
        Newsletter(
            persona_id="brand_strategists",
            persona_name="Brand Strategists",
            subject_line="Subject 2",
            body="Body 2",
        ),
        Newsletter(
            persona_id="account_managers",
            persona_name="Account Managers",
            subject_line="Subject 3",
            body="Body 3",
        ),
    ]

    result = send_newsletters("test_campaign", "Test Blog", newsletters)

    assert result["campaign_id"] == "test_campaign"
    assert result["total_sent"] == 6
    assert len(result["segments"]) == 3
    assert len(result["send_log"]) == 6
