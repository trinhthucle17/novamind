"""Engagement digest + LLM topic recommendations (no static topic bank)."""

from __future__ import annotations

from collections import defaultdict
from statistics import median
from typing import Any

import config
from pipeline.content_generator import recommend_topics_from_engagement
from storage.database import get_historical_metrics


def _weighted_rates(rows: list[dict]) -> tuple[float, float, float]:
    tw = 0.0
    o = c = u = 0.0
    for r in rows:
        rec = max(int(r.get("recipients") or 0), 1)
        w = float(rec)
        tw += w
        o += w * (int(r.get("opens") or 0) / rec * 100.0)
        c += w * (int(r.get("clicks") or 0) / rec * 100.0)
        u += w * (int(r.get("unsubscribes") or 0) / rec * 100.0)
    if tw <= 0:
        return 0.0, 0.0, 0.0
    return o / tw, c / tw, u / tw


def _engagement_score(open_pct: float, click_pct: float, unsub_pct: float) -> float:
    return 0.35 * open_pct + 0.55 * click_pct - 0.5 * unsub_pct


def build_engagement_digest() -> dict[str, Any] | None:
    """Structured text for the LLM plus past topic/title lists. None if no metric rows."""
    rows = get_historical_metrics()
    if not rows:
        return None

    by_cid: dict[str, dict[str, Any]] = {}
    for r in rows:
        cid = r["campaign_id"]
        if cid not in by_cid:
            by_cid[cid] = {
                "campaign_id": cid,
                "topic": (r.get("topic") or "").strip() or "Untitled",
                "blog_title": (r.get("blog_title") or "").strip(),
                "send_date": r.get("send_date") or "",
                "rows": [],
            }
        by_cid[cid]["rows"].append(r)

    campaigns = list(by_cid.values())
    campaigns.sort(key=lambda x: (x.get("send_date") or ""), reverse=True)

    past_topics: list[str] = []
    past_titles: list[str] = []
    seen_t: set[str] = set()
    seen_ti: set[str] = set()
    for c in campaigns:
        t = c["topic"]
        if t and t.lower() not in seen_t:
            seen_t.add(t.lower())
            past_topics.append(t)
        bt = c.get("blog_title") or ""
        if bt and bt.lower() not in seen_ti:
            seen_ti.add(bt.lower())
            past_titles.append(bt)

    # Portfolio-level persona rollups
    persona_keyed: dict[str, dict[str, float]] = defaultdict(
        lambda: {"recipients": 0.0, "opens": 0.0, "clicks": 0.0, "unsubs": 0.0, "name": ""}
    )
    for r in rows:
        pid = r.get("persona_id") or ""
        if not pid:
            continue
        rec = max(int(r.get("recipients") or 0), 1)
        persona_keyed[pid]["recipients"] += rec
        persona_keyed[pid]["opens"] += int(r.get("opens") or 0)
        persona_keyed[pid]["clicks"] += int(r.get("clicks") or 0)
        persona_keyed[pid]["unsubs"] += int(r.get("unsubscribes") or 0)
        if not persona_keyed[pid]["name"]:
            persona_keyed[pid]["name"] = (r.get("persona_name") or pid).strip()

    persona_lines = []
    for pid, agg in sorted(persona_keyed.items()):
        r = max(agg["recipients"], 1.0)
        o_pct = agg["opens"] / r * 100.0
        c_pct = agg["clicks"] / r * 100.0
        u_pct = agg["unsubs"] / r * 100.0
        sc = _engagement_score(o_pct, c_pct, u_pct)
        persona_lines.append(
            f"- **{agg['name']}** ({pid}): weighted **{o_pct:.1f}%** open, **{c_pct:.1f}%** click, "
            f"**{u_pct:.2f}%** unsub; engagement index **{sc:.2f}** (higher is better)."
        )

    o_pf, c_pf, u_pf = _weighted_rates(rows)
    pf_score = _engagement_score(o_pf, c_pf, u_pf)
    lines = [
        f"- **Portfolio (all segments, recipient-weighted):** **{o_pf:.1f}%** open, "
        f"**{c_pf:.1f}%** click, **{u_pf:.2f}%** unsub; index **{pf_score:.2f}**.",
        "",
        "### Persona rollups (who tends to engage across all sends)",
        *persona_lines,
        "",
        "### Per campaign (newest first)",
    ]

    campaign_scores: list[tuple[str, float]] = []
    for c in campaigns:
        o, cl, u = _weighted_rates(c["rows"])
        campaign_scores.append((_engagement_score(o, cl, u), c["campaign_id"]))
    mid = median([s for s, _ in campaign_scores]) if len(campaign_scores) >= 2 else None

    for c in campaigns:
        o, cl, u = _weighted_rates(c["rows"])
        score = _engagement_score(o, cl, u)
        rel = ""
        if mid is not None:
            rel = " — **above typical** for your history" if score >= mid else " — **below typical** for your history"

        lines.append(f"#### {c['campaign_id']}")
        lines.append(f"- Topic: {c['topic']}")
        if c.get("blog_title"):
            lines.append(f"- Blog title: {c['blog_title']}")
        lines.append(f"- Send date: {c.get('send_date') or 'unknown'}")
        lines.append(
            f"- Campaign rollup (weighted): **{o:.1f}%** open, **{cl:.1f}%** click, **{u:.2f}%** unsub; "
            f"index **{score:.2f}**{rel}."
        )
        lines.append("- By persona:")
        best = None
        best_click = -1.0
        for r in sorted(c["rows"], key=lambda x: x.get("persona_id") or ""):
            rec = max(int(r.get("recipients") or 0), 1)
            pn = (r.get("persona_name") or r.get("persona_id") or "").strip()
            o_r = int(r.get("opens") or 0) / rec * 100.0
            c_r = int(r.get("clicks") or 0) / rec * 100.0
            u_r = int(r.get("unsubscribes") or 0) / rec * 100.0
            if c_r > best_click:
                best_click = c_r
                best = pn
            lines.append(
                f"  - {pn}: {rec} recipients, **{o_r:.1f}%** open, **{c_r:.1f}%** click, **{u_r:.2f}%** unsub"
            )
        if best:
            lines.append(f"- Strongest click segment this send: **{best}** ({best_click:.1f}% click).")
        lines.append("")

    digest = "\n".join(lines)

    return {
        "digest": digest,
        "past_topics": past_topics,
        "past_blog_titles": past_titles,
        "campaign_count": len(campaigns),
        "segment_rows": len(rows),
    }


