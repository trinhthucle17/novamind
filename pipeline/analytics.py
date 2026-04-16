from __future__ import annotations

import json
import random
import re
from datetime import datetime

from openai import OpenAI

import config
from models.metrics import CampaignMetrics, HubSpotEmailStats, PersonaMetrics
from pipeline.crm_manager import fetch_email_statistics
from storage.database import (
    save_metrics, save_ai_summary, get_historical_metrics,
    save_hubspot_stats, get_hubspot_stats, get_hubspot_stats_latest,
)


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
    """Create a data-backed summary and lightweight recommendations.

    The recommendation engine is deterministic and built only from real campaign
    metrics in SQLite. If OpenAI is available, we optionally rewrite the summary
    for tone using strict prompt constraints to avoid hallucinated numbers.
    """
    baselines = _historical_persona_baselines(metrics)
    recommendations = _build_lightweight_recommendations(metrics, baselines)
    facts = _build_fact_pack(metrics, baselines, recommendations)

    guarded_summary = _rewrite_summary_with_guardrails(facts)
    if guarded_summary:
        return guarded_summary

    return _deterministic_summary_text(facts)


def _historical_persona_baselines(metrics: CampaignMetrics) -> dict[str, dict]:
    """Build persona-level historical baselines from stored DB metrics."""
    rows = get_historical_metrics()
    baselines: dict[str, dict] = {}
    for row in rows:
        if row.get("campaign_id") == metrics.campaign_id:
            continue
        persona_id = row.get("persona_id", "")
        if not persona_id:
            continue
        if persona_id not in baselines:
            baselines[persona_id] = {
                "persona_name": row.get("persona_name", persona_id),
                "recipients": 0,
                "opens": 0,
                "clicks": 0,
                "unsubscribes": 0,
            }
        baselines[persona_id]["recipients"] += row.get("recipients", 0)
        baselines[persona_id]["opens"] += row.get("opens", 0)
        baselines[persona_id]["clicks"] += row.get("clicks", 0)
        baselines[persona_id]["unsubscribes"] += row.get("unsubscribes", 0)

    for pid, data in baselines.items():
        recipients = max(data["recipients"], 1)
        data["open_rate"] = round(data["opens"] / recipients * 100, 2)
        data["click_rate"] = round(data["clicks"] / recipients * 100, 2)
        data["unsubscribe_rate"] = round(data["unsubscribes"] / recipients * 100, 2)
        baselines[pid] = data
    return baselines


def _build_lightweight_recommendations(
    metrics: CampaignMetrics,
    baselines: dict[str, dict],
) -> list[str]:
    """Deterministic recommendations using only real metrics and DB baselines."""
    if not metrics.persona_metrics:
        return ["No persona metrics available; run a campaign first to generate recommendations."]

    best_click = max(metrics.persona_metrics, key=lambda p: p.click_rate)
    lowest_open = min(metrics.persona_metrics, key=lambda p: p.open_rate)
    highest_unsub = max(metrics.persona_metrics, key=lambda p: p.unsubscribe_rate)

    recs = [
        (
            f"Scale what worked for {best_click.persona_name}: this segment led click rate at "
            f"{best_click.click_rate}% (campaign average: {metrics.overall_click_rate}%)."
        ),
        (
            f"Test a new subject line for {lowest_open.persona_name}: this segment had the lowest "
            f"open rate at {lowest_open.open_rate}%."
        ),
    ]

    if highest_unsub.unsubscribe_rate > 0:
        recs.append(
            f"Reduce send friction for {highest_unsub.persona_name}: unsubscribe rate was "
            f"{highest_unsub.unsubscribe_rate}% in this campaign."
        )
    else:
        recs.append("Unsubscribe rate is 0.0% across segments; keep the same send cadence.")

    # Add one trend-aware line if historical baseline exists for best-click segment.
    baseline = baselines.get(best_click.persona_id)
    if baseline:
        delta = round(best_click.click_rate - baseline.get("click_rate", 0.0), 2)
        direction = "up" if delta >= 0 else "down"
        recs.append(
            f"Vs historical baseline for {best_click.persona_name}, click rate is {direction} "
            f"{abs(delta)} pts ({best_click.click_rate}% vs {baseline.get('click_rate', 0.0)}%)."
        )
    else:
        recs.append("No prior campaign baseline available yet; keep collecting data for trend comparisons.")

    return recs[:4]


