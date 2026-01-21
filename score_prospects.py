#!/usr/bin/env python3
"""
ICP Prospect Qualifier

Score a list of company domains against your Ideal Customer Profile criteria.
Outputs a prioritized CSV ready for enrichment with Apollo or similar tools.

Usage:
    python score_prospects.py input/domains.csv
    python score_prospects.py input/domains.csv --output results.csv
    python score_prospects.py input/domains.csv --include-reasoning
"""

import argparse
import os
import sys
from pathlib import Path

import anthropic
from dotenv import load_dotenv
from tqdm import tqdm

from src.scorer import load_icp_criteria, score_company
from src.csv_handler import read_domains, write_results, generate_output_filename


def main():
    parser = argparse.ArgumentParser(
        description="Score company domains against ICP criteria"
    )
    parser.add_argument(
        "input_file",
        help="Path to CSV or text file containing domains"
    )
    parser.add_argument(
        "--output", "-o",
        help="Output CSV path (default: auto-generated with timestamp)"
    )
    parser.add_argument(
        "--criteria", "-c",
        default="icp_criteria.json",
        help="Path to ICP criteria JSON file (default: icp_criteria.json)"
    )
    parser.add_argument(
        "--include-reasoning",
        action="store_true",
        help="Include detailed reasoning for each score in output"
    )
    parser.add_argument(
        "--model", "-m",
        default="claude-sonnet-4-20250514",
        help="Claude model to use (default: claude-sonnet-4-20250514)"
    )
    parser.add_argument(
        "--limit", "-l",
        type=int,
        default=None,
        help="Limit number of domains to process (for testing)"
    )
    parser.add_argument(
        "--min-score",
        type=int,
        default=None,
        help="Only output companies with score >= this value"
    )

    args = parser.parse_args()

    # Load environment variables
    load_dotenv()

    # Check for API key
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("Error: ANTHROPIC_API_KEY not found in environment or .env file")
        print("Create a .env file with: ANTHROPIC_API_KEY=your_key_here")
        sys.exit(1)

    # Validate input file
    if not Path(args.input_file).exists():
        print(f"Error: Input file not found: {args.input_file}")
        sys.exit(1)

    # Load ICP criteria
    print(f"Loading ICP criteria from {args.criteria}...")
    try:
        criteria = load_icp_criteria(args.criteria)
        print(f"  ICP: {criteria['name']}")
    except FileNotFoundError:
        print(f"Error: Criteria file not found: {args.criteria}")
        sys.exit(1)

    # Initialize Anthropic client
    client = anthropic.Anthropic(api_key=api_key)

    # Read domains
    print(f"Reading domains from {args.input_file}...")
    domains = list(read_domains(args.input_file))

    if args.limit:
        domains = domains[:args.limit]

    print(f"  Found {len(domains)} domains to process")

    if not domains:
        print("Error: No valid domains found in input file")
        sys.exit(1)

    # Process each domain
    print(f"\nScoring companies against ICP criteria using {args.model}...")
    results = []

    for domain in tqdm(domains, desc="Scoring"):
        try:
            result = score_company(domain, criteria, client, model=args.model)
            results.append(result)
        except Exception as e:
            print(f"\n  Error processing {domain}: {str(e)}")
            results.append({
                "domain": domain,
                "company_name": "Error",
                "company_description": str(e),
                "linkedin_url": "",
                "total_score": -1,
                "tier": "error",
                "scores": {},
                "recommendation": "Manual review needed"
            })

    # Filter by minimum score if specified
    if args.min_score is not None:
        original_count = len(results)
        results = [r for r in results if r.get("total_score", -1) >= args.min_score]
        print(f"\nFiltered to {len(results)} companies (score >= {args.min_score})")

    # Sort by score descending
    results.sort(key=lambda x: x.get("total_score", -1), reverse=True)

    # Generate output path
    output_path = args.output or generate_output_filename(args.input_file)

    # Write results
    print(f"\nWriting results to {output_path}...")
    write_results(results, output_path, include_reasoning=args.include_reasoning)

    # Summary
    print("\n" + "=" * 50)
    print("SCORING COMPLETE")
    print("=" * 50)

    tiers = {}
    for r in results:
        tier = r.get("tier", "unknown")
        tiers[tier] = tiers.get(tier, 0) + 1

    print(f"\nResults by tier:")
    for tier in ["hot_lead", "warm_lead", "review_needed", "disqualified", "unknown", "error"]:
        if tier in tiers:
            print(f"  {tier}: {tiers[tier]}")

    print(f"\nOutput saved to: {output_path}")
    print("\nNext steps:")
    print("  1. Review the CSV and filter by tier")
    print("  2. Enrich hot/warm leads with Apollo")
    print("  3. Start outreach!")


if __name__ == "__main__":
    main()
