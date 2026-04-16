from __future__ import annotations

import time
import httpx

import config
from storage.file_store import load_contacts


def _get_headers() -> dict:
    return {
        "Authorization": f"Bearer {config.HUBSPOT_API_KEY}",
        "Content-Type": "application/json",
    }


CONTACTS_URL = f"{config.HUBSPOT_BASE_URL}/crm/v3/objects/contacts"
_persona_property_ensured = False


def _make_request(method: str, url: str, json_data: dict | None = None) -> dict:
    """Make an HTTP request to the HubSpot API with error handling."""
    try:
        with httpx.Client(timeout=30) as client:
            response = client.request(method, url, headers=_get_headers(), json=json_data)
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as e:
        print(f"  [HubSpot API error] {e.response.status_code}: {e.response.text[:200]}")
        return {"error": str(e), "status_code": e.response.status_code}
    except httpx.RequestError as e:
        print(f"  [HubSpot connection error] {e}")
        return {"error": str(e)}


_persona_property_available = False


def ensure_persona_property():
    """Create the novamind_persona custom property in HubSpot if it doesn't exist."""
    global _persona_property_ensured, _persona_property_available
    if _persona_property_ensured:
        return

    prop_url = f"{config.HUBSPOT_BASE_URL}/crm/v3/properties/contacts"
    payload = {
        "name": "novamind_persona",
        "label": "NovaMind Persona",
        "type": "enumeration",
        "fieldType": "select",
        "groupName": "contactinformation",
        "options": [
            {"label": "Creative Professionals", "value": "creative_professionals"},
            {"label": "Brand Strategists", "value": "brand_strategists"},
            {"label": "Account Managers", "value": "account_managers"},
        ],
    }

    result = _make_request("POST", prop_url, payload)
    if "error" not in result:
        print("  Created custom property: novamind_persona")
        _persona_property_available = True
    elif result.get("status_code") == 409:
        print("  Custom property novamind_persona already exists")
        _persona_property_available = True
    else:
        print("  Note: Storing persona in jobtitle field (custom property requires additional scope)")

    _persona_property_ensured = True


def create_or_update_contact(contact: dict) -> dict:
    """Create a contact in HubSpot, or update if they already exist."""
    properties = {
        "email": contact["email"],
        "firstname": contact["first_name"],
        "lastname": contact["last_name"],
        "company": contact.get("company", ""),
    }

    persona = contact.get("persona", "")
    if _persona_property_available:
        properties["novamind_persona"] = persona
    else:
        properties["jobtitle"] = persona.replace("_", " ").title()

    payload = {"properties": properties}

    result = _make_request("POST", CONTACTS_URL, payload)

    if result.get("status_code") == 409:
        search_result = search_contact_by_email(contact["email"])
        if search_result:
            contact_id = search_result["id"]
            update_url = f"{CONTACTS_URL}/{contact_id}"
            result = _make_request("PATCH", update_url, payload)

    return result


def search_contact_by_email(email: str) -> dict | None:
    """Search for a contact by email address."""
    search_url = f"{config.HUBSPOT_BASE_URL}/crm/v3/objects/contacts/search"
    payload = {
        "filterGroups": [
            {
                "filters": [
                    {
                        "propertyName": "email",
                        "operator": "EQ",
                        "value": email,
                    }
                ]
            }
        ]
    }
    result = _make_request("POST", search_url, payload)
    results = result.get("results", [])
    return results[0] if results else None


def get_contacts_by_persona(persona_id: str) -> list[dict]:
    """Get all mock contacts matching a persona from the local contact list."""
    contacts = load_contacts()
    return [c for c in contacts if c.get("persona") == persona_id]


def sync_all_contacts() -> int:
    """Sync all mock contacts to HubSpot. Returns the number synced."""
    ensure_persona_property()

    contacts = load_contacts()
    synced = 0
    for contact in contacts:
        result = create_or_update_contact(contact)
        if "error" not in result:
            synced += 1
        print(f"  Synced: {contact['first_name']} {contact['last_name']} ({contact['persona']})")
    return synced


def _get_all_hubspot_contact_ids() -> list[str]:
    """Look up HubSpot contact IDs for all contacts in our local list."""
    contacts = load_contacts()
    contact_ids = []
    for contact in contacts:
        result = search_contact_by_email(contact["email"])
        if result:
            contact_ids.append(result["id"])
    return contact_ids