def _build_fact_pack(
    metrics: CampaignMetrics,
    baselines: dict[str, dict],
    recommendations: list[str],
) -> dict:
    persona_facts = []
    for p in metrics.persona_metrics:
        base = baselines.get(p.persona_id)
        persona_facts.append({
            "persona_id": p.persona_id,
            "persona_name": p.persona_name,
            "recipients": p.recipients,
            "opens": p.opens,
            "clicks": p.clicks,
            "unsubscribes": p.unsubscribes,
            "open_rate": p.open_rate,
            "click_rate": p.click_rate,
            "unsubscribe_rate": p.unsubscribe_rate,
            "historical_open_rate": base.get("open_rate") if base else None,
            "historical_click_rate": base.get("click_rate") if base else None,
            "historical_unsubscribe_rate": base.get("unsubscribe_rate") if base else None,
        })

    return {
        "campaign_id": metrics.campaign_id,
        "blog_title": metrics.blog_title,
        "total_recipients": metrics.total_recipients,
        "overall_open_rate": metrics.overall_open_rate,
        "overall_click_rate": metrics.overall_click_rate,
        "persona_facts": persona_facts,
        "recommendations": recommendations,
    }


def _deterministic_summary_text(facts: dict) -> str:
    """Fallback summary that never uses generated numbers."""
    persona_lines = []
    for p in facts.get("persona_facts", []):
        persona_lines.append(
            f"- {p['persona_name']}: {p['recipients']} recipients, "
            f"{p['open_rate']}% open, {p['click_rate']}% click, "
            f"{p['unsubscribe_rate']}% unsubscribe."
        )

    sections = [
        (
            f'Campaign "{facts.get("blog_title", "")}" reached '
            f'{facts.get("total_recipients", 0)} recipients with '
            f'{facts.get("overall_open_rate", 0.0)}% open rate and '
            f'{facts.get("overall_click_rate", 0.0)}% click rate.'
        ),
        "Segment breakdown:",
        "\n".join(persona_lines) if persona_lines else "- No segment metrics available.",
        "Recommendations:",
    ]
    sections.extend(f"- {r}" for r in facts.get("recommendations", []))
    return "\n".join(sections)


def _allowed_number_tokens(facts: dict) -> set[str]:
    tokens: set[str] = set()

    def collect(value):
        if isinstance(value, dict):
            for v in value.values():
                collect(v)
        elif isinstance(value, list):
            for v in value:
                collect(v)
        elif isinstance(value, (int, float)):
            tokens.add(str(int(value)) if isinstance(value, int) else str(value))
            if isinstance(value, float):
                tokens.add(f"{value:.1f}")
                tokens.add(f"{value:.2f}")
            tokens.add(f"{value}%")
            if isinstance(value, float):
                tokens.add(f"{value:.1f}%")
                tokens.add(f"{value:.2f}%")

    collect(facts)
    # Common safe numerics that may appear in phrasing
    tokens.update({"0", "1", "2", "3", "4", "5"})
    return tokens


def _uses_only_allowed_numbers(text: str, allowed: set[str]) -> bool:
    found = re.findall(r"\d+(?:\.\d+)?%?", text)
    for token in found:
        if token not in allowed:
            return False
    return True


def _rewrite_summary_with_guardrails(facts: dict) -> str | None:
    """Optional LLM rewrite with strict anti-hallucination constraints."""
    if not config.OPENAI_API_KEY:
        return None

    system_prompt = (
        "You are a factual analytics editor. Use ONLY numbers and facts from the input JSON. "
        "Do not speculate, do not infer causes, and do not invent benchmarks. "
        "If a fact is missing, say 'insufficient data'. Return strict JSON only."
    )
    user_prompt = f"""Rewrite this campaign summary using ONLY the provided facts.

Facts JSON:
{json.dumps(facts, indent=2)}

Return JSON with:
- "summary": 3-5 concise sentences, factual only.
- "recommendations": copy the recommendations exactly as provided in facts.recommendations.

Rules:
1) Do not add any new numbers.
2) Do not modify recommendation text.
3) Keep professional and concise tone.
"""

    try:
        client = _get_client()
        response = client.chat.completions.create(
            model=config.LLM_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.0,
        )
        raw = (response.choices[0].message.content or "").strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1]
            raw = raw.rsplit("```", 1)[0]
        data = json.loads(raw)
        summary = data.get("summary", "").strip()
        recommendations = data.get("recommendations", [])

        if not summary or recommendations != facts.get("recommendations", []):
            return None
        if not _uses_only_allowed_numbers(summary, _allowed_number_tokens(facts)):
            return None

        lines = [summary, "Recommendations:"]
        lines.extend(f"- {r}" for r in recommendations)
        return "\n".join(lines)
    except Exception:
        return None


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


