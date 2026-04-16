from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "novamind.db")


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create tables if they don't exist."""
    conn = _get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS campaigns (
            campaign_id TEXT PRIMARY KEY,
            topic TEXT NOT NULL,
            blog_title TEXT,
            blog_body TEXT,
            blog_outline TEXT,
            newsletters TEXT,
            contacts_synced INTEGER DEFAULT 0,
            send_date TEXT,
            status TEXT DEFAULT 'draft',
            created_at TEXT
        );

        CREATE TABLE IF NOT EXISTS metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id TEXT NOT NULL,
            persona_id TEXT NOT NULL,
            persona_name TEXT,
            recipients INTEGER DEFAULT 0,
            opens INTEGER DEFAULT 0,
            clicks INTEGER DEFAULT 0,
            unsubscribes INTEGER DEFAULT 0,
            recorded_at TEXT,
            FOREIGN KEY (campaign_id) REFERENCES campaigns(campaign_id)
        );

        CREATE TABLE IF NOT EXISTS ai_summaries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id TEXT NOT NULL,
            summary TEXT,
            suggested_topics TEXT,
            created_at TEXT,
            FOREIGN KEY (campaign_id) REFERENCES campaigns(campaign_id)
        );

        CREATE TABLE IF NOT EXISTS hubspot_email_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id TEXT NOT NULL,
            hubspot_email_id TEXT NOT NULL,
            persona_id TEXT NOT NULL,
            persona_name TEXT,
            sent INTEGER DEFAULT 0,
            delivered INTEGER DEFAULT 0,
            opens INTEGER DEFAULT 0,
            clicks INTEGER DEFAULT 0,
            unsubscribes INTEGER DEFAULT 0,
            bounces INTEGER DEFAULT 0,
            open_rate REAL DEFAULT 0.0,
            click_rate REAL DEFAULT 0.0,
            unsubscribe_rate REAL DEFAULT 0.0,
            bounce_rate REAL DEFAULT 0.0,
            fetched_at TEXT,
            FOREIGN KEY (campaign_id) REFERENCES campaigns(campaign_id)
        );
    """)
    conn.commit()
    conn.close()


def save_campaign(campaign_data: dict):
    """Save a campaign record to the database."""
    conn = _get_conn()
    conn.execute(
        """INSERT OR REPLACE INTO campaigns
           (campaign_id, topic, blog_title, blog_body, blog_outline,
            newsletters, contacts_synced, send_date, status, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            campaign_data["campaign_id"],
            campaign_data["topic"],
            campaign_data.get("blog_title", ""),
            campaign_data.get("blog_body", ""),
            json.dumps(campaign_data.get("blog_outline", [])),
            json.dumps(campaign_data.get("newsletters", [])),
            campaign_data.get("contacts_synced", 0),
            campaign_data.get("send_date", datetime.utcnow().isoformat()),
            campaign_data.get("status", "draft"),
            campaign_data.get("created_at", datetime.utcnow().isoformat()),
        ),
    )
    conn.commit()
    conn.close()


