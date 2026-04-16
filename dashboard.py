"""
NovaMind — Streamlit Dashboard
A modern visual interface for the AI marketing pipeline.

Run with:
    streamlit run dashboard.py
"""

import base64
import io
import json
import os
import re
from datetime import datetime

import plotly.graph_objects as go
import plotly.express as px
import streamlit as st
from PIL import Image

import config
from pipeline.orchestrator import (
    finalize_campaign_after_review,
    generate_campaign_draft,
    run_post_send_analytics,
)
from pipeline.topic_recommendations import (
    build_topic_recommendations,
    engagement_cache_key,
)
from storage.database import (
    get_all_campaigns,
    get_campaign,
    get_metrics,
    get_historical_metrics,
)
from storage.file_store import load_contacts, resolve_markdown_images_for_streamlit


@st.cache_data(ttl=600, show_spinner="Generating suggestions from your metrics…")
def _cached_topic_recommendations(_cache_key: str, max_items: int) -> dict:
    """Cache LLM topic suggestions; _cache_key busts cache when metrics change."""
    return build_topic_recommendations(max_items=max_items)


# ── Page Config ──────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="NovaMind Dashboard",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)

LOGO_PATH = os.path.join("data", "logo.png")
LOGO_DARK_PATH = os.path.join("data", "logo_dark.png")


def _logo_base64(path: str, remove_dark_bg: bool = False) -> str:
    """Return a base64-encoded PNG ready for embedding in an HTML img src.

    When remove_dark_bg=True, dark unsaturated (grey/black) pixels are made
    fully transparent, so the logo blends into a dark sidebar background.
    """
    img = Image.open(path).convert("RGBA")
    if remove_dark_bg:
        data = img.getdata()
        new_data = []
        for r, g, b, a in data:
            brightness = (r + g + b) / 3
            # Saturation proxy: how spread out the channels are.
            # Low spread = grey/black; high spread = coloured (purple, white).
            hi, lo = max(r, g, b), min(r, g, b)
            saturation = (hi - lo) / max(hi, 1)
            if brightness < 80 and saturation < 0.25:
                # Dark, unsaturated → background → transparent
                new_data.append((r, g, b, 0))
            elif brightness < 130 and saturation < 0.15:
                # Mid-dark grey edge → feather alpha proportionally
                alpha = int(a * (brightness - 80) / 50)
                new_data.append((r, g, b, max(0, alpha)))
            else:
                new_data.append((r, g, b, a))
        img.putdata(new_data)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()