def fetch_hubspot_metrics(campaign_id: str, hubspot_emails: list[dict]) -> list[HubSpotEmailStats]:
    """Fetch real newsletter performance data from HubSpot and store for historical comparison.

    Args:
        campaign_id: The NovaMind campaign ID (e.g. "camp_20260414_051441")
        hubspot_emails: List of dicts with "persona" and "hubspot_email_id" keys
            (from the campaign JSON's "hubspot_emails" field)

    Returns:
        List of HubSpotEmailStats with real open/click/unsubscribe data.
    """
    persona_labels = {
        "creative_professionals": "Creative Professionals",
        "brand_strategists": "Brand Strategists",
        "account_managers": "Account Managers",
    }

    email_ids = [str(e["hubspot_email_id"]) for e in hubspot_emails]
    persona_map = {str(e["hubspot_email_id"]): e["persona"] for e in hubspot_emails}

    print(f"\n  Fetching HubSpot stats for {len(email_ids)} emails...")
    raw_stats = fetch_email_statistics(email_ids)

    now = datetime.utcnow().isoformat()
    stats_list: list[HubSpotEmailStats] = []
    db_rows: list[dict] = []

    for eid, data in raw_stats.items():
        persona_id = persona_map.get(eid, "unknown")
        persona_name = persona_labels.get(persona_id, persona_id)

        stat = HubSpotEmailStats(
            campaign_id=campaign_id,
            hubspot_email_id=eid,
            persona_id=persona_id,
            persona_name=persona_name,
            sent=data["sent"],
            delivered=data["delivered"],
            opens=data["opens"],
            clicks=data["clicks"],
            unsubscribes=data["unsubscribes"],
            bounces=data["bounces"],
            open_rate=round(data["open_rate"], 2),
            click_rate=round(data["click_rate"], 2),
            unsubscribe_rate=round(data["unsubscribe_rate"], 2),
            bounce_rate=round(data["bounce_rate"], 2),
            fetched_at=now,
        )
        stats_list.append(stat)
        db_rows.append(stat.model_dump())

    save_hubspot_stats(db_rows)

    return stats_list


def print_hubspot_stats(stats: list[HubSpotEmailStats], campaign_id: str):
    """Pretty-print fetched HubSpot performance data."""
    print(f"\n{'='*65}")
    print(f"  HubSpot Newsletter Performance — {campaign_id}")
    print(f"{'='*65}")
    print(f"  {'Segment':<28} {'Sent':>5} {'Opens':>6} {'Open%':>7} {'Click%':>7} {'Unsub%':>7}")
    print(f"  {'-'*62}")

    total_sent = total_opens = total_clicks = total_unsubs = 0
    for s in stats:
        print(f"  {s.persona_name:<28} {s.sent:>5} {s.opens:>6} {s.open_rate:>6.1f}% {s.click_rate:>6.1f}% {s.unsubscribe_rate:>6.1f}%")
        total_sent += s.sent
        total_opens += s.opens
        total_clicks += s.clicks
        total_unsubs += s.unsubscribes

    overall_open = round(total_opens / max(total_sent, 1) * 100, 2)
    overall_click = round(total_clicks / max(total_sent, 1) * 100, 2)
    overall_unsub = round(total_unsubs / max(total_sent, 1) * 100, 2)
    print(f"  {'-'*62}")
    print(f"  {'OVERALL':<28} {total_sent:>5} {total_opens:>6} {overall_open:>6.1f}% {overall_click:>6.1f}% {overall_unsub:>6.1f}%")
    print(f"{'='*65}")
    print(f"  Fetched at: {stats[0].fetched_at if stats else 'N/A'}")
    print(f"  Data stored to SQLite for historical comparison.\n")


def show_historical_comparison(campaign_id: str):
    """Display historical stats snapshots for a campaign, showing trends."""
    all_stats = get_hubspot_stats(campaign_id)
    if not all_stats:
        print(f"  No historical data found for {campaign_id}")
        return

    snapshots: dict[str, list[dict]] = {}
    for row in all_stats:
        ts = row["fetched_at"]
        snapshots.setdefault(ts, []).append(row)

    timestamps = sorted(snapshots.keys())
    print(f"\n  Historical snapshots for {campaign_id}: {len(timestamps)} fetch(es)")
    print(f"  {'-'*50}")
    for ts in timestamps:
        rows = snapshots[ts]
        total_sent = sum(r["sent"] for r in rows)
        total_opens = sum(r["opens"] for r in rows)
        total_clicks = sum(r["clicks"] for r in rows)
        total_unsubs = sum(r["unsubscribes"] for r in rows)
        o_rate = round(total_opens / max(total_sent, 1) * 100, 1)
        c_rate = round(total_clicks / max(total_sent, 1) * 100, 1)
        u_rate = round(total_unsubs / max(total_sent, 1) * 100, 1)
        print(f"  {ts}  |  Open: {o_rate}%  Click: {c_rate}%  Unsub: {u_rate}%")
    print()


def _best_segment(metrics: CampaignMetrics) -> str:
    if not metrics.persona_metrics:
        return "N/A"
    best = max(metrics.persona_metrics, key=lambda p: p.click_rate)
    return f"{best.persona_name} ({best.click_rate}% click rate)"
