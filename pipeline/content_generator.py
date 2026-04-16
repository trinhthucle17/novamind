from __future__ import annotations

import base64
import json
import os
import re
from openai import OpenAI

import config
from models.content import BlogPost, Newsletter
from storage.file_store import CONTENT_IMAGES_DIR


def _get_client() -> OpenAI:
    return OpenAI(api_key=config.OPENAI_API_KEY)


def _call_llm(system_prompt: str, user_prompt: str) -> str:
    client = _get_client()
    response = client.chat.completions.create(
        model=config.LLM_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.7,
    )
    return response.choices[0].message.content or ""


def generate_blog_hero_image(topic: str, blog_title: str, campaign_id: str) -> str | None:
    """Generate a topic-based hero image and return markdown image path.

    Returns relative markdown path like `images/blog_hero_<campaign_id>.png`,
    or None if image generation is unavailable/fails.
    """
    filename = f"blog_hero_{campaign_id}.png"
    path = os.path.join(CONTENT_IMAGES_DIR, filename)
    if os.path.exists(path):
        return f"images/{filename}"
    if not config.OPENAI_API_KEY:
        return None

    prompt = (
        "Create a blog header illustration. "
        f"Topic: {topic}. "
        f"Title: {blog_title}. "
        "Style is STRICTLY cartoon or animated 2D only: flat or cel-shaded illustration, bold "
        "outlines, expressive simplified shapes — like a modern comic, a TV animation still frame, "
        "motion graphics style, or an animated explainer video keyframe. "
        "NOT allowed: photorealism, 3D renders, CGI, stock-photo look, painterly realism, "
        "or any lifelike human faces or hands. "
        "No text in the image, no logos, no watermarks, high contrast, suitable for a blog header."
    )

    try:
        client = _get_client()
        result = client.images.generate(
            model="gpt-image-1",
            prompt=prompt,
            size="1536x1024",
        )
        data_item = result.data[0] if result and result.data else None
        if not data_item:
            return None

        b64 = getattr(data_item, "b64_json", None)
        if not b64:
            return None

        os.makedirs(CONTENT_IMAGES_DIR, exist_ok=True)
        with open(path, "wb") as f:
            f.write(base64.b64decode(b64))
        return f"images/{filename}"
    except Exception:
        return None


def inject_hero_image_markdown(body: str, image_rel_path: str | None, alt_text: str) -> str:
    """Inject a hero image markdown block into blog body if missing."""
    text = (body or "").strip()
    if not text or not image_rel_path:
        return text
    if re.search(r"!\[[^\]]*\]\(images/[^\)]+\)", text):
        return text
    hero_md = f"![{alt_text}]({image_rel_path})"
    return f"{hero_md}\n\n{text}"


_BLOG_SYSTEM_PROMPT = """\
You are a specialized blog writer for NovaMind, an AI platform helping small creative agencies \
automate their daily workflows. Your audience is agency professionals — account managers, brand \
strategists, copywriters, designers, and project managers.

Voice: Friendly, empathetic, creative, and informative. Write like a smart peer who gets it, \
not a vendor pitching a product. Connect before you sell.

MANDATORY STRUCTURE (follow this exact order):
1. HOOK — Open with an industry in-joke or a relatable "that's me" moment. No definitions or \
stat dumps at the top.
2. THE REAL COST — Name where their time actually goes with real statistics (cite believable \
industry data). Be brief — they already live this pain.
3. THE SOLUTION — Show exactly what AI handles for them. Give a concrete time-savings estimate \
(e.g., "saves ~3 hours/week on status reports").
4. THE UNLOCK — What can they do with that reclaimed time? High-value creative work, strategic \
thinking, or simply leaving at 6pm. Make this aspirational and specific to agency life.
5. REASSURANCE — Close by affirming AI is their smart intern, not their replacement. Their \
judgment, relationships, and creativity are irreplaceable.

ENGAGEMENT RULE — Embed exactly ONE interactive element mid-post. Use one of:
- A "what type of agency person are you?" quiz (4 quick questions, 4 personality types)
- A relatable Monday checklist ("does this sound like your week?")
- A quick scenario selector

FORMAT: Markdown. 500–700 words. Section headings should feel editorial and punchy, never \
corporate (avoid "Introduction" or "Conclusion").

ORIGINALITY RULE — When past blog references are provided, you MUST study them and ensure \
your output is genuinely distinct. Specifically:
- Do NOT reuse or closely paraphrase any past title or section heading.
- Do NOT recycle the same opening scenario or metaphor (e.g., if a past post opened with a \
late-night Slack ping, do not open with another "working late" scene).
- Do NOT rehash the same illustrative examples, analogies, or narrative arc.
- You MAY address the same category of pain or benefit — but approach it from a completely \
fresh angle, with different framing, examples, and emotional entry point.
- Think: same audience, same value, entirely new story.

Tone check: Before finalizing, read as if you're an overloaded account manager on a Thursday \
afternoon. Would you keep reading? Would you feel understood, not sold to?\
"""


