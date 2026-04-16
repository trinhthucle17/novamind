"""
NovaMind — FastAPI server providing API endpoints for the dashboard.

Run with:
    uvicorn app:app --reload --port 8000
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from pipeline.orchestrator import run_pipeline
from pipeline.content_generator import suggest_topics
from storage.database import (
    get_all_campaigns,
    get_campaign,
    get_metrics,
    get_ai_summary,
    get_historical_metrics,
)

app = FastAPI(
    title="NovaMind API",
    description="AI-Powered Marketing Content Pipeline",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class PipelineRequest(BaseModel):
    topic: str


@app.get("/")
def root():
    return {"service": "NovaMind API", "status": "running"}


@app.post("/pipeline/run")
def run_pipeline_endpoint(request: PipelineRequest):
    """Trigger the full pipeline with a topic."""
    try:
        result = run_pipeline(request.topic)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/campaigns")
def list_campaigns():
    """List all campaigns, most recent first."""
    return get_all_campaigns()


@app.get("/content/{campaign_id}")
def get_content(campaign_id: str):
    """Retrieve generated content for a campaign."""
    campaign = get_campaign(campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return campaign


@app.get("/analytics/{campaign_id}")
def get_analytics(campaign_id: str):
    """Get performance metrics and AI summary for a campaign."""
    metrics = get_metrics(campaign_id)
    summary = get_ai_summary(campaign_id)
    if not metrics:
        raise HTTPException(status_code=404, detail="No metrics found for this campaign")
    return {
        "campaign_id": campaign_id,
        "metrics": metrics,
        "ai_summary": summary,
    }


@app.get("/suggestions/topics")
def get_topic_suggestions():
    """Get AI-suggested next blog topics based on past performance."""
    campaigns = get_all_campaigns()
    past_data = []
    for c in campaigns[:5]:
        past_data.append({
            "topic": c.get("topic", ""),
            "open_rate": "N/A",
            "click_rate": "N/A",
            "best_persona": "N/A",
        })
    topics = suggest_topics(past_data)
    return {"suggested_topics": topics}
