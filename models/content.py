from __future__ import annotations
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class BlogPost(BaseModel):
    title: str
    outline: list[str] = Field(default_factory=list)
    body: str
    word_count: int = 0
    topic: str = ""
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())

    def model_post_init(self, __context):
        if self.word_count == 0 and self.body:
            self.word_count = len(self.body.split())


class Newsletter(BaseModel):
    persona_id: str
    persona_name: str
    subject_line: str
    body: str
    blog_title: str = ""
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class Campaign(BaseModel):
    campaign_id: str
    topic: str
    blog: BlogPost
    newsletters: list[Newsletter] = Field(default_factory=list)
    contacts_synced: int = 0
    send_date: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    status: str = "draft"


class ContentRevision(BaseModel):
    original: str
    revised: str
    feedback: str
    persona_id: Optional[str] = None
