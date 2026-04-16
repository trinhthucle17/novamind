"""Tests for the AI content generation module."""

import json
from unittest.mock import patch, MagicMock

from pipeline.content_generator import generate_blog_post, generate_newsletters, suggest_topics
from models.content import BlogPost


MOCK_BLOG_RESPONSE = json.dumps({
    "title": "How AI Is Reshaping Creative Automation",
    "outline": [
        "Introduction",
        "The Rise of AI in Creative Workflows",
        "Key Benefits for Agencies",
        "Getting Started",
        "Conclusion",
    ],
    "body": "Artificial intelligence is transforming how creative agencies operate. " * 30,
})

MOCK_NEWSLETTER_RESPONSE = json.dumps({
    "subject_line": "Your Creative Workflow, Supercharged",
    "body": "Hi there!\n\nWe just published a new blog post about AI automation. " * 5,
})


@patch("pipeline.content_generator._call_llm")
def test_generate_blog_post(mock_llm):
    mock_llm.return_value = MOCK_BLOG_RESPONSE

    blog = generate_blog_post("AI in creative automation")

    assert isinstance(blog, BlogPost)
    assert blog.title == "How AI Is Reshaping Creative Automation"
    assert len(blog.outline) == 5
    assert blog.word_count > 0
    assert blog.topic == "AI in creative automation"
    mock_llm.assert_called_once()


@patch("pipeline.content_generator._call_llm")
def test_generate_newsletters(mock_llm):
    mock_llm.return_value = MOCK_NEWSLETTER_RESPONSE

    blog = BlogPost(
        title="Test Blog",
        outline=["Intro", "Body", "Conclusion"],
        body="This is a test blog post about AI automation.",
        topic="AI automation",
    )

    newsletters = generate_newsletters(blog)

    assert len(newsletters) == 3
    personas = {nl.persona_id for nl in newsletters}
    assert personas == {"creative_professionals", "brand_strategists", "account_managers"}

    for nl in newsletters:
        assert nl.subject_line
        assert nl.body
        assert nl.blog_title == "Test Blog"


@patch("pipeline.content_generator._call_llm")
def test_suggest_topics_no_history(mock_llm):
    mock_llm.return_value = json.dumps([
        "Topic 1",
        "Topic 2",
        "Topic 3",
        "Topic 4",
        "Topic 5",
    ])

    topics = suggest_topics([])

    assert len(topics) == 5
    assert all(isinstance(t, str) for t in topics)


@patch("pipeline.content_generator._call_llm")
def test_suggest_topics_with_history(mock_llm):
    mock_llm.return_value = json.dumps(["Future Topic 1", "Future Topic 2"])

    past = [
        {"topic": "AI Automation", "open_rate": "35", "click_rate": "8", "best_persona": "Creative Professionals"},
    ]
    topics = suggest_topics(past)

    assert len(topics) == 2
    assert mock_llm.called
