"""Tests for the HubSpot CRM manager module."""

from unittest.mock import patch

from pipeline.crm_manager import (
    create_or_update_contact,
    get_contacts_by_persona,
    search_contact_by_email,
)


MOCK_CONTACT = {
    "email": "test@example.com",
    "first_name": "Test",
    "last_name": "User",
    "company": "TestCo",
    "persona": "brand_strategists",
}


@patch("pipeline.crm_manager._make_request")
def test_create_contact(mock_request):
    mock_request.return_value = {"id": "123", "properties": {"email": "test@example.com"}}

    result = create_or_update_contact(MOCK_CONTACT)

    assert "id" in result
    mock_request.assert_called_once()
    call_args = mock_request.call_args
    assert call_args[0][0] == "POST"


@patch("pipeline.crm_manager._make_request")
def test_create_contact_conflict_updates(mock_request):
    mock_request.side_effect = [
        {"error": "Conflict", "status_code": 409},
        {"results": [{"id": "456"}]},
        {"id": "456", "properties": {"email": "test@example.com"}},
    ]

    result = create_or_update_contact(MOCK_CONTACT)
    assert mock_request.call_count == 3


def test_get_contacts_by_persona():
    contacts = get_contacts_by_persona("creative_professionals")
    assert len(contacts) > 0
    assert all(c["persona"] == "creative_professionals" for c in contacts)


def test_get_contacts_by_persona_all_segments():
    for persona in ["creative_professionals", "brand_strategists", "account_managers"]:
        contacts = get_contacts_by_persona(persona)
        assert len(contacts) > 0


@patch("pipeline.crm_manager._make_request")
def test_search_contact_by_email(mock_request):
    mock_request.return_value = {"results": [{"id": "789", "properties": {"email": "test@example.com"}}]}

    result = search_contact_by_email("test@example.com")
    assert result is not None
    assert result["id"] == "789"


@patch("pipeline.crm_manager._make_request")
def test_search_contact_not_found(mock_request):
    mock_request.return_value = {"results": []}

    result = search_contact_by_email("nonexistent@example.com")
    assert result is None
