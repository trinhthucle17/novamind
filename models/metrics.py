from __future__ import annotations
from datetime import datetime
from pydantic import BaseModel, Field


class PersonaMetrics(BaseModel):
    persona_id: str
    persona_name: str
    recipients: int = 0
    opens: int = 0
    clicks: int = 0
    unsubscribes: int = 0

    @property
    def open_rate(self) -> float:
        return round(self.opens / max(self.recipients, 1) * 100, 2)

    @property
    def click_rate(self) -> float:
        return round(self.clicks / max(self.recipients, 1) * 100, 2)

    @property
    def unsubscribe_rate(self) -> float:
        return round(self.unsubscribes / max(self.recipients, 1) * 100, 2)


class HubSpotEmailStats(BaseModel):
    """Real performance data fetched from HubSpot's Marketing Email Statistics API."""
    campaign_id: str
    hubspot_email_id: str
    persona_id: str
    persona_name: str = ""
    sent: int = 0
    delivered: int = 0
    opens: int = 0
    clicks: int = 0
    unsubscribes: int = 0
    bounces: int = 0
    open_rate: float = 0.0
    click_rate: float = 0.0
    unsubscribe_rate: float = 0.0
    bounce_rate: float = 0.0
    fetched_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class CampaignMetrics(BaseModel):
    campaign_id: str
    blog_title: str = ""
    send_date: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    persona_metrics: list[PersonaMetrics] = Field(default_factory=list)
    ai_summary: str = ""
    suggested_topics: list[str] = Field(default_factory=list)

    @property
    def total_recipients(self) -> int:
        return sum(p.recipients for p in self.persona_metrics)

    @property
    def overall_open_rate(self) -> float:
        total = self.total_recipients
        if total == 0:
            return 0.0
        opens = sum(p.opens for p in self.persona_metrics)
        return round(opens / total * 100, 2)

    @property
    def overall_click_rate(self) -> float:
        total = self.total_recipients
        if total == 0:
            return 0.0
        clicks = sum(p.clicks for p in self.persona_metrics)
        return round(clicks / total * 100, 2)