# ── Custom CSS ───────────────────────────────────────────────────────────────

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    .block-container { padding-top: 1.1rem; padding-bottom: 1.2rem; max-width: 1280px; }

    /* Sidebar styling */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0f0f23 0%, #1a1a3e 100%);
    }
    [data-testid="stSidebar"] * { color: #e0e0f0 !important; }
    [data-testid="stSidebar"] .stRadio label {
        font-size: 0.95rem;
        padding: 0.4rem 0;
    }

    /* KPI cards */
    .kpi-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        border-radius: 16px;
        padding: 1.5rem;
        color: white;
        text-align: center;
        box-shadow: 0 4px 15px rgba(102, 126, 234, 0.3);
        transition: transform 0.2s;
    }
    .kpi-card:hover { transform: translateY(-2px); }
    .kpi-card h2 { margin: 0; font-size: 2.2rem; font-weight: 700; }
    .kpi-card p { margin: 0.3rem 0 0; font-size: 0.85rem; opacity: 0.9; }

    .kpi-green {
        background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
        box-shadow: 0 4px 15px rgba(17, 153, 142, 0.3);
    }
    .kpi-orange {
        background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
        box-shadow: 0 4px 15px rgba(240, 147, 251, 0.3);
    }
    .kpi-blue {
        background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
        box-shadow: 0 4px 15px rgba(79, 172, 254, 0.3);
    }

    /* Campaign card */
    .campaign-card {
        background: white;
        border: 1px solid #e8eaf0;
        border-radius: 12px;
        padding: 1.25rem;
        margin-bottom: 0.75rem;
        transition: box-shadow 0.2s;
    }
    .campaign-card:hover { box-shadow: 0 4px 12px rgba(0,0,0,0.08); }

    /* Status badges */
    .badge {
        display: inline-block;
        padding: 0.2rem 0.75rem;
        border-radius: 20px;
        font-size: 0.75rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    .badge-sent { background: #d4edda; color: #155724; }
    .badge-draft { background: #fff3cd; color: #856404; }

    /* Section headers */
    .section-header {
        font-size: 1.1rem;
        font-weight: 600;
        color: #1a1a3e;
        margin-top: 0.25rem;
        margin-bottom: 0.65rem;
        padding-bottom: 0.4rem;
        border-bottom: 2px solid #667eea;
        display: inline-block;
    }

    .insight-card {
        background: linear-gradient(135deg, #f8faff 0%, #eef3ff 100%);
        border: 1px solid #dbe6ff;
        border-left: 5px solid #667eea;
        border-radius: 14px;
        padding: 1rem 1rem 0.8rem 1rem;
        margin: 0.4rem 0 0.8rem 0;
    }
    .insight-card h4 {
        margin: 0 0 0.35rem 0;
        font-size: 1.02rem;
        color: #1f2a56;
    }
    .insight-card p {
        margin: 0;
        color: #2d3558;
        font-size: 0.94rem;
        line-height: 1.45;
    }
    .action-card {
        background: #ffffff;
        border: 1px solid #e5e9f3;
        border-radius: 12px;
        padding: 0.8rem 0.95rem 0.2rem 0.95rem;
        margin: 0.35rem 0 0.9rem 0;
    }
    .small-gap { margin-top: 0.5rem; margin-bottom: 1.15rem; }

    /* Contact table */
    .contact-row {
        display: flex;
        align-items: center;
        padding: 0.6rem 0;
        border-bottom: 1px solid #f0f0f5;
    }

    /* Persona chips */
    .persona-chip {
        display: inline-block;
        padding: 0.15rem 0.6rem;
        border-radius: 12px;
        font-size: 0.75rem;
        font-weight: 500;
    }
    .persona-creative { background: #ede7f6; color: #4527a0; }
    .persona-brand { background: #e3f2fd; color: #1565c0; }
    .persona-account { background: #e8f5e9; color: #2e7d32; }

    /* Hide default Streamlit elements */
    #MainMenu { visibility: hidden; }
    footer { visibility: hidden; }
    .stDeployButton { display: none; }

    div[data-testid="stMetric"] {
        background: #f8f9fc;
        border-radius: 10px;
        padding: 0.75rem 1rem;
        border: 1px solid #e8eaf0;
    }
</style>
""", unsafe_allow_html=True)


# ── Sidebar ──────────────────────────────────────────────────────────────────

with st.sidebar:
    logo_path = LOGO_DARK_PATH if os.path.exists(LOGO_DARK_PATH) else LOGO_PATH
    if os.path.exists(logo_path):
        try:
            is_dark = logo_path == LOGO_DARK_PATH
            logo_b64 = _logo_base64(logo_path, remove_dark_bg=is_dark)
            st.markdown(
                f'<img src="data:image/png;base64,{logo_b64}" '
                'style="width:100%;display:block;margin:0 auto;padding:0.5rem 0;" />',
                unsafe_allow_html=True,
            )
        except Exception:
            st.image(logo_path, use_container_width=True)
    else:
        st.markdown("## NovaMind")
    st.caption("AI Marketing Pipeline")
    st.divider()

    nav_pages = [
        "Overview",
        "Content Generation",
        "Campaigns",
        "Analytics",
        "Contacts",
    ]
    requested_page = st.query_params.get("page", "Overview")
    if requested_page == "Run Pipeline":
        requested_page = "Content Generation"
    if requested_page == "Campaign Generation":
        requested_page = "Content Generation"
    if requested_page not in nav_pages:
        requested_page = "Overview"

    page = st.radio(
        "Navigation",
        nav_pages,
        index=nav_pages.index(requested_page),
        label_visibility="collapsed",
        format_func=lambda x: {
            "Overview": "📊  Overview",
            "Content Generation": "🚀  Content Generation",
            "Campaigns": "📄  Campaigns",
            "Analytics": "📈  Analytics",
            "Contacts": "👥  Contacts",
        }[x],
    )

    st.divider()
    campaigns = get_all_campaigns()
    st.caption(f"📌 {len(campaigns)} campaigns total")
    contacts = load_contacts()
    st.caption(f"👥 {len(contacts)} contacts in CRM")


# ── Helper Functions ─────────────────────────────────────────────────────────

def _kpi_card(value, label, css_class=""):
    cls = f"kpi-card {css_class}" if css_class else "kpi-card"
    st.markdown(f"""
    <div class="{cls}">
        <h2>{value}</h2>
        <p>{label}</p>
    </div>
    """, unsafe_allow_html=True)


def _status_badge(status):
    cls = "badge-sent" if status == "sent" else "badge-draft"
    return f'<span class="badge {cls}">{status}</span>'


def _persona_chip(persona_id):
    labels = {
        "creative_professionals": ("Creative Pro", "persona-creative"),
        "brand_strategists": ("Brand Strat", "persona-brand"),
        "account_managers": ("Account Mgr", "persona-account"),
    }
    label, cls = labels.get(persona_id, (persona_id, ""))
    return f'<span class="persona-chip {cls}">{label}</span>'


def _format_date(date_str):
    if not date_str:
        return "—"
    try:
        dt = datetime.fromisoformat(date_str)
        return dt.strftime("%b %d, %Y • %I:%M %p")
    except (ValueError, TypeError):
        return date_str[:10] if date_str else "—"


def _short_date(date_str):
    if not date_str:
        return "—"
    try:
        dt = datetime.fromisoformat(date_str)
        return dt.strftime("%b %d")
    except (ValueError, TypeError):
        return date_str[:10]


def _campaign_blog_link(campaign_id: str) -> str:
    return f"?page=Campaigns&campaign_id={campaign_id}"


def _resolve_newsletter_blog_links(markdown: str, campaign_id: str) -> str:
    """Map newsletter placeholder links (#) to the campaign's blog page."""
    blog_link = _campaign_blog_link(campaign_id)
    return re.sub(r"\]\(#(?:[^)]*)\)", f"]({blog_link})", markdown)


def _overview_summary_and_actions(
    campaigns_data: list[dict],
    all_metrics: list[dict],
    unique_recipient_count: int,
) -> tuple[str, list[str]]:
    """Create overview summary + dynamic actions from real DB metrics only."""
    if not campaigns_data or not all_metrics:
        return ("No performance data yet. Generate and send a campaign to see analytics.", [])

    total_recipients = sum(m.get("recipients", 0) for m in all_metrics)
    total_opens = sum(m.get("opens", 0) for m in all_metrics)
    total_clicks = sum(m.get("clicks", 0) for m in all_metrics)
    total_unsubs = sum(m.get("unsubscribes", 0) for m in all_metrics)
    overall_open = round(total_opens / max(total_recipients, 1) * 100, 1)
    overall_click = round(total_clicks / max(total_recipients, 1) * 100, 1)
    overall_unsub = round(total_unsubs / max(total_recipients, 1) * 100, 2)

    latest = campaigns_data[0]
    latest_metrics = [m for m in all_metrics if m.get("campaign_id") == latest.get("campaign_id")]
    latest_recipients = sum(m.get("recipients", 0) for m in latest_metrics)
    latest_opens = sum(m.get("opens", 0) for m in latest_metrics)
    latest_clicks = sum(m.get("clicks", 0) for m in latest_metrics)
    latest_open = round(latest_opens / max(latest_recipients, 1) * 100, 1)
    latest_click = round(latest_clicks / max(latest_recipients, 1) * 100, 1)

    latest_title = latest.get("blog_title", latest.get("topic", latest.get("campaign_id", "Latest campaign")))
    summary = (
        f"Across all {len(campaigns_data)} campaigns, NovaMind reached {unique_recipient_count} unique recipients "
        f"with {overall_open}% open, {overall_click}% click, and {overall_unsub}% unsubscribe rates. "
        f'The most recent campaign ("{latest_title}") reached {latest_recipients} recipients '
        f"with {latest_open}% open and {latest_click}% click rates."
    )

    # Persona performance across all campaigns
    persona_rollup: dict[str, dict] = {}
    for row in all_metrics:
        pid = row.get("persona_id", "")
        if not pid:
            continue
        if pid not in persona_rollup:
            persona_rollup[pid] = {
                "persona_name": row.get("persona_name", pid),
                "recipients": 0,
                "opens": 0,
                "clicks": 0,
                "unsubs": 0,
            }
        persona_rollup[pid]["recipients"] += row.get("recipients", 0)
        persona_rollup[pid]["opens"] += row.get("opens", 0)
        persona_rollup[pid]["clicks"] += row.get("clicks", 0)
        persona_rollup[pid]["unsubs"] += row.get("unsubscribes", 0)

    for pid in persona_rollup:
        rec = max(persona_rollup[pid]["recipients"], 1)
        persona_rollup[pid]["open_rate"] = round(persona_rollup[pid]["opens"] / rec * 100, 1)
        persona_rollup[pid]["click_rate"] = round(persona_rollup[pid]["clicks"] / rec * 100, 1)
        persona_rollup[pid]["unsub_rate"] = round(persona_rollup[pid]["unsubs"] / rec * 100, 1)

    # Historical campaign-level baseline excluding latest campaign.
    historical_rows = [m for m in all_metrics if m.get("campaign_id") != latest.get("campaign_id")]
    historical_recipients = sum(m.get("recipients", 0) for m in historical_rows)
    historical_opens = sum(m.get("opens", 0) for m in historical_rows)
    historical_clicks = sum(m.get("clicks", 0) for m in historical_rows)
    historical_unsubs = sum(m.get("unsubscribes", 0) for m in historical_rows)
    hist_open_rate = round(historical_opens / max(historical_recipients, 1) * 100, 1) if historical_rows else None
    hist_click_rate = round(historical_clicks / max(historical_recipients, 1) * 100, 1) if historical_rows else None
    hist_unsub_rate = round(historical_unsubs / max(historical_recipients, 1) * 100, 2) if historical_rows else None

    # Dynamic recommendation engine: build scored action candidates from metrics signals.
    candidates: list[dict] = []

    def add_action(priority: float, text: str):
        candidates.append({"priority": priority, "text": text})

    if hist_open_rate is not None:
        open_delta = round(latest_open - hist_open_rate, 1)
        if open_delta < -2:
            add_action(
                abs(open_delta) + 2,
                (
                    f"Improve top-of-funnel engagement: latest open rate is **{latest_open}%**, "
                    f"which is **{abs(open_delta)} pts below** historical average ({hist_open_rate}%). "
                    "Test 2-3 subject line variants and send-time windows in the next campaign."
                ),
            )
        elif open_delta > 2:
            add_action(
                open_delta + 1,
                (
                    f"Capture what is working in opens: latest open rate (**{latest_open}%**) is "
                    f"**{open_delta} pts above** historical average ({hist_open_rate}%). "
                    "Reuse high-performing subject framing as a baseline for the next send."
                ),
            )

    if hist_click_rate is not None:
        click_delta = round(latest_click - hist_click_rate, 1)
        if click_delta < -1.5:
            add_action(
                abs(click_delta) + 2,
                (
                    f"Strengthen conversion in body copy: latest click rate is **{latest_click}%**, "
                    f"**{abs(click_delta)} pts below** historical average ({hist_click_rate}%). "
                    "Tighten CTA placement and make one primary action explicit per persona."
                ),
            )
        elif click_delta > 1.5:
            add_action(
                click_delta + 1,
                (
                    f"Scale recent click-through gains: latest click rate (**{latest_click}%**) is "
                    f"**{click_delta} pts above** historical average ({hist_click_rate}%). "
                    "Replicate CTA structure and narrative flow from this campaign."
                ),
            )

    if hist_unsub_rate is not None:
        unsub_delta = round(overall_unsub - hist_unsub_rate, 2)
        if unsub_delta > 0.3:
            add_action(
                unsub_delta * 10 + 1,
                (
                    f"Reduce list fatigue: unsubscribe rate is **{overall_unsub}%**, "
                    f"up **{unsub_delta} pts** vs historical ({hist_unsub_rate}%). "
                    "Shorten copy and tighten persona-message fit for low-engagement segments."
                ),
            )

    if latest_metrics:
        by_click = sorted(
            latest_metrics,
            key=lambda x: x.get("clicks", 0) / max(x.get("recipients", 1), 1),
            reverse=True,
        )
        by_open = sorted(
            latest_metrics,
            key=lambda x: x.get("opens", 0) / max(x.get("recipients", 1), 1),
        )
        by_unsub = sorted(
            latest_metrics,
            key=lambda x: x.get("unsubscribes", 0) / max(x.get("recipients", 1), 1),
            reverse=True,
        )

        best_click_seg = by_click[0]
        best_click_rate = round(best_click_seg.get("clicks", 0) / max(best_click_seg.get("recipients", 1), 1) * 100, 1)
        add_action(
            best_click_rate / 3 + 1,
            (
                f"Scale winning persona strategy: **{best_click_seg.get('persona_name', best_click_seg.get('persona_id'))}** "
                f"led click performance at **{best_click_rate}%** in the latest campaign. "
                "Reuse its angle and CTA style in the next iteration."
            ),
        )

        low_open_seg = by_open[0]
        low_open_rate = round(low_open_seg.get("opens", 0) / max(low_open_seg.get("recipients", 1), 1) * 100, 1)
        add_action(
            max(1.0, (50 - low_open_rate) / 10),
            (
                f"Focus optimization on **{low_open_seg.get('persona_name', low_open_seg.get('persona_id'))}**: "
                f"open rate is **{low_open_rate}%** in the latest campaign. "
                "Test a sharper subject hook and first-line personalization for this segment."
            ),
        )

        high_unsub_seg = by_unsub[0]
        high_unsub_rate = round(
            high_unsub_seg.get("unsubscribes", 0) / max(high_unsub_seg.get("recipients", 1), 1) * 100, 1
        )
        if high_unsub_rate > 0:
            add_action(
                high_unsub_rate + 1,
                (
                    f"Contain churn risk in **{high_unsub_seg.get('persona_name', high_unsub_seg.get('persona_id'))}** "
                    f"(unsubscribe **{high_unsub_rate}%**). "
                    "Shorten the email and align examples more tightly to that persona's workflow pain."
                ),
            )

    # Fallback action if signals are sparse.
    if not candidates:
        candidates.append(
            {
                "priority": 1.0,
                "text": "Collect another campaign cycle to unlock stronger trend-based recommendations.",
            }
        )

    # Keep top unique actions by priority.
    actions = []
    seen = set()
    for item in sorted(candidates, key=lambda x: x["priority"], reverse=True):
        text = item["text"]
        if text in seen:
            continue
        seen.add(text)
        actions.append(text)
        if len(actions) == 4:
            break

    if latest_metrics:
        return summary, actions
    return summary, actions


PERSONA_COLORS = {
    "creative_professionals": "#7c4dff",
    "brand_strategists": "#2196f3",
    "account_managers": "#4caf50",
}


def _backfill_missing_metrics_for_sent_campaigns():
    """Populate delayed metrics after a page refresh for sent campaigns."""
    for c in campaigns:
        if c.get("status") != "sent":
            continue
        if get_metrics(c["campaign_id"]):
            continue
        try:
            run_post_send_analytics(c["campaign_id"])
        except Exception:
            # Non-fatal: keep UI responsive even if metrics backfill fails.
            pass


# ── Page: Overview ───────────────────────────────────────────────────────────

def page_overview():
    _backfill_missing_metrics_for_sent_campaigns()
    st.title("Dashboard Overview")
    st.caption("Real-time view of your AI marketing pipeline performance")

    all_metrics = get_historical_metrics()
    unique_recipient_count = len(
        {(c.get("email", "") or "").strip().lower() for c in contacts if c.get("email")}
    )

    total_campaigns = len(campaigns)
    total_recipients = sum(m.get("recipients", 0) for m in all_metrics)
    total_opens = sum(m.get("opens", 0) for m in all_metrics)
    total_clicks = sum(m.get("clicks", 0) for m in all_metrics)
    avg_open_rate = round(total_opens / max(total_recipients, 1) * 100, 1)
    avg_click_rate = round(total_clicks / max(total_recipients, 1) * 100, 1)

    # AI summary at top (overview only)
    st.markdown('<p class="section-header">AI Performance Summary</p>', unsafe_allow_html=True)
    summary_text, next_actions = _overview_summary_and_actions(
        campaigns,
        all_metrics,
        unique_recipient_count=unique_recipient_count,
    )
    st.markdown(
        f"""
        <div class="insight-card">
            <h4>Portfolio Insight</h4>
            <p>{summary_text}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if next_actions:
        st.markdown('<div class="action-card"><p class="small-gap"><strong>Recommended Next Actions</strong></p></div>', unsafe_allow_html=True)
        for i, action in enumerate(next_actions, 1):
            st.markdown(f"{i}. {action}")

    st.markdown('<div class="small-gap"></div>', unsafe_allow_html=True)
    st.markdown('<div style="margin-top: 0.65rem; margin-bottom: 0.75rem;"></div>', unsafe_allow_html=True)

    # KPI row
    k1, k2, k3, k4 = st.columns(4)
    with k1:
        _kpi_card(total_campaigns, "Total Campaigns")
    with k2:
        _kpi_card(unique_recipient_count, "Unique Recipients", "kpi-green")
    with k3:
        _kpi_card(f"{avg_open_rate}%", "Avg Open Rate", "kpi-orange")
    with k4:
        _kpi_card(f"{avg_click_rate}%", "Avg Click Rate", "kpi-blue")

    # Charts row
    col_left, col_right = st.columns([3, 2])

    with col_left:
        st.markdown('<p class="section-header">Performance by Campaign</p>', unsafe_allow_html=True)

        if campaigns:
            camp_names = []
            camp_opens = []
            camp_clicks = []

            for c in reversed(campaigns):
                metrics = get_metrics(c["campaign_id"])
                if not metrics:
                    continue
                title = c.get("blog_title", c.get("topic", ""))
                r = sum(m["recipients"] for m in metrics)
                o = sum(m["opens"] for m in metrics)
                cl = sum(m["clicks"] for m in metrics)
                camp_names.append(title[:36] + "..." if len(title) > 36 else title)
                camp_opens.append(round(o / max(r, 1) * 100, 1))
                camp_clicks.append(round(cl / max(r, 1) * 100, 1))

            if camp_names:
                fig = go.Figure()
                fig.add_trace(go.Bar(
                    name="Open %",
                    x=camp_names,
                    y=camp_opens,
                    marker_color="#667eea",
                    marker_cornerradius=6,
                ))
                fig.add_trace(go.Bar(
                    name="Click %",
                    x=camp_names,
                    y=camp_clicks,
                    marker_color="#38ef7d",
                    marker_cornerradius=6,
                ))
                fig.update_layout(
                    height=350,
                    barmode="group",
                    margin=dict(l=20, r=20, t=20, b=70),
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    font=dict(family="Inter, sans-serif", size=12),
                    yaxis=dict(title="Rate (%)", gridcolor="#f0f0f5"),
                    legend=dict(orientation="h", y=1.05, x=1, xanchor="right"),
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No campaign metrics available yet.")
        else:
            st.info("No campaign data yet. Run the pipeline to get started!")

    with col_right:
        st.markdown('<p class="section-header">Persona Audience Split</p>', unsafe_allow_html=True)

        if all_metrics:
            persona_data = {}
            for m in all_metrics:
                pid = m["persona_id"]
                if pid not in persona_data:
                    persona_data[pid] = {"name": m["persona_name"], "recipients": 0}
                persona_data[pid]["recipients"] += m.get("recipients", 0)
            recipients = [v["recipients"] for v in persona_data.values()]
            names = [v["name"] for v in persona_data.values()]
            colors = [PERSONA_COLORS.get(k, "#999") for k in persona_data.keys()]

            fig = go.Figure(data=[go.Pie(
                labels=names,
                values=recipients,
                hole=0.45,
                marker=dict(colors=colors),
                textinfo="none",
                hovertemplate="%{label}<br>Recipients: %{value}<br>%{percent}<extra></extra>",
            )])
            fig.update_layout(
                height=330,
                margin=dict(l=10, r=10, t=20, b=10),
                paper_bgcolor="rgba(0,0,0,0)",
                font=dict(family="Inter, sans-serif"),
                showlegend=True,
                legend=dict(orientation="h", y=-0.15, x=0.5, xanchor="center"),
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No engagement data yet.")

    # Recent campaigns list
    st.markdown('<p class="section-header">Recent Campaigns</p>', unsafe_allow_html=True)

    if campaigns:
        for c in campaigns[:5]:
            title = c.get("blog_title", c.get("topic", "Untitled"))
            status = c.get("status", "draft")
            date = _format_date(c.get("send_date", ""))
            synced = c.get("contacts_synced", 0)
            nls = c.get("newsletters", [])
            nl_count = len(nls)

            metrics = get_metrics(c["campaign_id"])
            r = sum(m["recipients"] for m in metrics) if metrics else 0
            o = sum(m["opens"] for m in metrics) if metrics else 0
            o_rate = round(o / max(r, 1) * 100, 1) if metrics else 0

            c1, c2, c3, c4, c5 = st.columns([4, 1.4, 1.1, 1.2, 1.1])
            with c1:
                st.markdown(f"**{title}**")
                st.caption(f"📅 {date}")
            with c2:
                st.markdown(_status_badge(status), unsafe_allow_html=True)
            with c3:
                st.metric("Recipients", r)
            with c4:
                st.metric("Open Rate", f"{o_rate:.1f}%")
            with c5:
                st.metric("Newsletters", nl_count)
            st.divider()

# ── Page: Campaigns ──────────────────────────────────────────────────────────

def page_campaigns():
    st.title("Campaign History")
    st.caption("Browse all campaigns and their generated content")

    if not campaigns:
        st.info("No campaigns yet. Go to **Content Generation** to create your first one!")
        return

    # Campaign selector
    campaign_options = {
        c["campaign_id"]: f"{c.get('blog_title', c.get('topic', 'Untitled'))} — {_short_date(c.get('send_date', ''))}"
        for c in campaigns
    }

    selected_id = st.selectbox(
        "Select a campaign",
        options=list(campaign_options.keys()),
        index=(
            list(campaign_options.keys()).index(st.query_params.get("campaign_id"))
            if st.query_params.get("campaign_id") in campaign_options
            else 0
        ),
        format_func=lambda x: campaign_options[x],
    )

    if not selected_id:
        return

    camp = get_campaign(selected_id)
    if not camp:
        st.error("Campaign not found in database.")
        return

    # Campaign header
    st.markdown(f"### {camp.get('blog_title', camp.get('topic', ''))}")

    h1, h2, h3, h4 = st.columns(4)
    h1.metric("Status", camp.get("status", "—").title())
    h2.metric("Contacts Synced", camp.get("contacts_synced", 0))
    h3.metric("Newsletters", len(camp.get("newsletters", [])))
    h4.metric("Date", _short_date(camp.get("send_date", "")))

    st.divider()

    # Blog content
    blog_tab, newsletter_tab = st.tabs(["📝 Blog Post", "📧 Newsletters"])

    with blog_tab:
        body = camp.get("blog_body", "")
        if body:
            st.markdown(resolve_markdown_images_for_streamlit(body))
        else:
            st.info("No blog content stored for this campaign.")

    with newsletter_tab:
        newsletters = camp.get("newsletters", [])
        if not newsletters:
            st.info("No newsletters for this campaign.")
        else:
            nl_tabs = st.tabs([nl.get("persona_name", nl.get("persona_id", "")) for nl in newsletters])
            for i, nl in enumerate(newsletters):
                with nl_tabs[i]:
                    st.markdown(f"**Subject:** {nl.get('subject_line', '')}")
                    st.divider()
                    body_with_blog_link = _resolve_newsletter_blog_links(
                        nl.get("body", ""),
                        selected_id,
                    )
                    st.markdown(resolve_markdown_images_for_streamlit(body_with_blog_link))


# ── Page: Analytics ──────────────────────────────────────────────────────────

def page_analytics():
    _backfill_missing_metrics_for_sent_campaigns()
    st.title("Performance Analytics")
    st.caption("Campaign engagement metrics and trends")

    if not campaigns:
        st.info("No campaign data yet.")
        return

    # Campaign selector
    selected_id = st.selectbox(
        "Select a campaign to analyze",
        options=[c["campaign_id"] for c in campaigns],
        format_func=lambda x: next(
            (f"{c.get('blog_title', c.get('topic', ''))} ({_short_date(c.get('send_date', ''))})"
             for c in campaigns if c["campaign_id"] == x),
            x,
        ),
    )

    if not selected_id:
        return

    metrics = get_metrics(selected_id)
    sim_tab = st.tabs(["📊 Simulated Metrics"])[0]

    # Tab 1: Simulated/Pipeline Metrics
    with sim_tab:
        if not metrics:
            st.info("No simulated metrics found for this campaign.")
        else:
            personas = [m["persona_name"] for m in metrics]
            recipients = [m["recipients"] for m in metrics]
            open_rates = [round(m["opens"] / max(m["recipients"], 1) * 100, 1) for m in metrics]
            click_rates = [round(m["clicks"] / max(m["recipients"], 1) * 100, 1) for m in metrics]
            unsub_rates = [round(m["unsubscribes"] / max(m["recipients"], 1) * 100, 2) for m in metrics]

            m1, m2, m3 = st.columns(3)
            total_r = sum(recipients)
            total_o = sum(m["opens"] for m in metrics)
            total_c = sum(m["clicks"] for m in metrics)
            m1.metric("Total Recipients", total_r)
            m2.metric("Overall Open Rate", f"{round(total_o / max(total_r, 1) * 100, 1)}%")
            m3.metric("Overall Click Rate", f"{round(total_c / max(total_r, 1) * 100, 1)}%")

            st.markdown("<br>", unsafe_allow_html=True)

            col1, col2 = st.columns(2)

            with col1:
                fig = go.Figure()
                fig.add_trace(go.Bar(
                    name="Open Rate %", x=personas, y=open_rates,
                    marker_color="#667eea", marker_cornerradius=6,
                ))
                fig.add_trace(go.Bar(
                    name="Click Rate %", x=personas, y=click_rates,
                    marker_color="#38ef7d", marker_cornerradius=6,
                ))
                fig.add_trace(go.Bar(
                    name="Unsub Rate %", x=personas, y=unsub_rates,
                    marker_color="#f5576c", marker_cornerradius=6,
                ))
                fig.update_layout(
                    barmode="group",
                    height=440,
                    title=dict(
                        text="Engagement by Persona",
                        x=0.02,
                        xanchor="left",
                        y=0.98,
                        yanchor="top",
                        font=dict(size=15),
                    ),
                    margin=dict(l=20, r=20, t=56, b=96),
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    font=dict(family="Inter, sans-serif", size=12),
                    legend=dict(
                        orientation="h",
                        yanchor="top",
                        y=-0.32,
                        xanchor="center",
                        x=0.5,
                    ),
                    yaxis=dict(gridcolor="#f0f0f5"),
                )
                st.plotly_chart(fig, use_container_width=True)

            with col2:
                fig = go.Figure(data=go.Scatterpolar(
                    r=open_rates + [open_rates[0]],
                    theta=personas + [personas[0]],
                    fill="toself",
                    fillcolor="rgba(102, 126, 234, 0.2)",
                    line=dict(color="#667eea", width=2),
                    name="Open Rate",
                ))
                fig.add_trace(go.Scatterpolar(
                    r=click_rates + [click_rates[0]],
                    theta=personas + [personas[0]],
                    fill="toself",
                    fillcolor="rgba(56, 239, 125, 0.2)",
                    line=dict(color="#38ef7d", width=2),
                    name="Click Rate",
                ))
                fig.update_layout(
                    polar=dict(radialaxis=dict(visible=True, gridcolor="#f0f0f5")),
                    height=380, title="Persona Comparison Radar",
                    margin=dict(l=40, r=40, t=50, b=40),
                    paper_bgcolor="rgba(0,0,0,0)",
                    font=dict(family="Inter, sans-serif", size=12),
                    legend=dict(orientation="h", yanchor="bottom", y=-0.15, xanchor="center", x=0.5),
                )
                st.plotly_chart(fig, use_container_width=True)

            # Detailed persona cards
            st.markdown('<p class="section-header">Persona Breakdown</p>', unsafe_allow_html=True)
            pcols = st.columns(len(metrics))
            for i, m in enumerate(metrics):
                with pcols[i]:
                    o_rate = round(m["opens"] / max(m["recipients"], 1) * 100, 1)
                    c_rate = round(m["clicks"] / max(m["recipients"], 1) * 100, 1)
                    u_rate = round(m["unsubscribes"] / max(m["recipients"], 1) * 100, 2)
                    st.markdown(f"**{m['persona_name']}**")
                    st.metric("Recipients", m["recipients"])
                    st.metric("Opens", f"{m['opens']} ({o_rate}%)")
                    st.metric("Clicks", f"{m['clicks']} ({c_rate}%)")
                    st.metric("Unsubs", f"{m['unsubscribes']} ({u_rate}%)")

    # Cross-campaign trends
    st.divider()
    st.markdown('<p class="section-header">Cross-Campaign Trend</p>', unsafe_allow_html=True)

    all_hist = get_historical_metrics()
    if all_hist:
        camp_agg = {}
        for row in all_hist:
            cid = row["campaign_id"]
            if cid not in camp_agg:
                camp_agg[cid] = {
                    "topic": row.get("topic", ""),
                    "date": row.get("send_date", ""),
                    "recipients": 0, "opens": 0, "clicks": 0,
                }
            camp_agg[cid]["recipients"] += row.get("recipients", 0)
            camp_agg[cid]["opens"] += row.get("opens", 0)
            camp_agg[cid]["clicks"] += row.get("clicks", 0)

        sorted_camps = sorted(camp_agg.items(), key=lambda x: x[1]["date"])
        dates = [_short_date(v["date"]) for _, v in sorted_camps]
        trend_open = [round(v["opens"] / max(v["recipients"], 1) * 100, 1) for _, v in sorted_camps]
        trend_click = [round(v["clicks"] / max(v["recipients"], 1) * 100, 1) for _, v in sorted_camps]

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=dates, y=trend_open, mode="lines+markers",
            name="Open Rate %", line=dict(color="#667eea", width=3),
            marker=dict(size=10),
        ))
        fig.add_trace(go.Scatter(
            x=dates, y=trend_click, mode="lines+markers",
            name="Click Rate %", line=dict(color="#38ef7d", width=3),
            marker=dict(size=10),
        ))
        fig.update_layout(
            height=300,
            margin=dict(l=20, r=20, t=20, b=40),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font=dict(family="Inter, sans-serif", size=12),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            yaxis=dict(gridcolor="#f0f0f5", title="Rate (%)"),
            xaxis=dict(title="Campaign"),
        )
        st.plotly_chart(fig, use_container_width=True)


# ── Page: Contacts ───────────────────────────────────────────────────────────

def page_contacts():
    st.title("CRM Contacts")
    st.caption("All contacts synced to HubSpot, segmented by persona")

    contacts_data = load_contacts()

    if not contacts_data:
        st.info("No contacts found. Add contacts to `data/contacts.json`.")
        return

    # Summary cards
    personas = {}
    for c in contacts_data:
        p = c.get("persona", "unknown")
        personas.setdefault(p, []).append(c)

    cols = st.columns(len(personas))
    persona_labels = {
        "creative_professionals": ("Creative Professionals", "kpi-card"),
        "brand_strategists": ("Brand Strategists", "kpi-card kpi-blue"),
        "account_managers": ("Account Managers", "kpi-card kpi-green"),
    }
    for i, (pid, members) in enumerate(personas.items()):
        label, css = persona_labels.get(pid, (pid, "kpi-card"))
        with cols[i]:
            _kpi_card(len(members), label, css.replace("kpi-card ", "").replace("kpi-card", ""))

    st.markdown("<br>", unsafe_allow_html=True)

    # Filter
    filter_persona = st.selectbox(
        "Filter by Persona",
        ["All"] + list(personas.keys()),
        format_func=lambda x: x.replace("_", " ").title() if x != "All" else "All Personas",
    )

    filtered = contacts_data if filter_persona == "All" else personas.get(filter_persona, [])

    # Contact table
    st.markdown(f'<p class="section-header">{len(filtered)} Contacts</p>', unsafe_allow_html=True)

    for c in filtered:
        c1, c2, c3, c4 = st.columns([2, 3, 2, 2])
        with c1:
            st.markdown(f"**{c.get('first_name', '')} {c.get('last_name', '')}**")
        with c2:
            st.caption(c.get("email", ""))
        with c3:
            st.caption(c.get("company", ""))
        with c4:
            st.markdown(_persona_chip(c.get("persona", "")), unsafe_allow_html=True)


# ── Page: Content Generation ───────────────────────────────────────────────

def page_run_pipeline():
    st.title("Content Generation")
    st.caption("Human-in-the-loop workflow: generate draft, review/edit, then approve and send")

    col_left, col_right = st.columns([3, 2])
    active_campaign = None

    with col_left:
        st.markdown("### 1) Generate Draft")
        topic = st.text_input(
            "Enter a blog topic",
            placeholder="e.g., AI in creative automation",
        )

        if st.button(
            "Generate Draft for Review",
            type="primary",
            disabled=not topic,
            use_container_width=True,
        ):
            with st.spinner("Generating draft blog + newsletters..."):
                try:
                    draft = generate_campaign_draft(topic)
                    st.session_state["hitl_campaign_id"] = draft["campaign_id"]
                    st.success(
                        f"Draft created for campaign **{draft['campaign_id']}**. "
                        "Now review and approve below."
                    )
                except Exception as e:
                    st.error(f"Draft generation failed: {e}")

        # Prefer active draft in session; fallback to latest awaiting_review draft
        active_draft_id = st.session_state.get("hitl_campaign_id")
        active_campaign = get_campaign(active_draft_id) if active_draft_id else None
        if not active_campaign or active_campaign.get("status") != "awaiting_review":
            pending = [c for c in campaigns if c.get("status") == "awaiting_review"]
            active_campaign = pending[0] if pending else None
            if active_campaign:
                st.session_state["hitl_campaign_id"] = active_campaign["campaign_id"]

        if active_campaign:
            campaign_id = active_campaign["campaign_id"]
            st.divider()
            st.markdown("### 2) Human Review & Approval")
            st.caption(f"Campaign: `{campaign_id}`")

            default_title = active_campaign.get("blog_title", "")
            edited_title = st.text_input(
                "Blog title (editable)",
                value=default_title,
                key=f"hitl_blog_title_{campaign_id}",
            )
            edited_body = st.text_area(
                "Blog body (review and edit)",
                value=active_campaign.get("blog_body", ""),
                height=420,
                key=f"hitl_blog_body_{campaign_id}",
            )

            st.markdown("#### Newsletter Review")
            newsletters = active_campaign.get("newsletters", [])
            edited_newsletters: list[dict] = []
            if newsletters:
                nl_tabs = st.tabs([nl.get("persona_name", "") for nl in newsletters])
                for i, nl in enumerate(newsletters):
                    with nl_tabs[i]:
                        subject = st.text_input(
                            "Subject line",
                            value=nl.get("subject_line", ""),
                            key=f"hitl_subject_{campaign_id}_{nl.get('persona_id', i)}",
                        )
                        body = st.text_area(
                            "Newsletter body",
                            value=nl.get("body", ""),
                            height=240,
                            key=f"hitl_body_{campaign_id}_{nl.get('persona_id', i)}",
                        )
                        edited_newsletters.append({
                            "persona_id": nl.get("persona_id", ""),
                            "persona_name": nl.get("persona_name", ""),
                            "subject_line": subject,
                            "body": body,
                        })

            if st.button("Approve & Send to HubSpot", type="primary", use_container_width=True):
                with st.spinner("Finalizing campaign and sending approved content..."):
                    try:
                        result = finalize_campaign_after_review(
                            campaign_id=campaign_id,
                            topic=active_campaign.get("topic", ""),
                            blog_title=edited_title,
                            blog_body=edited_body,
                            newsletters_data=edited_newsletters,
                        )
                        st.success(f"Campaign sent! **{result['campaign_id']}**")

                        r1, r2 = st.columns(2)
                        r1.metric("Blog Words", result["blog"]["word_count"])
                        r2.metric("Contacts Synced", result["contacts_synced"])
                        st.info(
                            "Metrics are not available immediately after send. "
                            "Refresh the page to fetch post-send metrics in Overview and Analytics."
                        )

                        st.session_state.pop("hitl_campaign_id", None)
                    except Exception as e:
                        st.error(f"Finalization failed: {e}")

    with col_right:
        if active_campaign:
            campaign_id = active_campaign["campaign_id"]
            st.markdown("### AI Copilot (Mock)")
            st.caption("Demo chatbot experience during review.")

            chat_state_key = f"hitl_chat_{campaign_id}"
            if chat_state_key not in st.session_state:
                st.session_state[chat_state_key] = []

            chat_messages = st.session_state[chat_state_key]
            for msg in chat_messages[-8:]:
                with st.chat_message(msg["role"]):
                    st.markdown(msg["content"])

            user_prompt = st.chat_input(
                "Chat with AI Copilot (mock)...",
                key=f"hitl_chat_input_{campaign_id}",
            )
            if user_prompt:
                chat_messages.append({"role": "user", "content": user_prompt})
                chat_messages.append({
                    "role": "assistant",
                    "content": "This is a feature in development. Please check again later",
                })
                st.session_state[chat_state_key] = chat_messages
                st.rerun()

            st.divider()

        st.markdown("### Suggested Topics")
        h1, h2 = st.columns(2)
        with h1:
            st.caption("LLM picks new angles from engagement + past topics (cached ~10 min).")
        with h2:
            if st.button(
                "Refresh",
                key="topic_recs_refresh",
                help="Clear cache and run the model again",
                use_container_width=True,
            ):
                _cached_topic_recommendations.clear()
                st.rerun()
        _ck = engagement_cache_key()
        rec_payload = _cached_topic_recommendations(_ck, 5)
        if not rec_payload["has_data"]:
            st.info(rec_payload["tagline"])
        elif rec_payload.get("needs_api_key"):
            st.warning(rec_payload["tagline"])
        else:
            st.caption(rec_payload["tagline"])
            if rec_payload.get("error") and config.OPENAI_API_KEY:
                st.caption("No topics returned — tap **Refresh** or check API logs.")
            for item in rec_payload["recommendations"]:
                st.markdown(f"**{item['rank']}.** {item['topic']}")

        st.divider()
        st.markdown("### HITL Steps")
        st.markdown("""
        1. **Generate Draft** — AI creates blog + persona newsletters
        2. **Human Review** — You edit/approve blog content
        3. **Human Review** — You edit/approve each newsletter
        4. **Send** — Approved content is sent via HubSpot
        5. **Analyze** — Metrics and recommendations are generated
        """)

        if campaigns:
            st.divider()
            st.markdown("### Recent Topics")
            for c in campaigns[:3]:
                st.caption(f"• {c.get('topic', '')}")


# ── Router ───────────────────────────────────────────────────────────────────

if page == "Overview":
    page_overview()
elif page == "Campaigns":
    page_campaigns()
elif page == "Analytics":
    page_analytics()
elif page == "Contacts":
    page_contacts()
elif page == "Content Generation":
    page_run_pipeline()
