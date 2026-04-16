"""
NovaMind — Streamlit Dashboard
A visual interface to trigger the pipeline, view content, and browse analytics.

Run with:
    streamlit run dashboard.py
"""

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px

from pipeline.orchestrator import run_pipeline
from pipeline.content_generator import suggest_topics
from storage.database import (
    get_all_campaigns,
    get_campaign,
    get_metrics,
    get_ai_summary,
)

st.set_page_config(
    page_title="NovaMind Dashboard",
    page_icon="🧠",
    layout="wide",
)

st.title("🧠 NovaMind — AI Marketing Pipeline")
st.caption("Generate, distribute, and optimize marketing content with AI")

tab_pipeline, tab_campaigns, tab_analytics = st.tabs(
    ["Run Pipeline", "Campaign History", "Analytics"]
)


# ── Tab 1: Run Pipeline ──────────────────────────────────────────────────────
with tab_pipeline:
    st.header("Generate New Content")
    topic = st.text_input(
        "Enter a blog topic",
        placeholder="e.g., AI in creative automation",
    )

    if st.button("Run Pipeline", type="primary", disabled=not topic):
        with st.spinner("Running the full pipeline — this takes about 30 seconds..."):
            try:
                result = run_pipeline(topic)
                st.success(f"Pipeline complete! Campaign: {result['campaign_id']}")

                col1, col2, col3 = st.columns(3)
                col1.metric("Blog Words", result["blog"]["word_count"])
                col2.metric("Contacts Synced", result["contacts_synced"])
                col3.metric("Open Rate", f"{result['metrics']['overall_open_rate']}%")

                st.subheader("Generated Blog Post")
                st.markdown(f"**{result['blog']['title']}**")

                campaign = get_campaign(result["campaign_id"])
                if campaign:
                    st.markdown(campaign.get("blog_body", ""))

                    st.subheader("Newsletter Variants")
                    newsletters = campaign.get("newsletters", [])
                    if newsletters:
                        nl_tabs = st.tabs(
                            [nl.get("persona_name", nl.get("persona_id", "")) for nl in newsletters]
                        )
                        for i, nl in enumerate(newsletters):
                            with nl_tabs[i]:
                                st.markdown(f"**Subject:** {nl.get('subject_line', '')}")
                                st.markdown(nl.get("body", ""))

                st.subheader("AI Performance Summary")
                st.info(result.get("ai_summary", "No summary available"))

                st.subheader("Suggested Next Topics")
                for i, t in enumerate(result.get("suggested_topics", []), 1):
                    st.write(f"{i}. {t}")

            except Exception as e:
                st.error(f"Pipeline failed: {e}")

    st.divider()
    st.subheader("Quick Topic Suggestions")
    if st.button("Get AI Topic Ideas"):
        with st.spinner("Thinking..."):
            campaigns = get_all_campaigns()
            past_data = [{"topic": c.get("topic", "")} for c in campaigns[:5]]
            topics = suggest_topics(past_data)
            for i, t in enumerate(topics, 1):
                st.write(f"{i}. {t}")


# ── Tab 2: Campaign History ──────────────────────────────────────────────────
with tab_campaigns:
    st.header("Campaign History")
    campaigns = get_all_campaigns()

    if not campaigns:
        st.info("No campaigns yet. Run the pipeline to create your first one!")
    else:
        for c in campaigns:
            with st.expander(f"📄 {c.get('blog_title', c.get('topic', 'Untitled'))} — {c['campaign_id']}"):
                col1, col2, col3 = st.columns(3)
                col1.write(f"**Topic:** {c.get('topic', '')}")
                col2.write(f"**Status:** {c.get('status', '')}")
                col3.write(f"**Date:** {c.get('send_date', '')[:10]}")

                st.subheader("Blog Post")
                st.markdown(c.get("blog_body", "No content"))

                st.subheader("Newsletters")
                newsletters = c.get("newsletters", [])
                if newsletters:
                    nl_tabs = st.tabs(
                        [nl.get("persona_name", nl.get("persona_id", "")) for nl in newsletters]
                    )
                    for i, nl in enumerate(newsletters):
                        with nl_tabs[i]:
                            st.markdown(f"**Subject:** {nl.get('subject_line', '')}")
                            st.markdown(nl.get("body", ""))


# ── Tab 3: Analytics ─────────────────────────────────────────────────────────
with tab_analytics:
    st.header("Performance Analytics")
    campaigns = get_all_campaigns()

    if not campaigns:
        st.info("No campaign data yet.")
    else:
        selected_id = st.selectbox(
            "Select a campaign",
            options=[c["campaign_id"] for c in campaigns],
            format_func=lambda x: next(
                (f"{c.get('blog_title', c.get('topic', ''))} ({x})" for c in campaigns if c["campaign_id"] == x),
                x,
            ),
        )

        if selected_id:
            metrics = get_metrics(selected_id)
            summary_data = get_ai_summary(selected_id)

            if metrics:
                st.subheader("Engagement by Persona")

                personas = [m["persona_name"] for m in metrics]
                open_rates = [
                    round(m["opens"] / max(m["recipients"], 1) * 100, 1) for m in metrics
                ]
                click_rates = [
                    round(m["clicks"] / max(m["recipients"], 1) * 100, 1) for m in metrics
                ]
                unsub_rates = [
                    round(m["unsubscribes"] / max(m["recipients"], 1) * 100, 2) for m in metrics
                ]

                fig = go.Figure()
                fig.add_trace(go.Bar(name="Open Rate %", x=personas, y=open_rates, marker_color="#4C78A8"))
                fig.add_trace(go.Bar(name="Click Rate %", x=personas, y=click_rates, marker_color="#54A24B"))
                fig.add_trace(go.Bar(name="Unsub Rate %", x=personas, y=unsub_rates, marker_color="#E45756"))
                fig.update_layout(barmode="group", height=400)
                st.plotly_chart(fig, use_container_width=True)

                col1, col2, col3 = st.columns(3)
                for i, m in enumerate(metrics):
                    col = [col1, col2, col3][i % 3]
                    with col:
                        st.metric(f"{m['persona_name']} Opens", f"{open_rates[i]}%")
                        st.metric(f"{m['persona_name']} Clicks", f"{click_rates[i]}%")

            if summary_data:
                st.subheader("AI Performance Summary")
                st.info(summary_data.get("summary", ""))

                topics = summary_data.get("suggested_topics", [])
                if topics:
                    st.subheader("Suggested Next Topics")
                    for i, t in enumerate(topics, 1):
                        st.write(f"{i}. {t}")
