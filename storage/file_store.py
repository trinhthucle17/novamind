from __future__ import annotations

import json
import os
from datetime import datetime

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
CONTENT_DIR = os.path.join(DATA_DIR, "content")
CAMPAIGNS_DIR = os.path.join(DATA_DIR, "campaigns")

os.makedirs(CONTENT_DIR, exist_ok=True)
os.makedirs(CAMPAIGNS_DIR, exist_ok=True)


def save_blog_markdown(campaign_id: str, title: str, outline: list[str], body: str) -> str:
    """Save a blog post as a Markdown file and return the file path."""
    filename = f"blog_{campaign_id}.md"
    filepath = os.path.join(CONTENT_DIR, filename)

    outline_md = "\n".join(f"- {item}" for item in outline)
    content = f"""# {title}

## Outline

{outline_md}

---

{body}
"""
    with open(filepath, "w") as f:
        f.write(content)
    return filepath


def save_newsletter_markdown(campaign_id: str, persona_id: str, subject_line: str, body: str) -> str:
    """Save a newsletter variant as a Markdown file and return the file path."""
    filename = f"newsletter_{campaign_id}_{persona_id}.md"
    filepath = os.path.join(CONTENT_DIR, filename)

    content = f"""# Newsletter: {subject_line}

**Persona:** {persona_id}
**Campaign:** {campaign_id}

---

{body}
"""
    with open(filepath, "w") as f:
        f.write(content)
    return filepath


def save_campaign_json(campaign_id: str, campaign_data: dict) -> str:
    """Save the full campaign data as a JSON file and return the file path."""
    filename = f"campaign_{campaign_id}.json"
    filepath = os.path.join(CAMPAIGNS_DIR, filename)

    with open(filepath, "w") as f:
        json.dump(campaign_data, f, indent=2, default=str)
    return filepath


def load_contacts() -> list[dict]:
    """Load the mock contact list from data/contacts.json."""
    contacts_path = os.path.join(DATA_DIR, "contacts.json")
    with open(contacts_path, "r") as f:
        return json.load(f)
