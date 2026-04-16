from __future__ import annotations

from datetime import datetime

from models.content import Campaign
from models.metrics import CampaignMetrics
from pipeline.content_generator import generate_blog_post, generate_newsletters, suggest_topics
from pipeline.crm_manager import sync_all_contacts, create_marketing_email
from pipeline.distributor import send_newsletters
from pipeline.analytics import simulate_engagement, generate_performance_summary, generate_topic_suggestions
from storage.database import save_campaign, save_ai_summary
from storage.file_store import save_blog_markdown, save_newsletter_markdown, save_campaign_json


def run_pipeline(topic: str) -> dict:
    """
    Execute the full NovaMind content pipeline:
    1. Generate blog post + newsletter variants
    2. Sync contacts to CRM and segment by persona
    3. Send newsletters to each persona segment
    4. Collect engagement metrics and generate AI summary
    """
    campaign_id = f"camp_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
    print(f"\n{'='*60}")
    print(f"  NovaMind Pipeline — Campaign {campaign_id}")
    print(f"  Topic: \"{topic}\"")
    print(f"{'='*60}\n")

    # --- Step 1: Content Generation ---
    print("[1/5] Generating content with AI...")
    blog = generate_blog_post(topic)
    print(f"  Blog: \"{blog.title}\" ({blog.word_count} words)")

    newsletters = generate_newsletters(blog)
    for nl in newsletters:
        print(f"  Newsletter ({nl.persona_name}): \"{nl.subject_line}\"")

    # --- Step 2: Save content to files ---
    print("\n[2/5] Saving content and syncing contacts to CRM...")
    blog_path = save_blog_markdown(campaign_id, blog.title, blog.outline, blog.body)
    print(f"  Blog saved: {blog_path}")

    nl_paths = []
    for nl in newsletters:
        path = save_newsletter_markdown(campaign_id, nl.persona_id, nl.subject_line, nl.body)
        nl_paths.append(path)
        print(f"  Newsletter saved: {path}")

    synced = sync_all_contacts()
    print(f"  Contacts synced to HubSpot: {synced}")

    # --- Step 3: Send newsletters ---
    print("\n[3/5] Distributing newsletters...")
    send_results = send_newsletters(
        campaign_id=campaign_id,
        blog_title=blog.title,
        newsletters=newsletters,
    )
    print(f"  Total emails sent: {send_results['total_sent']}")

    # --- Step 4: Create HubSpot marketing emails ---
    print("\n[4/5] Creating marketing emails in HubSpot...")
    hubspot_emails = []
    for nl in newsletters:
        body_html = nl.body.replace("\n", "<br>")
        body_html = f"<p>Hey {{{{ contact.firstname }}}},</p>{body_html}"
        hs_result = create_marketing_email(
            campaign_id=campaign_id,
            persona_id=nl.persona_id,
            persona_name=nl.persona_name,
            subject_line=nl.subject_line,
            body_html=body_html,
        )
        hs_email_id = hs_result.get("id", "error")
        hubspot_emails.append({"persona": nl.persona_id, "hubspot_email_id": hs_email_id})
        if "error" not in hs_result:
            print(f"  [{nl.persona_name}] HubSpot email ID: {hs_email_id}")
        else:
            print(f"  [{nl.persona_name}] Error: {hs_result}")

    # --- Step 5: Analytics ---
    print("\n[5/5] Analyzing performance...")
    metrics = simulate_engagement(campaign_id, blog.title, send_results)

    for pm in metrics.persona_metrics:
        print(f"  {pm.persona_name}: {pm.open_rate}% open, {pm.click_rate}% click")

    summary = generate_performance_summary(metrics)
    metrics.ai_summary = summary
    print(f"\n  AI Summary:\n  {summary[:200]}...")

    topics = generate_topic_suggestions(metrics)
    metrics.suggested_topics = topics
    save_ai_summary(campaign_id, summary, topics)

    print("\n  Suggested next topics:")
    for i, t in enumerate(topics, 1):
        print(f"    {i}. {t}")

    # --- Save campaign record ---
    campaign = Campaign(
        campaign_id=campaign_id,
        topic=topic,
        blog=blog,
        newsletters=newsletters,
        contacts_synced=synced,
        send_date=send_results["send_date"],
        status="sent",
    )

    campaign_dict = {
        "campaign_id": campaign_id,
        "topic": topic,
        "blog_title": blog.title,
        "blog_body": blog.body,
        "blog_outline": blog.outline,
        "newsletters": [nl.model_dump() for nl in newsletters],
        "contacts_synced": synced,
        "send_date": send_results["send_date"],
        "status": "sent",
    }
    save_campaign(campaign_dict)
    save_campaign_json(campaign_id, campaign_dict)

    print(f"\n{'='*60}")
    print(f"  Pipeline complete! Campaign: {campaign_id}")
    print(f"{'='*60}\n")

    return {
        "campaign_id": campaign_id,
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
        "campaign_logged": True,
        "metrics": {
            "overall_open_rate": metrics.overall_open_rate,
            "overall_click_rate": metrics.overall_click_rate,
        },
        "ai_summary": summary,
        "suggested_topics": topics,
    }