_NEWSLETTER_SYSTEM_PROMPT = """\
You are a newsletter copywriter for NovaMind, writing persona-targeted email promotions for \
blog posts about AI automation for creative agencies.

PERSONALIZATION RULES:
- Greet with [First Name] placeholder — NEVER use the persona group name as a greeting
- Reference the persona's specific daily tasks and friction points by role
- Lead with a stat or insight directly relevant to their role
- Keep it 150–250 words — concise, inviting, CTA-forward
- Subject line: under 60 characters, conversational and curiosity-driven (not clickbait)
- Sound like a helpful peer, not a mass-blast marketing email

TONE: Warm, direct, a little playful. Agency people have short attention spans and sharp BS \
detectors. Be real — do not oversell.

STRUCTURE:
1. Greeting: Hey [First Name],
2. One-sentence hook tied to the persona's specific role pain
3. Tease what the blog reveals (don't dump everything — make them click)
4. One role-relevant stat or time-savings number
5. CTA: a linked phrase like "Read the full post →" — no bare URLs

ORIGINALITY RULE — When past newsletter references are provided for this persona, you MUST \
ensure your output is genuinely distinct. Specifically:
- Do NOT reuse or closely paraphrase any past subject line.
- Do NOT open with the same hook angle or sentence structure as a past newsletter.
- Do NOT repeat the same stat, metaphor, or CTA phrasing.
- Keep the persona voice and role context — but find a fresh emotional entry point and \
a different specific pain or scenario to lead with.

Do NOT pitch NovaMind as a product to buy. The newsletter promotes the blog, and the blog \
builds the trust.\
"""


def _past_blog_digest(past_campaigns: list[dict]) -> str:
    """Build a compact reference block of past blog titles, hooks, and section headings."""
    if not past_campaigns:
        return ""
    lines = ["PAST BLOG POSTS — study these and do NOT repeat or paraphrase them:\n"]
    for i, c in enumerate(past_campaigns, 1):
        title = c.get("blog_title") or c.get("topic") or "Untitled"
        outline = c.get("outline") or []
        body = (c.get("blog_body") or "").strip()
        # Extract the hook: first non-image, non-empty paragraph
        hook = ""
        for para in body.split("\n"):
            para = para.strip()
            if para and not para.startswith("!") and not para.startswith("#"):
                hook = para[:180]
                break
        sections = ", ".join(outline) if outline else "N/A"
        lines.append(f"{i}. Title: \"{title}\"")
        lines.append(f"   Sections: {sections}")
        if hook:
            lines.append(f"   Opening hook: \"{hook}...\"")
        lines.append("")
    return "\n".join(lines)


def _past_newsletter_digest(past_campaigns: list[dict], persona_id: str) -> str:
    """Build a compact reference block of past subject lines and hooks for a persona."""
    if not past_campaigns:
        return ""
    entries = []
    for c in past_campaigns:
        for nl in c.get("newsletters") or []:
            if nl.get("persona_id") != persona_id:
                continue
            subject = nl.get("subject_line", "")
            body = (nl.get("body") or "").strip()
            hook = ""
            for line in body.split("\n"):
                line = line.strip()
                if line and not line.startswith("#") and "First Name" not in line:
                    hook = line[:150]
                    break
            entries.append((subject, hook))
    if not entries:
        return ""
    lines = [f"PAST NEWSLETTERS FOR THIS PERSONA — do NOT repeat or paraphrase these:\n"]
    for i, (subject, hook) in enumerate(entries, 1):
        lines.append(f"{i}. Subject: \"{subject}\"")
        if hook:
            lines.append(f"   Opening line: \"{hook}...\"")
        lines.append("")
    return "\n".join(lines)

