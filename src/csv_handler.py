import csv
from pathlib import Path
from typing import Generator
from datetime import datetime


def read_domains(input_path: str) -> Generator[str, None, None]:
    """Read domains from a CSV or text file.

    Supports:
    - Plain text file with one domain per line
    - CSV with a 'domain' column
    - CSV with domain in first column (no header)
    """
    path = Path(input_path)

    with open(path, "r", encoding="utf-8") as f:
        # Try to detect if it's a CSV with headers
        first_line = f.readline().strip()
        f.seek(0)

        # Check if first line looks like a header
        if "," in first_line or first_line.lower() in ["domain", "domains", "url", "website"]:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames or []

            # Find the domain column
            domain_col = None
            for col in ["domain", "domains", "url", "website", "site"]:
                if col in [fn.lower() for fn in fieldnames]:
                    domain_col = fieldnames[[fn.lower() for fn in fieldnames].index(col)]
                    break

            if domain_col:
                for row in reader:
                    domain = clean_domain(row[domain_col])
                    if domain:
                        yield domain
            else:
                # Use first column
                f.seek(0)
                reader = csv.reader(f)
                next(reader, None)  # Skip header
                for row in reader:
                    if row:
                        domain = clean_domain(row[0])
                        if domain:
                            yield domain
        else:
            # Plain text file, one domain per line
            for line in f:
                domain = clean_domain(line)
                if domain:
                    yield domain


def clean_domain(raw: str) -> str:
    """Clean and normalize a domain string."""
    domain = raw.strip().lower()

    # Remove protocol
    for prefix in ["https://", "http://", "www."]:
        if domain.startswith(prefix):
            domain = domain[len(prefix):]

    # Remove trailing slash and path
    domain = domain.split("/")[0]

    # Remove whitespace
    domain = domain.strip()

    return domain if domain else ""


def write_results(
    results: list[dict],
    output_path: str,
    include_reasoning: bool = False
) -> str:
    """Write scoring results to CSV.

    Returns the path to the created file.
    """
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    # Define columns
    base_columns = [
        "company_name",
        "domain",
        "linkedin_url",
        "total_score",
        "tier",
        "company_description",
        "recommendation",
        "disqualified",
        "disqualifier_reason"
    ]

    score_columns = [
        "offer_price_score",
        "sales_model_score",
        "buyer_reachability_score",
        "pain_point_clarity_score",
        "traction_score",
        "vertical_fit_score"
    ]

    reasoning_columns = [
        "offer_price_reasoning",
        "sales_model_reasoning",
        "buyer_reachability_reasoning",
        "pain_point_clarity_reasoning",
        "traction_reasoning",
        "vertical_fit_reasoning"
    ] if include_reasoning else []

    columns = base_columns + score_columns + reasoning_columns

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()

        for result in results:
            row = {
                "company_name": result.get("company_name", ""),
                "domain": result.get("domain", ""),
                "linkedin_url": result.get("linkedin_url", ""),
                "total_score": result.get("total_score", -1),
                "tier": result.get("tier", "unknown"),
                "company_description": result.get("company_description", ""),
                "recommendation": result.get("recommendation", ""),
                "disqualified": result.get("disqualified", False),
                "disqualifier_reason": result.get("disqualifier_reason", "")
            }

            # Add score columns
            scores = result.get("scores", {})
            for criterion in ["offer_price", "sales_model", "buyer_reachability",
                            "pain_point_clarity", "traction", "vertical_fit"]:
                score_data = scores.get(criterion, {})
                row[f"{criterion}_score"] = score_data.get("score", "")
                if include_reasoning:
                    row[f"{criterion}_reasoning"] = score_data.get("reasoning", "")

            writer.writerow(row)

    return str(path)


def generate_output_filename(input_path: str) -> str:
    """Generate a timestamped output filename."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    input_name = Path(input_path).stem
    return f"output/scored_{input_name}_{timestamp}.csv"
