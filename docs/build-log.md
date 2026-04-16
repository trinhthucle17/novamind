# NovaMind Build Log — April 14–15, 2026

## What We Built

A fully working AI-powered marketing content pipeline for **NovaMind**, a fictional AI startup that helps small creative agencies automate their daily workflows. The system takes a blog topic, generates content using AI, distributes personalized newsletters through HubSpot, tracks performance, and suggests what to write next.

---

## Setup & Configuration

- Installed **Homebrew** (Mac package manager), **Node.js**, and the **HubSpot CLI**
- Created a Python virtual environment and installed all project dependencies
- Set up API keys for **OpenAI** (GPT-4o) and **HubSpot** (Private App access token)
- Configured environment variables in `.env` (excluded from GitHub via `.gitignore`)
- Protected sensitive files: `.env`, `hubspot.config.yml`, and `*.db` are all git-ignored

---

## Files Created

| File | What It Does |
|------|-------------|
| `config.py` | Central settings — AI model, word counts, persona definitions |
| `main.py` | Command-line entry point to run the full pipeline |
| `app.py` | FastAPI web server with 6 API endpoints |
| `dashboard.py` | Streamlit visual dashboard with 3 tabs |
| `requirements.txt` | All Python library dependencies |
| `.env.example` | Template showing required API keys (no real keys) |
| `.gitignore` | Keeps secrets and generated files out of GitHub |
| `models/content.py` | Data structures for Blog Posts, Newsletters, Campaigns |
| `models/metrics.py` | Data structures for performance metrics |
| `pipeline/content_generator.py` | Talks to OpenAI to generate blog posts and newsletters |
| `pipeline/crm_manager.py` | Manages contacts and campaigns in HubSpot |
| `pipeline/distributor.py` | Sends the right newsletter to each audience segment |
| `pipeline/analytics.py` | Simulates engagement metrics and generates AI summaries |
| `pipeline/orchestrator.py` | Coordinates all four pipeline stages end-to-end |
| `storage/database.py` | SQLite database for campaigns, metrics, and AI summaries |
| `storage/file_store.py` | Saves blogs and newsletters as readable Markdown/JSON files |
| `data/contacts.json` | 15 mock contacts across 3 persona segments |
| `tests/test_content_generator.py` | Tests for AI content generation |
| `tests/test_crm_manager.py` | Tests for HubSpot CRM integration |
| `tests/test_distributor.py` | Tests for newsletter distribution |
| `tests/test_analytics.py` | Tests for performance analytics |
| `docs/architecture.md` | Detailed architecture and design document |

---

## Pipeline Flow (What Happens When You Run It)

1. **You enter a topic** (e.g., "AI in creative automation")
2. **AI generates content** — A 400-600 word blog post and 3 newsletter versions, each tailored to a different audience
3. **Contacts sync to HubSpot** — 15 mock contacts are created/updated in your HubSpot CRM, tagged by persona
4. **Newsletters are distributed** — Each persona segment receives their customized version
5. **Campaign is logged** — A note is created in HubSpot recording the campaign details
6. **Performance is analyzed** — Engagement metrics are simulated, stored, and analyzed by AI
7. **Next topics are suggested** — AI recommends 5 future blog topics based on what performed well

---

## Three Target Personas

| Persona | Who They Are | Newsletter Tone |
|---------|-------------|----------------|
| Creative Professionals | Freelance designers, writers, video editors | Inspirational, peer-to-peer, craft-focused |
| Brand Strategists | Brand strategists and planning leads at creative agencies | Insight-driven, framework-oriented, analytical |
| Account Managers | Senior account managers at creative agencies | Practical, empathetic, workflow-oriented |

---

## Issues We Solved Along the Way

1. **OpenAI API key not loading** — The `.env` file was edited in Cursor but not saved to disk. Fixed by saving with Cmd+S and adding `override=True` to the dotenv loader.

2. **OpenAI quota error** — The OpenAI account didn't have billing credits. Resolved by adding a payment method on platform.openai.com.

3. **HubSpot authentication expired** — The initial HubSpot key was from the CLI (`hs init`), not a Private App token. Fixed by creating a Private App in HubSpot Settings and using that access token instead.

4. **HubSpot custom property didn't exist** — The `novamind_persona` custom field couldn't be created because the Private App lacked the property-creation scope. Fixed with a graceful fallback that stores persona in the standard `jobtitle` field when the custom property isn't available.

5. **HubSpot timestamp format** — The notes API expected a Unix timestamp in milliseconds, not an ISO date string. Fixed by converting to epoch milliseconds.

---

## Successful Pipeline Run

The final pipeline run completed successfully:

- **Campaign ID**: `camp_20260414_052338`
- **Blog**: "Revolutionizing Creativity: The Role of AI in Creative Automation" (430 words)
- **Newsletters sent**: 15 total (5 per persona segment)
- **Contacts synced to HubSpot**: 15
- **Campaign logged to CRM**: Yes
- **Overall open rate**: 26.67% (simulated)
- **AI summary**: Generated with segment-specific insights and 3 actionable recommendations
- **Suggested next topics**: 5 AI-generated topic ideas based on performance

---

## Bonus Features Included

- **AI-driven content optimization** — Suggests next blog topics and headlines based on engagement trends
- **Web dashboard** (Streamlit) — Visual interface to run the pipeline, view content, and browse analytics charts
- **API server** (FastAPI) — 6 endpoints for programmatic access to the pipeline

---

## April 15 — Newsletter Distribution & CRM Logging

Distributed the hand-crafted newsletters from campaign `camp_20260414_051441` to all 15 contacts, segmented by persona, and logged the campaign to HubSpot CRM.