def save_metrics(campaign_id: str, persona_metrics: list[dict]):
    """Save engagement metrics for a campaign."""
    conn = _get_conn()
    now = datetime.utcnow().isoformat()
    for pm in persona_metrics:
        conn.execute(
            """INSERT INTO metrics
               (campaign_id, persona_id, persona_name, recipients,
                opens, clicks, unsubscribes, recorded_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                campaign_id,
                pm["persona_id"],
                pm.get("persona_name", ""),
                pm.get("recipients", 0),
                pm.get("opens", 0),
                pm.get("clicks", 0),
                pm.get("unsubscribes", 0),
                now,
            ),
        )
    conn.commit()
    conn.close()


def save_ai_summary(campaign_id: str, summary: str, suggested_topics: list[str]):
    """Save an AI-generated performance summary."""
    conn = _get_conn()
    conn.execute(
        """INSERT INTO ai_summaries (campaign_id, summary, suggested_topics, created_at)
           VALUES (?, ?, ?, ?)""",
        (campaign_id, summary, json.dumps(suggested_topics), datetime.utcnow().isoformat()),
    )
    conn.commit()
    conn.close()


def get_all_campaigns() -> list[dict]:
    """Return all campaigns, most recent first."""
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM campaigns ORDER BY created_at DESC"
    ).fetchall()
    conn.close()
    result = []
    for row in rows:
        d = dict(row)
        d["blog_outline"] = json.loads(d.get("blog_outline") or "[]")
        d["newsletters"] = json.loads(d.get("newsletters") or "[]")
        result.append(d)
    return result


def get_campaign(campaign_id: str) -> dict | None:
    """Return a single campaign by ID."""
    conn = _get_conn()
    row = conn.execute(
        "SELECT * FROM campaigns WHERE campaign_id = ?", (campaign_id,)
    ).fetchone()
    conn.close()
    if row is None:
        return None
    d = dict(row)
    d["blog_outline"] = json.loads(d.get("blog_outline") or "[]")
    d["newsletters"] = json.loads(d.get("newsletters") or "[]")
    return d


def get_metrics(campaign_id: str) -> list[dict]:
    """Return metrics for a campaign."""
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM metrics WHERE campaign_id = ? ORDER BY persona_id",
        (campaign_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_ai_summary(campaign_id: str) -> dict | None:
    """Return the AI summary for a campaign."""
    conn = _get_conn()
    row = conn.execute(
        "SELECT * FROM ai_summaries WHERE campaign_id = ? ORDER BY created_at DESC LIMIT 1",
        (campaign_id,),
    ).fetchone()
    conn.close()
    if row is None:
        return None
    d = dict(row)
    d["suggested_topics"] = json.loads(d.get("suggested_topics") or "[]")
    return d


def save_hubspot_stats(stats_list: list[dict]):
    """Save fetched HubSpot email statistics for historical tracking."""
    conn = _get_conn()
    now = datetime.utcnow().isoformat()
    for s in stats_list:
        conn.execute(
            """INSERT INTO hubspot_email_stats
               (campaign_id, hubspot_email_id, persona_id, persona_name,
                sent, delivered, opens, clicks, unsubscribes, bounces,
                open_rate, click_rate, unsubscribe_rate, bounce_rate, fetched_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                s["campaign_id"],
                s["hubspot_email_id"],
                s["persona_id"],
                s.get("persona_name", ""),
                s.get("sent", 0),
                s.get("delivered", 0),
                s.get("opens", 0),
                s.get("clicks", 0),
                s.get("unsubscribes", 0),
                s.get("bounces", 0),
                s.get("open_rate", 0.0),
                s.get("click_rate", 0.0),
                s.get("unsubscribe_rate", 0.0),
                s.get("bounce_rate", 0.0),
                s.get("fetched_at", now),
            ),
        )
    conn.commit()
    conn.close()


def get_hubspot_stats(campaign_id: str | None = None) -> list[dict]:
    """Return HubSpot email stats, optionally filtered by campaign.
    Returns all snapshots for historical comparison.
    """
    conn = _get_conn()
    if campaign_id:
        rows = conn.execute(
            """SELECT * FROM hubspot_email_stats
               WHERE campaign_id = ? ORDER BY fetched_at DESC""",
            (campaign_id,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM hubspot_email_stats ORDER BY fetched_at DESC"
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_hubspot_stats_latest(campaign_id: str) -> list[dict]:
    """Return only the most recent fetch for each persona in a campaign."""
    conn = _get_conn()
    rows = conn.execute(
        """SELECT * FROM hubspot_email_stats
           WHERE campaign_id = ?
           AND fetched_at = (
               SELECT MAX(fetched_at) FROM hubspot_email_stats
               WHERE campaign_id = ?
           )
           ORDER BY persona_id""",
        (campaign_id, campaign_id),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_campaign(campaign_id: str):
    """Delete a campaign and all associated records from the database."""
    conn = _get_conn()
    conn.execute("DELETE FROM metrics WHERE campaign_id = ?", (campaign_id,))
    conn.execute("DELETE FROM ai_summaries WHERE campaign_id = ?", (campaign_id,))
    conn.execute("DELETE FROM hubspot_email_stats WHERE campaign_id = ?", (campaign_id,))
    conn.execute("DELETE FROM campaigns WHERE campaign_id = ?", (campaign_id,))
    conn.commit()
    conn.close()


def get_historical_metrics() -> list[dict]:
    """Return aggregated metrics across all campaigns for trend analysis."""
    conn = _get_conn()
    rows = conn.execute("""
        SELECT c.campaign_id, c.topic, c.blog_title, c.send_date,
               m.persona_id, m.persona_name, m.recipients, m.opens,
               m.clicks, m.unsubscribes
        FROM campaigns c
        JOIN metrics m ON c.campaign_id = m.campaign_id
        ORDER BY c.send_date DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


init_db()
