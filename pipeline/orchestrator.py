from __future__ import annotations

from datetime import datetime

from models.content import BlogPost, Newsletter
from pipeline.content_generator import (
    generate_blog_post,
    generate_newsletters,
    generate_blog_hero_image,
    inject_hero_image_markdown,
)
from pipeline.crm_manager import (
    sync_all_contacts,
    create_marketing_email,
    get_contacts_by_persona,
    log_campaign_to_crm,
)
from pipeline.distributor import send_newsletters
from pipeline.analytics import (
    simulate_engagement,
    generate_performance_summary,
    generate_topic_suggestions,
)
from storage.database import save_campaign, save_ai_summary, get_campaign, get_metrics, get_all_campaigns
from storage.file_store import (
    save_blog_markdown,
    save_newsletter_markdown,
    save_campaign_json,
)


def _campaign_id() -> str:
    return f"camp_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"


def _serialize_newsletters(newsletters: list[Newsletter], nl_paths: dict[str, str]) -> list[dict]:
    result = []
    for nl in newsletters:
        d = nl.model_dump()
        d["source_file"] = nl_paths.get(nl.persona_id, "")
        result.append(d)
    return result


def _save_campaign_state(
    campaign_id: str,
    topic: str,
    blog: BlogPost,
    newsletters: list[Newsletter],
    status: str,
    contacts_synced: int = 0,
    send_date: str = "",
) -> tuple[dict, str, dict[str, str]]:
    """Persist campaign to markdown/json/db and return canonical objects."""
    blog_path = save_blog_markdown(campaign_id, blog.title, blog.outline, blog.body)
    nl_paths: dict[str, str] = {}
    for nl in newsletters:
        nl_paths[nl.persona_id] = save_newsletter_markdown(
            campaign_id, nl.persona_id, nl.subject_line, nl.body
        )

    campaign_dict = {
        "campaign_id": campaign_id,
        "topic": topic,
        "blog_title": blog.title,
        "blog_body": blog.body,
        "blog_outline": blog.outline,
        "newsletters": _serialize_newsletters(newsletters, nl_paths),
        "contacts_synced": contacts_synced,
        "send_date": send_date,
        "status": status,
    }
    save_campaign(campaign_dict)
    save_campaign_json(campaign_id, campaign_dict)
    return campaign_dict, blog_path, nl_paths


def generate_campaign_draft(topic: str) -> dict:
    """Stage 1 (HITL): generate campaign content draft for human review."""
    campaign_id = _campaign_id()
    print(f"\n{'='*60}")
    print(f"  NovaMind Draft Generation — Campaign {campaign_id}")
    print(f"  Topic: \"{topic}\"")
    print(f"{'='*60}\n")

    print("[1/2] Generating draft content with AI...")
    past_campaigns = get_all_campaigns()
    blog = generate_blog_post(topic, past_campaigns=past_campaigns)
    newsletters = generate_newsletters(blog, past_campaigns=past_campaigns)
    hero_image_path = generate_blog_hero_image(topic, blog.title, campaign_id)
    blog.body = inject_hero_image_markdown(
        blog.body,
        hero_image_path,
        f"{blog.title} hero image",
    )

    print("[2/2] Saving draft for human review...")
    campaign_dict, blog_path, _ = _save_campaign_state(
        campaign_id=campaign_id,
        topic=topic,
        blog=blog,
        newsletters=newsletters,
        status="awaiting_review",
        contacts_synced=0,
        send_date="",
    )

    return {
        "campaign_id": campaign_id,
        "status": "awaiting_review",
        "blog": {"title": blog.title, "word_count": blog.word_count, "file": blog_path},
        "newsletters": campaign_dict["newsletters"],
    }


