"""
NovaMind — AI-Powered Marketing Content Pipeline
Run the full pipeline from the command line.

Usage:
    python main.py --topic "AI in creative automation"
"""

import argparse
import json
import sys

from pipeline.orchestrator import run_pipeline


def main():
    parser = argparse.ArgumentParser(
        description="NovaMind AI Marketing Pipeline",
    )
    parser.add_argument(
        "--topic",
        type=str,
        required=True,
        help='Blog topic to generate content for (e.g., "AI in creative automation")',
    )
    args = parser.parse_args()

    result = run_pipeline(args.topic)

    print("\n--- Pipeline Result (JSON) ---")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
