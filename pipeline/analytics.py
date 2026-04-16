from __future__ import annotations

import json
import random

from openai import OpenAI

import config
from models.metrics import CampaignMetrics, PersonaMetrics
from storage.database import save_metrics, save_ai_summary, get_historical_metrics


def _get_client() -> OpenAI:
    return OpenAI(api_key=config.OPENAI_API_KEY)


def simulate_engagement(campaign_id: str, blog_title: str, send_results: dict) -> CampaignMetrics:
    """
    Generate realistic simulated engagement metrics for each persona.
    Different personas have different typical engagement patterns.
    """
    engagement_profiles = {
        "creative_professionals": {
            "open_rate_range": (0.35, 0.50),
            "click_rate_range": (0.05, 0.12),
            "unsub_rate_range": (0.001, 0.005),
        },
        "brand_strategists": {
            "open_rate_range": (0.30, 0.45),
            "click_rate_range": (0.03, 0.08),
            "unsub_rate_range": (0.002, 0.008),
        },
        "account_managers": {
            "open_rate_range": (0.25, 0.40),
            "click_rate_range": (0.04, 0.10),
            "unsub_rate_range": (0.001, 0.003),
        },
    }

    persona_metrics_list: list[PersonaMetrics] = []

    for segment in send_results.get("segments", []):
        persona_id = segment["persona"]
        recipients = segment["recipients"]
        profile = engagement_profiles.get(persona_id, engagement_profiles["creative_professionals"])

        open_rate = random.uniform(*profile["open_rate_range"])
        click_rate = random.uniform(*profile["click_rate_range"])
        unsub_rate = random.uniform(*profile["unsub_rate_range"])

        pm = PersonaMetrics(
            persona_id=persona_id,
            persona_name=segment["persona_name"],
            recipients=recipients,
            opens=int(recipients * open_rate),
            clicks=int(recipients * click_rate),
            unsubscribes=max(0, int(recipients * unsub_rate)),
        )
        persona_metrics_list.append(pm)

    metrics = CampaignMetrics(
        campaign_id=campaign_id,
        blog_title=blog_title,
        send_date=send_results.get("send_date", ""),
        persona_metrics=persona_metrics_list,
    )

    save_metrics(
        campaign_id,
        [pm.model_dump() for pm in persona_metrics_list],
    )

    return metrics


def generate_performance_summary(metrics: CampaignMetrics) -> str:
    """Use AI to produce a plain-English performance summary with recommendations."""
    metrics_text = []
    for pm in metrics.persona_metrics:
        metrics_text.append(
            f"- {pm.persona_name}: {pm.recipients} recipients, "
            f"{pm.open_rate}% open rate, {pm.click_rate}% click rate, "
            f"{pm.unsubscribe_rate}% unsubscribe rate"
        )

    prompt = f"""Analyze this email campaign performance and write a brief summary
(3-5 sentences) with specific, actionable recommendations.

Campaign: "{metrics.blog_title}"
Overall: {metrics.total_recipients} recipients, {metrics.overall_open_rate}% open rate, {metrics.overall_click_rate}% click rate

Breakdown by audience segment:
{chr(10).join(metrics_text)}

Include:
1. Which segment performed best and why (speculate based on the persona)
2. Which segment needs improvement
3. 2-3 specific recommendations for the next campaign

Write in a professional but conversational tone. Be specific with numbers."""

    client = _get_client()
    response = client.chat.completions.create(
        model=config.LLM_MODEL,
        messages=[
            {
                "role": "system",
                "content": "You are a marketing analytics expert providing campaign performance insights.",
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0.5,
    )

    summary = response.choices[0].message.content or ""
    return summary


def generate_topic_suggestions(metrics: CampaignMetrics) -> list[str]:
    """Suggest next blog topics based on campaign performance trends."""
    historical = get_historical_metrics()

    history_text = ""
    if historical:
        seen = set()
        for row in historical[:20]:
            key = row["campaign_id"]
            if key not in seen:
                seen.add(key)
                recipients = row.get("recipients", 0)
                opens = row.get("opens", 0)
                rate = round(opens / max(recipients, 1) * 100, 1)
                history_text += f"- \"{row.get('topic', 'N/A')}\" (open rate: {rate}%)\n"

    prompt = f"""Based on the latest campaign and historical data, suggest 5 blog topic ideas
for NovaMind (an AI startup helping creative agencies automate workflows).

Latest campaign: "{metrics.blog_title}"
- Best performing segment: {_best_segment(metrics)}

{f"Past campaigns:{chr(10)}{history_text}" if history_text else "This is the first campaign."}

Return a JSON array of 5 topic strings. Each should be a specific, compelling blog title.
Respond ONLY with the JSON array, no extra text."""

    client = _get_client()
    response = client.chat.completions.create(
        model=config.LLM_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.8,
    )

    raw = response.choices[0].message.content or "[]"
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1]
        raw = raw.rsplit("```", 1)[0]

    try:
        topics = json.loads(raw)
    except json.JSONDecodeError:
        topics = ["AI Automation Trends for Creative Agencies"]

    save_ai_summary(metrics.campaign_id, metrics.ai_summary, topics)

    return topics


def _best_segment(metrics: CampaignMetrics) -> str:
    if not metrics.persona_metrics:
        return "N/A"
    best = max(metrics.persona_metrics, key=lambda p: p.click_rate)
    return f"{best.persona_name} ({best.click_rate}% click rate)"
