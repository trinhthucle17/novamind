from __future__ import annotations

import base64
import json
import mimetypes
import os
import re
import shutil
from datetime import datetime

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
CONTENT_DIR = os.path.join(DATA_DIR, "content")
CAMPAIGNS_DIR = os.path.join(DATA_DIR, "campaigns")
CONTENT_IMAGES_DIR = os.path.join(CONTENT_DIR, "images")
LOGO_SOURCE_PATH = os.path.join(DATA_DIR, "logo.png")
LOGO_CONTENT_PATH = os.path.join(CONTENT_IMAGES_DIR, "logo.png")

os.makedirs(CONTENT_DIR, exist_ok=True)
os.makedirs(CAMPAIGNS_DIR, exist_ok=True)
os.makedirs(CONTENT_IMAGES_DIR, exist_ok=True)


def ensure_logo_asset() -> str | None:
    """Ensure `data/content/images/logo.png` exists from `data/logo.png`."""
    if not os.path.exists(LOGO_SOURCE_PATH):
        return None
    if not os.path.exists(LOGO_CONTENT_PATH):
        shutil.copy2(LOGO_SOURCE_PATH, LOGO_CONTENT_PATH)
    return LOGO_CONTENT_PATH


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
    """Save a newsletter variant under data/campaigns/ (canonical source for the UI)."""
    filename = f"newsletter_{campaign_id}_{persona_id}.md"
    content = f"""# Newsletter: {subject_line}

**Persona:** {persona_id}
**Campaign:** {campaign_id}

---

{body}
"""
    filepath = os.path.join(CAMPAIGNS_DIR, filename)
    with open(filepath, "w") as f:
        f.write(content)
    return filepath


_MD_IMAGE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")


def resolve_markdown_images_for_streamlit(markdown: str, base_dir: str | None = None) -> str:
    """Embed local images as data URLs so Streamlit markdown can render them.

    Paths in markdown are resolved relative to ``base_dir`` (defaults to
    ``data/content``), matching how blog posts reference ``images/...``.
    """
    base = os.path.abspath(base_dir or CONTENT_DIR)

    def repl(match: re.Match) -> str:
        alt, url = match.group(1), match.group(2).strip()
        if url.startswith(("http://", "https://", "data:")):
            return match.group(0)
        abs_path = os.path.normpath(os.path.join(base, url))
        if not abs_path.startswith(base) or not os.path.isfile(abs_path):
            return match.group(0)
        mime, _ = mimetypes.guess_type(abs_path)
        mime = mime or "application/octet-stream"
        with open(abs_path, "rb") as f:
            b64 = base64.standard_b64encode(f.read()).decode("ascii")
        return f"![{alt}](data:{mime};base64,{b64})"

    return _MD_IMAGE.sub(repl, markdown)


def get_logo_data_uri() -> str | None:
    """Return logo image as a data URI for HTML emails."""
    path = ensure_logo_asset()
    if not path:
        return None
    mime, _ = mimetypes.guess_type(path)
    mime = mime or "application/octet-stream"
    with open(path, "rb") as f:
        b64 = base64.standard_b64encode(f.read()).decode("ascii")
    return f"data:{mime};base64,{b64}"


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