def generate_blog_post(topic: str, past_campaigns: list[dict] | None = None) -> BlogPost:
    """Generate a blog outline and short-form draft from a topic.

    Uses the agency-blog-writer skill guidelines: empathetic hook-first structure,
    real time-savings data, one interactive element, and an AI-as-intern close.
    Pass past_campaigns so the LLM avoids repeating prior titles, hooks, and section headings.
    """
    past_digest = _past_blog_digest(past_campaigns or [])
    originality_block = (
        f"\n\n{past_digest}"
        if past_digest
        else "\n\n(No past campaigns on record — this is the first one.)"
    )

    user_prompt = f"""Write a blog post about: "{topic}"
{originality_block}
Return your response as valid JSON with these keys:
- "title": a compelling, editorial blog title (not clickbait, not corporate)
- "outline": a JSON array of 4-6 section headings that follow the mandatory structure
- "body": the full blog post in Markdown format, 500-700 words, including one interactive \
element (quiz, checklist, or scenario selector) embedded naturally mid-post

Respond ONLY with the JSON object, no extra text."""

    raw = _call_llm(_BLOG_SYSTEM_PROMPT, user_prompt)
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1]
        raw = raw.rsplit("```", 1)[0]

    data = json.loads(raw)
    return BlogPost(
        title=data["title"],
        outline=data["outline"],
        body=data["body"],
        topic=topic,
    )


def generate_newsletters(
    blog: BlogPost,
    past_campaigns: list[dict] | None = None,
) -> list[Newsletter]:
    """Generate three persona-targeted newsletter variants from a blog post.

    Uses the agency-blog-writer skill guidelines: role-specific hooks, real numbers,
    [First Name] placeholder, and a peer-to-peer tone that drives blog clicks.
    Pass past_campaigns so the LLM avoids repeating prior subject lines and opening hooks
    for each persona.
    """
    newsletters: list[Newsletter] = []

    for persona in config.PERSONAS:
        past_nl_digest = _past_newsletter_digest(past_campaigns or [], persona["id"])
        originality_block = (
            f"\n\n{past_nl_digest}"
            if past_nl_digest
            else "\n\n(No past newsletters for this persona — this is the first one.)"
        )

        user_prompt = f"""Create a short newsletter email promoting this blog post.

Blog title: {blog.title}
Blog summary: {blog.body[:300]}...

Target audience: {persona['name']} — {persona['description']}
Tone: {persona['tone']}
Format guidance: {persona['format']}
{originality_block}
IMPORTANT: The greeting MUST use "[First Name]" as a placeholder (e.g. "Hey [First Name]," \
or "Hello [First Name],"). Do NOT use the persona group name or any generic greeting. The \
placeholder will be replaced with the recipient's actual first name at send time.

Return your response as valid JSON with these keys:
- "subject_line": a compelling email subject line (under 60 characters, conversational)
- "body": the newsletter body in Markdown format (150-250 words), personalized to \
{persona['name']}, including one role-relevant stat and a CTA linking to the blog post.

Respond ONLY with the JSON object, no extra text."""

        raw = _call_llm(_NEWSLETTER_SYSTEM_PROMPT, user_prompt)
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1]
            raw = raw.rsplit("```", 1)[0]

        data = json.loads(raw)
        newsletters.append(
            Newsletter(
                persona_id=persona["id"],
                persona_name=persona["name"],
                subject_line=data["subject_line"],
                body=data["body"],
                blog_title=blog.title,
            )
        )

    return newsletters


def suggest_topics(past_campaigns: list[dict]) -> list[str]:
    """Use AI to suggest next blog topics based on past campaign performance."""
    if not past_campaigns:
        system_prompt = (
            "You are a content strategist for NovaMind, an AI startup that "
            "helps small creative agencies automate daily workflows."
        )
        user_prompt = (
            "Suggest 5 blog topic ideas about AI automation for creative agencies. "
            "Return a JSON array of strings, each being a topic title. "
            "Respond ONLY with the JSON array."
        )
        raw = _call_llm(system_prompt, user_prompt)
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1]
            raw = raw.rsplit("```", 1)[0]
        return json.loads(raw)

    campaign_summaries = []
    for c in past_campaigns[-5:]:
        campaign_summaries.append(
            f"- Topic: {c.get('topic', 'N/A')}, "
            f"Open rate: {c.get('open_rate', 'N/A')}%, "
            f"Click rate: {c.get('click_rate', 'N/A')}%, "
            f"Best persona: {c.get('best_persona', 'N/A')}"
        )

    system_prompt = (
        "You are a data-driven content strategist for NovaMind, an AI startup "
        "that helps small creative agencies automate daily workflows."
    )
    user_prompt = f"""Based on these past campaign results, suggest 5 new blog topics
that are likely to perform well:

{chr(10).join(campaign_summaries)}

Consider what topics and angles drove the best engagement.
Return a JSON array of strings, each being a topic title.
Respond ONLY with the JSON array."""

    raw = _call_llm(system_prompt, user_prompt)
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1]
        raw = raw.rsplit("```", 1)[0]
    return json.loads(raw)


