#!/usr/bin/env python3
"""
ICP Prospect Qualifier (Ollama Edition)

Score a list of company domains against your Ideal Customer Profile criteria.
Outputs a prioritized CSV ready for enrichment with Apollo or similar tools.

Requires Ollama running locally: https://ollama.com

Usage:
    python score_prospects.py input/domains.csv
    python score_prospects.py input/domains.csv --output results.csv
    python score_prospects.py input/domains.csv --model mistral
"""

import argparse
import subprocess
import sys
import time
from pathlib import Path

from tqdm import tqdm

from src.scorer import load_icp_criteria, score_company
from src.csv_handler import read_domains, write_results, generate_output_filename


def check_ollama_running() -> bool:
    """Check if Ollama is running."""
    try:
        import ollama
        ollama.list()
        return True
    except Exception:
        return False


def check_model_available(model: str) -> bool:
    """Check if the specified model is available."""
    try:
        import ollama
        models = ollama.list()
        model_names = [m.model.split(":")[0] for m in models.models]
        return model.split(":")[0] in model_names
    except Exception:
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Score company domains against ICP criteria using Ollama"
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
        default="llama3.1:8b",
        help="Ollama model to use (default: llama3.1:8b)"
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
    parser.add_argument(
        "--delay", "-d",
        type=float,
        default=1.0,
        help="Delay in seconds between requests to avoid rate limiting (default: 1.0)"
    )

    args = parser.parse_args()

    # Check Ollama is running
    print("Checking Ollama connection...")
    if not check_ollama_running():
        print("Error: Ollama is not running.")
        print("\nTo start Ollama:")
        print("  1. Install: curl -fsSL https://ollama.com/install.sh | sh")
        print("  2. Start: ollama serve")
        print("  3. Pull model: ollama pull llama3.1:8b")
        sys.exit(1)

    # Check model is available
    if not check_model_available(args.model):
        print(f"Model '{args.model}' not found. Pulling it now...")
        try:
            subprocess.run(["ollama", "pull", args.model], check=True)
        except subprocess.CalledProcessError:
            print(f"Error: Failed to pull model '{args.model}'")
            print(f"Try manually: ollama pull {args.model}")
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
    print(f"\nScoring companies using Ollama ({args.model})...")
    print(f"(Delay: {args.delay}s between requests)\n")
    results = []

    for i, domain in enumerate(tqdm(domains, desc="Scoring")):
        try:
            result = score_company(domain, criteria, model=args.model)
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

        # Delay between requests (skip after last one)
        if args.delay > 0 and i < len(domains) - 1:
            time.sleep(args.delay)

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
