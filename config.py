import os
from dotenv import load_dotenv

load_dotenv(override=True)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
HUBSPOT_API_KEY = os.getenv("HUBSPOT_API_KEY", "")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///novamind.db")

LLM_MODEL = "gpt-4o"
BLOG_WORD_COUNT = 500
NEWSLETTER_VARIANTS = 3
HUBSPOT_BASE_URL = "https://api.hubapi.com"
METRICS_SIMULATION = True

PERSONAS = [
    {
        "id": "creative_professionals",
        "name": "Creative Professionals",
        "description": (
            "Senior designers, art directors, writers, and video editors (ages 25-34) "
            "at small agencies or freelancing. They juggle 3-5 client projects at once "
            "and lose hours to admin tasks like file organization, asset exporting, and "
            "revision tracking. They want concepts that are fresh, smart, and memorable. "
            "They care about creative freedom and audience impact. Their pain points are "
            "tight deadlines, staying relevant, and contradictory stakeholder feedback."
        ),
        "tone": "Inspirational, peer-to-peer, craft-focused",
        "format": (
            "Storytelling opening that feels like a creative peer talking. "
            "Include one visual or inspirational example. Keep it warm and relatable. "
            "Sign off casually — no corporate stiffness."
        ),
    },
    {
        "id": "brand_strategists",
        "name": "Brand Strategists",
        "description": (
            "Brand strategists and planning leads (ages 30-38) at creative agencies. "
            "They care deeply about brand identity and ensuring creative ideas align with "
            "the brand. They want consistency across all platforms and campaigns, and they "
            "derive ideas from audience insights. Their pain points are unclear briefs, "
            "poor cross-department communication, budget constraints, and spending 6+ hours "
            "a week manually pulling data into decks."
        ),
        "tone": "Insight-driven, framework-oriented, analytical but human",
        "format": (
            "Lead with a sharp insight or data point from the blog. "
            "Use a clear structure with takeaways. Reference the strategic 'why' behind "
            "the content. Sign off professionally but not stiffly."
        ),
    },
    {
        "id": "account_managers",
        "name": "Account Managers",
        "description": (
            "Senior account managers and account directors (ages 26-33) at creative agencies. "
            "They are client-facing and care about fostering relationships, trust, and "
            "responsiveness. They want on-time delivery and making sure all stakeholders are "
            "on the same page. Their pain points are unresponsive clients, misalignment between "
            "stakeholders, translating between client language and creative team language, "
            "and unrealistic deadlines or budgets."
        ),
        "tone": "Practical, empathetic, workflow-oriented, no fluff",
        "format": (
            "Open with a workflow pain point they'll immediately recognize. "
            "Include a mini checklist or 'try this today' action item. "
            "Keep it scannable — they have 200+ Slack messages waiting. "
            "Sign off with a concrete next step."
        ),
    },
]