def build_topic_recommendations(max_items: int = 5) -> dict[str, Any]:
    """Load metrics, call LLM for new topics. Requires OPENAI_API_KEY."""
    payload = build_engagement_digest()
    if not payload:
        return {
            "has_data": False,
            "recommendations": [],
            "tagline": (
                "Send campaigns and record metrics first — then we’ll use engagement + past "
                "topics to suggest new ideas."
            ),
        }

    if not config.OPENAI_API_KEY:
        return {
            "has_data": True,
            "recommendations": [],
            "tagline": "Set **OPENAI_API_KEY** to generate data-driven topic suggestions.",
            "needs_api_key": True,
        }

    try:
        topics = recommend_topics_from_engagement(
            payload["digest"],
            payload["past_topics"],
            payload["past_blog_titles"],
            n=max_items,
        )
    except Exception:
        topics = []

    recommendations = [{"rank": i + 1, "topic": t} for i, t in enumerate(topics)]

    return {
        "has_data": True,
        "recommendations": recommendations,
        "tagline": (
            f"Suggested from **{payload['campaign_count']}** campaign(s), "
            f"**{payload['segment_rows']}** persona segments — informed by opens, clicks, and unsubs."
        ),
        "error": len(recommendations) == 0,
    }


def engagement_cache_key() -> str:
    """Stable string for Streamlit cache invalidation when DB metrics change."""
    p = build_engagement_digest()
    if not p:
        return "empty"
    return (
        f"{p['campaign_count']}|{p['segment_rows']}|"
        f"{hash(p['digest']) & 0xFFFFFFFFFFFFFFFF:x}"
    )