def log_campaign_to_crm(
    campaign_id: str,
    blog_title: str,
    send_date: str,
    newsletters: list[dict] | None = None,
) -> dict:
    """Log a campaign as a note in HubSpot, associated with all contacts.

    Each newsletter dict may include: persona (or persona_id), subject_line,
    and hubspot_email_id (HubSpot marketing email object ID after creation).
    """
    newsletter_lines = ""
    if newsletters:
        for i, nl in enumerate(newsletters, 1):
            persona = nl.get("persona") or nl.get("persona_id", "")
            subject = nl.get("subject_line", "")
            eid = nl.get("hubspot_email_id")
            id_part = ""
            if eid is not None and str(eid) not in ("", "error", "None"):
                id_part = f" | Newsletter ID: {eid}"
            newsletter_lines += f"\n  {i}. [{persona}] {subject}{id_part}"
    else:
        newsletter_lines = "\n  Newsletters sent to 3 persona segments."

    contact_ids = _get_all_hubspot_contact_ids()

    associations = []
    for cid in contact_ids:
        associations.append({
            "to": {"id": cid},
            "types": [
                {
                    "associationCategory": "HUBSPOT_DEFINED",
                    "associationTypeId": 202,
                }
            ],
        })

    notes_url = f"{config.HUBSPOT_BASE_URL}/crm/v3/objects/notes"
    hs_timestamp = str(int(time.time() * 1000))
    payload = {
        "properties": {
            "hs_note_body": (
                f"NovaMind Campaign: {campaign_id}\n"
                f"Blog Title: {blog_title}\n"
                f"Send Date: {send_date}\n"
                f"Newsletters:{newsletter_lines}"
            ),
            "hs_timestamp": hs_timestamp,
        },
        "associations": associations,
    }
    return _make_request("POST", notes_url, payload)


MARKETING_EMAILS_URL = f"{config.HUBSPOT_BASE_URL}/marketing/v3/emails/"
MARKETING_STATS_URL = f"{config.HUBSPOT_BASE_URL}/marketing/emails/2026-03/statistics/list"


def fetch_email_statistics(email_ids: list[str]) -> dict[str, dict]:
    """Fetch real performance stats from HubSpot for the given marketing email IDs.

    Returns a dict keyed by email ID, each containing counters and ratios:
        {
            "334783443698": {
                "sent": 5, "delivered": 5, "opens": 3, "clicks": 1,
                "unsubscribes": 0, "bounces": 0,
                "open_rate": 0.6, "click_rate": 0.2, "unsubscribe_rate": 0.0,
                "bounce_rate": 0.0,
            },
            ...
        }
    """
    start_ts = "2026-01-01T00:00:00Z"
    end_ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    results: dict[str, dict] = {}
    for eid in email_ids:
        url = (
            f"{MARKETING_STATS_URL}"
            f"?emailIds={eid}"
            f"&startTimestamp={start_ts}"
            f"&endTimestamp={end_ts}"
        )
        data = _make_request("GET", url)
        if "error" in data:
            print(f"  [Stats] Could not fetch stats for email {eid}: {data.get('error', '')}")
            results[str(eid)] = _empty_stats()
            continue

        agg = data.get("aggregate", {})
        counters = agg.get("counters", {})
        ratios = agg.get("ratios", {})

        sent = counters.get("sent", 0)
        delivered = counters.get("delivered", 0)
        opens = counters.get("open", 0)
        clicks = counters.get("click", 0)
        unsubscribes = counters.get("unsubscribed", 0)
        bounces = counters.get("bounce", 0)

        results[str(eid)] = {
            "sent": sent,
            "delivered": delivered,
            "opens": opens,
            "clicks": clicks,
            "unsubscribes": unsubscribes,
            "bounces": bounces,
            "open_rate": ratios.get("openratio", 0.0),
            "click_rate": ratios.get("clickratio", 0.0),
            "unsubscribe_rate": ratios.get("unsubscribedratio", 0.0),
            "bounce_rate": ratios.get("bounceratio", 0.0),
        }
    return results


def _empty_stats() -> dict:
    return {
        "sent": 0, "delivered": 0, "opens": 0, "clicks": 0,
        "unsubscribes": 0, "bounces": 0,
        "open_rate": 0.0, "click_rate": 0.0,
        "unsubscribe_rate": 0.0, "bounce_rate": 0.0,
    }

PERSONA_LIST_IDS = {
    "creative_professionals": 12,
    "brand_strategists": 13,
    "account_managers": 14,
}


def create_marketing_email(
    campaign_id: str,
    persona_id: str,
    persona_name: str,
    subject_line: str,
    body_html: str,
) -> dict:
    """Create a marketing email in HubSpot with content, recipient list, and sender."""
    list_id = PERSONA_LIST_IDS.get(persona_id)

    payload = {
        "name": f"NovaMind Newsletter - {persona_name} ({campaign_id})",
        "subject": subject_line,
        "from": {
            "fromName": "NovaMind",
            "email": "imthuctrinh@gmail.com",
            "replyTo": "imthuctrinh@gmail.com",
        },
        "content": {
            "templatePath": "@hubspot/email/dnd/welcome.html",
            "widgets": {},
        },
    }

    if list_id:
        payload["to"] = {
            "contactIlsLists": {
                "include": [list_id],
                "exclude": [],
            },
        }

    result = _make_request("POST", MARKETING_EMAILS_URL, payload)

    if "error" not in result:
        email_id = result.get("id")
        url = f"{MARKETING_EMAILS_URL}{email_id}"
        body_payload = {
            "content": {
                "widgets": {
                    "module-1-0-0": {
                        "body": {
                            "html": body_html,
                            "css_class": "dnd-module",
                            "path": "@hubspot/rich_text",
                            "schema_version": 2,
                        },
                        "child_css": {},
                        "css": {},
                        "id": "module-1-0-0",
                        "name": "module-1-0-0",
                        "order": 3,
                        "type": "module",
                        "module_id": 1155639,
                    }
                }
            }
        }
        result = _make_request("PATCH", url, body_payload)

    return result
