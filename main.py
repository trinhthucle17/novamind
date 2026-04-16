"""
NovaMind — AI-Powered Marketing Content Pipeline
Run the full pipeline from the command line.

Usage:
    python main.py --topic "AI in creative automation"
    python main.py --stats camp_20260414_051441
    python main.py --stats camp_20260414_051441 --history
"""

import argparse
import json
import os
import sys

from pipeline.orchestrator import run_pipeline


def _load_campaign_hubspot_emails(campaign_id: str) -> list[dict]:
    """Load hubspot_emails from the campaign JSON file."""
    path = os.path.join("data", "campaigns", f"campaign_{campaign_id}.json")
    if not os.path.exists(path):
        print(f"  Campaign file not found: {path}")
        return []
    with open(path) as f:
        data = json.load(f)
    return data.get("hubspot_emails", [])


def run_stats(campaign_id: str, show_history: bool = False):
    """Fetch real newsletter performance data from HubSpot and store it."""
    from pipeline.analytics import (
        fetch_hubspot_metrics,
        print_hubspot_stats,
        show_historical_comparison,
    )

    hubspot_emails = _load_campaign_hubspot_emails(campaign_id)
    if not hubspot_emails:
        print(f"  No HubSpot email IDs found for campaign {campaign_id}.")
        print("  Make sure the campaign JSON has a 'hubspot_emails' field.")
        sys.exit(1)

    stats = fetch_hubspot_metrics(campaign_id, hubspot_emails)
    print_hubspot_stats(stats, campaign_id)

    if show_history:
        show_historical_comparison(campaign_id)


def main():
    parser = argparse.ArgumentParser(
        description="NovaMind AI Marketing Pipeline",
    )
    parser.add_argument(
        "--topic",
        type=str,
        help='Blog topic to generate content for (e.g., "AI in creative automation")',
    )
    parser.add_argument(
        "--stats",
        type=str,
        metavar="CAMPAIGN_ID",
        help="Fetch real newsletter performance from HubSpot for a campaign",
    )
    parser.add_argument(
        "--history",
        action="store_true",
        help="Show historical comparison when used with --stats",
    )
    args = parser.parse_args()

    if args.stats:
        run_stats(args.stats, show_history=args.history)
    elif args.topic:
        result = run_pipeline(args.topic)
        print("\n--- Pipeline Result (JSON) ---")
        print(json.dumps(result, indent=2))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