- **Campaign ID**: `camp_20260414_051441`
- **Blog**: "The Agency Work-Life Balance Myth (and the 20+ Hours of AI Automation That Could Make It Real)"
- **Send date**: 2026-04-15T17:56:56 UTC

| Persona Segment | Subject Line | Recipients | Status |
|----------------|-------------|:----------:|--------|
| Creative Professionals | Saving 9+ Hours a Week to Focus on Meaningful Campaigns That Connect With Your Audience | 5 | Delivered |
| Brand Strategists | 6+ Hours Back From Deck-Building. More Time Ensuring Every Touchpoint Tells the Same Brand Story. | 5 | Delivered |
| Account Managers | 3-5 Hours Back From CRM Updates and Follow-ups. More Time Building the Client Trust That Wins Renewals. | 5 | Delivered |

- **Total emails sent**: 15
- **Campaign logged to HubSpot CRM**: Yes (Note created with blog title, newsletter details, and send date)
- **Campaign JSON saved**: `data/campaigns/campaign_camp_20260414_051441.json`
- **SQLite record saved**: `novamind.db`

---

## April 15 — HubSpot Marketing Emails & Automation

### HubSpot Private App Scopes Added

Added `content` and `crm.lists.read` / `crm.lists.write` scopes to the NovaMind Private App to enable the Marketing Email API and Lists API.

### Contact Segmentation (Dynamic Lists)

Created 3 dynamic contact lists in HubSpot that auto-populate based on job title:

| List | List ID | Filter | Contacts |
|------|:-------:|--------|:--------:|
| NovaMind - Creative Professionals | 12 | jobtitle = "Creative Professionals" | 5 |
| NovaMind - Brand Strategists | 13 | jobtitle = "Brand Strategists" | 6 |
| NovaMind - Account Managers | 14 | jobtitle = "Account Managers" | 5 |

### Marketing Email Drafts

Created 3 marketing email drafts in HubSpot (Marketing > Email) for campaign `camp_20260414_051441`:

| Email | HubSpot ID | Recipient List | Personalization |
|-------|:----------:|:--------------:|:---------------:|
| Creative Professionals | 334783443698 | List 12 | `{{ contact.firstname }}` |
| Brand Strategists | 334783443701 | List 13 | `{{ contact.firstname }}` |
| Account Managers | 334783443704 | List 14 | `{{ contact.firstname }}` |

Each draft includes:
- Full newsletter body content (via `module-1-0-0` rich text widget)
- Personalized greeting using HubSpot's `{{ contact.firstname }}` token
- Recipient list pre-assigned by persona
- Sender set to **NovaMind <imthuctrinh@gmail.com>**

### CRM Note Associations

Updated `log_campaign_to_crm()` in `pipeline/crm_manager.py` to associate campaign notes with all contacts (using `associationTypeId: 202`), so notes appear on every contact's Activity timeline — not just as standalone objects.

### Blog Watcher Trigger (`trigger.py`)

Built an automated trigger script that watches for new blog posts and runs the full newsletter pipeline:

```
Blog .md file lands in data/content/
  → AI generates 3 persona-tailored newsletters
  → Contacts synced to HubSpot
  → Newsletters distributed to persona segments
  → Marketing emails created in HubSpot with content + recipient lists
  → Campaign logged to CRM
```

Two run modes:
- `python trigger.py` — Continuous watch mode (polls every 10s)
- `python trigger.py --once` — Process unprocessed blogs and exit

### Pipeline Orchestrator Updated

Updated `pipeline/orchestrator.py` to include HubSpot marketing email creation as Step 4/5, so running `python main.py --topic "..."` now creates the HubSpot marketing emails automatically as part of the end-to-end pipeline.

### Performance Logging & Analysis (Section 3)

Ran the analytics pipeline for `camp_20260414_051441`:

**Simulated engagement metrics** (stored to SQLite `metrics` table):

| Segment | Sent | Opens | Open Rate | Click Rate | Unsub Rate |
|---------|:----:|:-----:|:---------:|:----------:|:----------:|
| Creative Professionals | 5 | 2 | 40.0% | 0.0% | 0.0% |
| Brand Strategists | 6 | 1 | 16.67% | 0.0% | 0.0% |
| Account Managers | 5 | 1 | 20.0% | 0.0% | 0.0% |

**AI performance summary**: Creative Professionals showed the highest engagement (40% open rate). Brand Strategists need stronger CTAs and tailored subject lines. Recommendations include A/B testing and visual case studies.

**5 AI-suggested next topics** generated based on performance trends and stored in `ai_summaries` table.

**Performance report** created as a marketing email in HubSpot (ID: `334794977985`) alongside the 3 newsletter drafts, and also logged as a Note associated with all 15 contacts.

### Files Added/Modified Today

| File | Change |
|------|--------|
| `trigger.py` | New — blog watcher trigger for automated pipeline |
| `pipeline/crm_manager.py` | Added `create_marketing_email()`, `_get_all_hubspot_contact_ids()`, contact associations on notes, `PERSONA_LIST_IDS` mapping |
| `pipeline/orchestrator.py` | Added Step 4/5 — HubSpot marketing email creation |
| `pipeline/distributor.py` | No changes (already handles persona routing) |

---

## What's Left To Do

- [ ] Launch and test the Streamlit dashboard (`streamlit run dashboard.py`)
- [ ] Run the automated tests (`pytest tests/`)
- [ ] Write README with architecture overview, flow diagram, tools, and run instructions
- [ ] Commit all code to GitHub
- [ ] (Optional) Record a short Loom demo video walking through the pipeline
