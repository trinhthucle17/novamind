"""
NovaMind Blog Watcher — Automated Newsletter Trigger

Watches the data/content/ directory for new blog post files.
When a new blog is detected, it automatically:
  1. Reads the blog content
  2. Generates 3 persona-tailored newsletters via AI
  3. Creates marketing emails in HubSpot with the right recipient lists
  4. Logs the campaign to the CRM

Usage:
    python trigger.py              # Watch mode (continuous)
    python trigger.py --once       # Process any unprocessed blogs and exit
"""

from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime
from pathlib import Path

from models.content import Newsletter
from pipeline.content_generator import generate_newsletters
from pipeline.crm_manager import (
    create_marketing_email,
    log_campaign_to_crm,
    sync_all_contacts,
)
from pipeline.distributor import send_newsletters
from storage.database import save_campaign
from storage.file_store import save_campaign_json, save_newsletter_markdown

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
CONTENT_DIR = os.path.join(DATA_DIR, "content")
CAMPAIGNS_DIR = os.path.join(DATA_DIR, "campaigns")
PROCESSED_LOG = os.path.join(CAMPAIGNS_DIR, ".processed_blogs.json")

POLL_INTERVAL = 10


def _load_processed() -> set[str]:
    if os.path.exists(PROCESSED_LOG):
        with open(PROCESSED_LOG, "r") as f:
            return set(json.load(f))
    return set()


def _save_processed(processed: set[str]):
    os.makedirs(CAMPAIGNS_DIR, exist_ok=True)
    with open(PROCESSED_LOG, "w") as f:
        json.dump(sorted(processed), f, indent=2)


def _extract_blog_info(filepath: str) -> dict | None:
    """Extract title and body from a blog markdown file."""
    with open(filepath, "r") as f:
        content = f.read()

    lines = content.strip().split("\n")
    title = ""
    for line in lines:
        if line.startswith("# ") and not title:
            title = line[2:].strip()
            break

    separator_idx = content.find("---")
    if separator_idx != -1:
        body = content[separator_idx + 3:].strip()
    else:
        body = content

    if not title:
        return None

    return {"title": title, "body": body, "full_content": content}


def _find_unprocessed_blogs(processed: set[str]) -> list[str]:
    """Find blog markdown files that haven't been processed yet."""
    if not os.path.exists(CONTENT_DIR):
        return []

    blogs = []
    for fname in sorted(os.listdir(CONTENT_DIR)):
        if fname.startswith("blog_") and fname.endswith(".md"):
            if fname not in processed:
                blogs.append(os.path.join(CONTENT_DIR, fname))
    return blogs


def process_blog(filepath: str) -> dict:
    """Full pipeline: blog file -> newsletters -> HubSpot marketing emails."""
    filename = os.path.basename(filepath)
    campaign_id = filename.replace("blog_", "").replace(".md", "")
    if not campaign_id.startswith("camp_"):
        campaign_id = f"camp_{campaign_id}"

    print(f"\n{'='*60}")
    print(f"  TRIGGER: New blog detected!")
    print(f"  File: {filename}")
    print(f"  Campaign: {campaign_id}")
    print(f"{'='*60}\n")

    blog_info = _extract_blog_info(filepath)
    if not blog_info:
        print("  Error: Could not parse blog file.")
        return {"error": "Could not parse blog"}

    print(f"  Blog title: \"{blog_info['title']}\"")

    from models.content import BlogPost
    blog = BlogPost(
        title=blog_info["title"],
        body=blog_info["body"],
        topic=blog_info["title"],
    )

    # Step 1: Generate newsletters
    print("\n  [1/4] Generating persona newsletters with AI...")
    newsletters = generate_newsletters(blog)
    for nl in newsletters:
        print(f"    [{nl.persona_name}] \"{nl.subject_line}\"")

    # Step 2: Save newsletter files
    print("\n  [2/4] Saving newsletters and syncing contacts...")
    for nl in newsletters:
        path = save_newsletter_markdown(campaign_id, nl.persona_id, nl.subject_line, nl.body)
        print(f"    Saved: {path}")

    synced = sync_all_contacts()
    print(f"    Contacts synced: {synced}")

    # Step 3: Distribute + log to CRM
    print("\n  [3/4] Distributing newsletters and logging to CRM...")
    send_results = send_newsletters(campaign_id, blog.title, newsletters)
    print(f"    Emails sent: {send_results['total_sent']}")

    # Step 4: Create HubSpot marketing emails
    print("\n  [4/4] Creating marketing emails in HubSpot...")
    hubspot_emails = []
    for nl in newsletters:
        paragraphs = nl.body.strip().split("\n\n")
        body_html = "".join(f"<p>{p.strip()}</p>" for p in paragraphs if p.strip())
        greeting_end = body_html.find("</p>") + 4
        body_html = f"<p>Hey {{{{ contact.firstname }}}},</p>{body_html[greeting_end:]}"

        hs_result = create_marketing_email(
            campaign_id=campaign_id,
            persona_id=nl.persona_id,
            persona_name=nl.persona_name,
            subject_line=nl.subject_line,
            body_html=body_html,
        )
        hs_id = hs_result.get("id", "error")
        hubspot_emails.append({"persona": nl.persona_id, "hubspot_email_id": hs_id})
        if "error" not in hs_result:
            print(f"    [{nl.persona_name}] HubSpot email ID: {hs_id}")
        else:
            print(f"    [{nl.persona_name}] Error creating HubSpot email")

    # Save campaign record
    campaign_dict = {
        "campaign_id": campaign_id,
        "topic": blog.topic,
        "blog_title": blog.title,
        "blog_body": blog.body,
        "blog_outline": blog.outline,
        "newsletters": [nl.model_dump() for nl in newsletters],
        "hubspot_emails": hubspot_emails,
        "contacts_synced": synced,
        "send_date": send_results["send_date"],
        "status": "sent",
    }
    save_campaign(campaign_dict)
    save_campaign_json(campaign_id, campaign_dict)

    print(f"\n{'='*60}")
    print(f"  Pipeline complete! Campaign: {campaign_id}")
    print(f"  {len(hubspot_emails)} marketing emails ready in HubSpot")
    print(f"{'='*60}\n")

    return campaign_dict


def watch(once: bool = False):
    """Watch for new blog files and trigger the newsletter pipeline."""
    print("NovaMind Blog Watcher")
    print(f"  Watching: {CONTENT_DIR}")
    print(f"  Poll interval: {POLL_INTERVAL}s")
    if once:
        print("  Mode: one-shot (process and exit)")
    else:
        print("  Mode: continuous (Ctrl+C to stop)")
    print()

    processed = _load_processed()

    while True:
        unprocessed = _find_unprocessed_blogs(processed)

        if unprocessed:
            for blog_path in unprocessed:
                filename = os.path.basename(blog_path)
                try:
                    process_blog(blog_path)
                except Exception as e:
                    print(f"  Error processing {filename}: {e}")
                processed.add(filename)
                _save_processed(processed)
        elif once:
            print("  No unprocessed blogs found.")

        if once:
            break

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="NovaMind Blog Watcher")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Process unprocessed blogs and exit (no continuous watching)",
    )
    args = parser.parse_args()
    watch(once=args.once)