def finalize_campaign_after_review(
    campaign_id: str,
    topic: str,
    blog_title: str,
    blog_body: str,
    newsletters_data: list[dict],
) -> dict:
    """Stage 2 (HITL): use human-approved content, then send/distribute/analyze."""
    hero_image_path = generate_blog_hero_image(topic, blog_title, campaign_id)
    blog_body = inject_hero_image_markdown(
        blog_body,
        hero_image_path,
        f"{blog_title} hero image",
    )
    blog = BlogPost(title=blog_title, body=blog_body, outline=[], topic=topic)
    newsletters = [
        Newsletter(
            persona_id=nl["persona_id"],
            persona_name=nl["persona_name"],
            subject_line=nl["subject_line"],
            body=nl["body"],
            blog_title=blog_title,
        )
        for nl in newsletters_data
    ]

    print(f"\n{'='*60}")
    print(f"  NovaMind Finalization — Campaign {campaign_id}")
    print(f"{'='*60}\n")

    print("[1/5] Saving approved content...")
    campaign_dict, blog_path, nl_paths = _save_campaign_state(
        campaign_id=campaign_id,
        topic=topic,
        blog=blog,
        newsletters=newsletters,
        status="approved",
    )

    print("[2/5] Syncing contacts to CRM...")
    synced = sync_all_contacts()
    campaign_dict["contacts_synced"] = synced
    save_campaign(campaign_dict)
    save_campaign_json(campaign_id, campaign_dict)

    print("[3/5] Distributing newsletters...")
    send_results = send_newsletters(
        campaign_id=campaign_id,
        blog_title=blog.title,
        newsletters=newsletters,
    )

    print("[4/5] Creating marketing emails in HubSpot...")
    hubspot_emails = []
    newsletters_for_crm: list[dict] = []
    for nl in newsletters:
        body_html = nl.body.replace("[First Name]", "{{ contact.firstname }}")
        body_html = body_html.replace("\n", "<br>")
        hs_result = create_marketing_email(
            campaign_id=campaign_id,
            persona_id=nl.persona_id,
            persona_name=nl.persona_name,
            subject_line=nl.subject_line,
            body_html=body_html,
        )
        hs_email_id = hs_result.get("id", "error")
        hubspot_emails.append({"persona": nl.persona_id, "hubspot_email_id": hs_email_id})
        newsletters_for_crm.append({
            "persona": nl.persona_id,
            "subject_line": nl.subject_line,
            "hubspot_email_id": hs_email_id,
        })
        if "error" not in hs_result:
            print(f"  [{nl.persona_name}] HubSpot email ID: {hs_email_id}")
        else:
            print(f"  [{nl.persona_name}] Error: {hs_result}")

    crm_result = log_campaign_to_crm(
        campaign_id,
        blog.title,
        send_results["send_date"],
        newsletters=newsletters_for_crm,
    )
    if "error" in crm_result:
        print(f"  [CRM] Campaign note failed: {crm_result.get('error', crm_result)}")
    else:
        print("  [CRM] Campaign logged to HubSpot (blog title, send date, newsletter IDs).")

    print("[5/5] Analytics deferred (metrics pending after send)...")

    campaign_dict = {
        "campaign_id": campaign_id,
        "topic": topic,
        "blog_title": blog.title,
        "blog_body": blog.body,
        "blog_outline": blog.outline,
        "newsletters": _serialize_newsletters(newsletters, nl_paths),
        "contacts_synced": synced,
        "send_date": send_results["send_date"],
        "status": "sent",
    }
    save_campaign(campaign_dict)
    save_campaign_json(campaign_id, campaign_dict)

    return {
        "campaign_id": campaign_id,
        "status": "sent",
        "blog": {
            "title": blog.title,
            "word_count": blog.word_count,
            "file": blog_path,
        },
        "newsletters": [
            {
                "persona": nl.persona_id,
                "subject_line": nl.subject_line,
                "status": "sent",
            }
            for nl in newsletters
        ],
        "hubspot_emails": hubspot_emails,
        "contacts_synced": synced,
        "campaign_logged": "error" not in crm_result,
        "metrics_pending": True,
        "metrics": None,
        "ai_summary": "",
        "suggested_topics": [],
    }


def run_post_send_analytics(campaign_id: str) -> dict | None:
    """Generate metrics after send, intended to run on page refresh/background."""
    existing = get_metrics(campaign_id)
    if existing:
        return None

    campaign = get_campaign(campaign_id)
    if not campaign:
        return None

    newsletters = campaign.get("newsletters", [])
    if not newsletters:
        return None

    segments = []
    for nl in newsletters:
        pid = nl.get("persona_id", "")
        if not pid:
            continue
        recipients = len(get_contacts_by_persona(pid))
        segments.append(
            {
                "persona": pid,
                "persona_name": nl.get("persona_name", pid),
                "recipients": recipients,
                "subject_line": nl.get("subject_line", ""),
            }
        )

    send_results = {
        "send_date": campaign.get("send_date", ""),
        "segments": segments,
    }
    metrics = simulate_engagement(
        campaign_id=campaign_id,
        blog_title=campaign.get("blog_title", campaign.get("topic", "")),
        send_results=send_results,
    )
    summary = generate_performance_summary(metrics)
    topics = generate_topic_suggestions(metrics)
    save_ai_summary(campaign_id, summary, topics)
    return {
        "campaign_id": campaign_id,
        "overall_open_rate": metrics.overall_open_rate,
        "overall_click_rate": metrics.overall_click_rate,
    }


def run_pipeline(topic: str) -> dict:
    """
    Backward-compatible full auto pipeline:
    generate draft and immediately finalize without human edits.
    """
    draft = generate_campaign_draft(topic)
    # Re-read from DB-backed draft to keep single source of truth.
    from storage.database import get_campaign

    saved = get_campaign(draft["campaign_id"]) or {}
    return finalize_campaign_after_review(
        campaign_id=draft["campaign_id"],
        topic=topic,
        blog_title=saved.get("blog_title", draft["blog"]["title"]),
        blog_body=saved.get("blog_body", ""),
        newsletters_data=saved.get("newsletters", []),
    )
