from __future__ import annotations

from datetime import datetime

from models.content import Newsletter
from pipeline.crm_manager import get_contacts_by_persona


def send_newsletters(
    campaign_id: str,
    blog_title: str,
    newsletters: list[Newsletter],
) -> dict:
    """
    Send the appropriate newsletter version to each persona segment.
    In dev mode, this simulates the send and logs to the database.
    """
    send_date = datetime.utcnow().isoformat()
    total_sent = 0
    send_log: list[dict] = []
    segments: list[dict] = []

    for newsletter in newsletters:
        contacts = get_contacts_by_persona(newsletter.persona_id)
        recipient_count = len(contacts)
        total_sent += recipient_count

        print(f"  Sending to {newsletter.persona_name}: {recipient_count} recipients")
        print(f"    Subject: {newsletter.subject_line}")

        for contact in contacts:
            send_log.append({
                "email": contact["email"],
                "persona": newsletter.persona_id,
                "subject": newsletter.subject_line,
                "sent_at": send_date,
                "status": "delivered",
            })

        segments.append({
            "persona": newsletter.persona_id,
            "persona_name": newsletter.persona_name,
            "recipients": recipient_count,
            "subject_line": newsletter.subject_line,
        })

    return {
        "campaign_id": campaign_id,
        "total_sent": total_sent,
        "send_date": send_date,
        "segments": segments,
        "send_log": send_log,
    }
