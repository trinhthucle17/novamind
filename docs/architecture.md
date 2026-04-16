# NovaMind — Architecture & Design Document

## Overview

NovaMind is an AI-powered marketing content pipeline built for an early-stage AI startup targeting small creative agencies. The system automates the full lifecycle of content marketing: from topic ideation through content generation, audience-segmented distribution, and performance analysis.

## System Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                         NovaMind Pipeline                            │
│                                                                      │
│  ┌──────────┐    ┌───────────────┐    ┌───────────┐    ┌──────────┐ │
│  │  Topic    │───▶│ AI Content    │───▶│ CRM &     │───▶│Analytics │ │
│  │  Input    │    │ Generation    │    │ Delivery  │    │& Logging │ │
│  └──────────┘    └───────────────┘    └───────────┘    └──────────┘ │
│       │                │                    │                │       │
│       │           OpenAI API          HubSpot API      Feedback     │
│       │                │                    │             Loop      │
│       └────────────────┴────────────────────┴──────────────┘       │
│                          Optimization Loop                           │
└──────────────────────────────────────────────────────────────────────┘
```

## Component Breakdown

### 1. Content Generator (`pipeline/content_generator.py`)

**Responsibility:** Interface with OpenAI to produce marketing content.

**How it works:**
- Accepts a topic string as input
- Sends structured prompts to GPT-4o requesting JSON-formatted responses
- Generates a blog post (title, outline, 400-600 word body)
- Generates three newsletter variants, one per persona
- Includes topic suggestion engine for the optimization loop

**Key design decisions:**
- JSON response format ensures structured, parseable output
- Code-fence stripping handles model response inconsistencies
- Temperature set to 0.7 for creative but consistent output

### 2. CRM Manager (`pipeline/crm_manager.py`)

**Responsibility:** Manage contacts and campaigns in HubSpot.

**How it works:**
- Uses HubSpot's Contacts API v3 for CRUD operations
- Creates contacts with a custom `novamind_persona` property for segmentation
- Handles 409 Conflict responses by falling back to update
- Logs campaigns as notes attached to the CRM timeline

**Key design decisions:**
- Uses `httpx` for HTTP calls with 30-second timeout
- Graceful error handling — API failures don't crash the pipeline
- Contact segmentation uses local filtering for reliability

### 3. Distributor (`pipeline/distributor.py`)

**Responsibility:** Match newsletter variants to persona segments and send.

**How it works:**
- For each newsletter variant, looks up contacts matching that persona
- Simulates email delivery (HubSpot free tier doesn't support marketing sends)
- Logs every send with recipient, subject, timestamp, and delivery status
- Records the campaign in HubSpot via the notes API

### 4. Analytics Engine (`pipeline/analytics.py`)

**Responsibility:** Track engagement and generate AI-powered insights.

**How it works:**
- Simulates realistic engagement metrics per persona segment
- Different personas have different engagement profiles (creative pros tend to open more, etc.)
- Stores metrics in SQLite for historical trend analysis
- Uses GPT-4o to generate plain-English performance summaries
- Suggests future topics based on engagement patterns

**Key design decisions:**
- Simulation uses realistic distributions based on industry benchmarks
- Metrics stored per-persona to enable segment-level analysis
- AI summary uses lower temperature (0.5) for more factual analysis

### 5. Storage Layer (`storage/`)

**Database (`database.py`):**
- SQLite for zero-configuration persistence
- Three tables: campaigns, metrics, ai_summaries
- Initialized automatically on first import

**File Store (`file_store.py`):**
- Saves blogs as Markdown files for easy reading
- Saves newsletters as Markdown files per persona
- Saves full campaign data as JSON for programmatic access

### 6. Orchestrator (`pipeline/orchestrator.py`)

**Responsibility:** Coordinate the full pipeline end-to-end.

**Flow:**
1. Generate blog post and newsletter variants via AI
2. Save content to files (Markdown + JSON)
3. Sync contacts to HubSpot and segment by persona
4. Send newsletters to each segment
5. Simulate engagement metrics
6. Generate AI performance summary
7. Suggest next topics
8. Save campaign record to database

### 7. Web Layer

**API Server (`app.py`):**
- FastAPI with 6 endpoints
- Endpoints for running the pipeline, viewing campaigns, fetching analytics, and getting suggestions
- CORS enabled for dashboard access

**Dashboard (`dashboard.py`):**
- Streamlit-based single-page application
- Three tabs: Run Pipeline, Campaign History, Analytics
- Interactive charts using Plotly
- Real-time pipeline execution with progress feedback

## Data Flow

```
Topic Input
    │
    ▼
Content Generator (OpenAI GPT-4o)
    │
    ├──▶ Blog Post (Markdown + JSON)
    │
    ├──▶ Newsletter: Creative Professionals
    ├──▶ Newsletter: Brand Strategists
    └──▶ Newsletter: Account Managers
            │
            ▼
    CRM Manager (HubSpot API)
    ├── Create/Update Contacts
    ├── Tag by Persona
    └── Log Campaign
            │
            ▼
    Distributor
    ├── Match newsletter → persona segment
    └── Send to recipients
            │
            ▼
    Analytics Engine
    ├── Simulate engagement metrics
    ├── Store to SQLite
    ├── Generate AI summary (OpenAI)
    └── Suggest next topics (OpenAI)
            │
            ▼
    Dashboard / API Response
```

## Target Personas

| Persona | Description | Newsletter Tone |
|---------|-------------|-----------------|
| Creative Professionals | Freelance designers, writers, video editors | Inspirational, peer-to-peer, craft-focused |
| Brand Strategists | Brand strategists and planning leads at creative agencies | Insight-driven, framework-oriented, analytical |
| Account Managers | Senior account managers at creative agencies | Practical, empathetic, workflow-oriented |

## External APIs

| API | Purpose | Auth Method |
|-----|---------|-------------|
| OpenAI API (GPT-4o) | Content generation, performance analysis, topic suggestions | Bearer token |
| HubSpot Contacts API v3 | Contact management, segmentation | Private app access token |
| HubSpot Notes API v3 | Campaign logging | Private app access token |

## Assumptions

1. **Mock contacts** — 15 fictional contacts are used across 3 persona segments
2. **Simulated sends** — HubSpot free tier doesn't support marketing email sends; delivery is simulated with realistic logging
3. **Simulated metrics** — Engagement data uses randomized but realistic distributions based on industry benchmarks
4. **Single-user** — The system is designed for local single-user operation
5. **No authentication** — The API server runs without auth (development only)
