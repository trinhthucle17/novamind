from __future__ import annotations

import json
from openai import OpenAI

import config
from models.content import BlogPost, Newsletter


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


def generate_blog_post(topic: str) -> BlogPost:
    """Generate a blog outline and short-form draft from a topic."""
    system_prompt = (
        "You are a content strategist for NovaMind, an AI startup that helps "
        "small creative agencies automate their daily workflows (think Notion + "
        "Zapier + ChatGPT combined). Write in a friendly, authoritative tone."
    )
    user_prompt = f"""Write a blog post about: "{topic}"

Return your response as valid JSON with these keys:
- "title": a compelling blog title
- "outline": a JSON array of 4-6 section headings
- "body": the full blog post in Markdown format, 400-600 words

Respond ONLY with the JSON object, no extra text."""

    raw = _call_llm(system_prompt, user_prompt)
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


def generate_newsletters(blog: BlogPost) -> list[Newsletter]:
    """Generate three persona-targeted newsletter variants from a blog post."""
    newsletters: list[Newsletter] = []

    for persona in config.PERSONAS:
        system_prompt = (
            "You are a marketing copywriter for NovaMind, an AI startup that "
            "helps small creative agencies automate their daily workflows. "
            "Write newsletter copy that promotes a blog post."
        )
        user_prompt = f"""Create a short newsletter email promoting this blog post.

Blog title: {blog.title}
Blog summary: {blog.body[:300]}...

Target audience: {persona['name']} — {persona['description']}
Tone: {persona['tone']}

Return your response as valid JSON with these keys:
- "subject_line": a compelling email subject line (under 60 characters)
- "body": the newsletter body in Markdown format (150-250 words). Include a call-to-action linking to the blog post.

Respond ONLY with the JSON object, no extra text."""

        raw = _call_llm(system_prompt, user_prompt)
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