def recommend_topics_from_engagement(
    portfolio_digest: str,
    past_topics: list[str],
    past_blog_titles: list[str],
    n: int = 5,
) -> list[str]:
    """LLM: new blog topics from engagement data — not paraphrases of past lines."""
    if not config.OPENAI_API_KEY:
        return []

    topics_block = "\n".join(f"- {t}" for t in past_topics) if past_topics else "(none)"
    titles_block = "\n".join(f"- {t}" for t in past_blog_titles if t) if past_blog_titles else "(none)"

    system_prompt = """You are a senior content strategist for NovaMind, an AI product that helps \
small creative agencies automate everyday workflows. Your readers are account managers, brand \
strategists, designers, and producers — smart, cynical about generic AI hype, and short on time.

You receive real newsletter/blog engagement metrics (opens, clicks, unsubs by persona) and a list \
of topics that already exist. Your job is to recommend genuinely NEW blog topic ideas.

Hard rules:
- Output must be a JSON array of strings only. No markdown, no keys, no commentary.
- Each string is one concrete blog topic / working title (specific, editorial, not corporate).
- Do NOT paraphrase, shorten, or lightly edit any past topic or past blog title. If it would look \
like the same story in a new coat of paint, discard it and think of a different angle.
- Use the metrics: lean into angles and audience pains that align with personas and patterns that \
performed well (clicks/opens); avoid repeating themes that clearly underperformed unless you pivot \
to a sharply different premise.
- Topics must be NEW territory: different problem, format, or hook — not a sequel title to an \
existing post unless the metrics justify a "opposite take" and you make that contrast obvious in \
the wording.
- Keep each topic under ~120 characters when possible."""

    user_prompt = f"""## Engagement and portfolio data
{portfolio_digest}

## Past topics (do not reuse or near-duplicate)
{topics_block}

## Past blog titles (do not reuse or near-duplicate)
{titles_block}

Recommend exactly {n} new blog topics as a JSON array of strings, e.g. ["topic one", "topic two"].
Respond ONLY with the JSON array."""

    raw = _call_llm(system_prompt, user_prompt)
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1]
        raw = raw.rsplit("```", 1)[0]
    data = json.loads(raw)
    if not isinstance(data, list):
        return []
    out = [str(x).strip() for x in data if str(x).strip()]
    return out[:n]


def recommend_topics_from_engagement(
    portfolio_digest: str,
    past_topics: list[str],
    past_blog_titles: list[str],
    n: int = 5,
) -> list[str]:
    """LLM: new blog topics from engagement data — not paraphrases of past lines."""
    if not config.OPENAI_API_KEY:
        return []

    topics_block = "\n".join(f"- {t}" for t in past_topics) if past_topics else "(none)"
    titles_block = "\n".join(f"- {t}" for t in past_blog_titles if t) if past_blog_titles else "(none)"

    system_prompt = """You are a senior content strategist for NovaMind, an AI product that helps \
small creative agencies automate everyday workflows. Your readers are account managers, brand \
strategists, designers, and producers — smart, cynical about generic AI hype, and short on time.

You receive real newsletter/blog engagement metrics (opens, clicks, unsubs by persona) and a list \
of topics that already exist. Your job is to recommend genuinely NEW blog topic ideas.

Hard rules:
- Output must be a JSON array of strings only. No markdown, no keys, no commentary.
- Each string is one concrete blog topic / working title (specific, editorial, not corporate).
- Do NOT paraphrase, shorten, or lightly edit any past topic or past blog title. If it would look \
like the same story in a new coat of paint, discard it and think of a different angle.
- Use the metrics: lean into angles and audience pains that align with personas and patterns that \
performed well (clicks/opens); avoid repeating themes that clearly underperformed unless you pivot \
to a sharply different premise.
- Topics must be NEW territory: different problem, format, or hook — not a sequel title to an \
existing post unless the metrics justify a "opposite take" and you make that contrast obvious in \
the wording.
- Keep each topic under ~120 characters when possible."""

    user_prompt = f"""## Engagement and portfolio data
{portfolio_digest}

## Past topics (do not reuse or near-duplicate)
{topics_block}

## Past blog titles (do not reuse or near-duplicate)
{titles_block}

Recommend exactly {n} new blog topics as a JSON array of strings, e.g. ["topic one", "topic two"].
Respond ONLY with the JSON array."""

    raw = _call_llm(system_prompt, user_prompt)
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1]
        raw = raw.rsplit("```", 1)[0]
    data = json.loads(raw)
    if not isinstance(data, list):
        return []
    out = [str(x).strip() for x in data if str(x).strip()]
    return out[:n]
