import json
import ollama

from src.scraper import scrape_website, format_scraped_data


def load_icp_criteria(criteria_path: str = "icp_criteria.json") -> dict:
    """Load ICP criteria from JSON file."""
    with open(criteria_path, "r") as f:
        return json.load(f)


def build_scoring_prompt(domain: str, website_data: str, criteria: dict) -> str:
    """Build the prompt to score a company based on scraped website data."""

    criteria_text = ""
    for name, config in criteria["scoring_criteria"].items():
        criteria_text += f"\n### {name.replace('_', ' ').title()} (Weight: {config['weight']}%)\n"
        criteria_text += f"{config['description']}\n"
        criteria_text += "Scoring guide:\n"
        for score, desc in config["scoring_guide"].items():
            criteria_text += f"  - {score}: {desc}\n"

    disqualifiers_text = "\n".join(
        f"- {d['name']}: {d['description']}"
        for d in criteria["disqualifiers"]
    )

    verticals_text = "\n".join(f"- {v}" for v in criteria["target_verticals"])

    return f"""You are an ICP (Ideal Customer Profile) qualification expert. Analyze this company and score them against the criteria below.

## Company Information
Domain: {domain}

{website_data}

## Target Verticals
{verticals_text}

## Scoring Criteria
{criteria_text}

## Automatic Disqualifiers (score 0 if any apply)
{disqualifiers_text}

## Your Task

Based on the website data above:

1. Identify what the company does (product/service, target market, pricing model)
2. Check if any disqualifiers apply - if yes, explain which one and give total_score of 0
3. Score each criterion from 0-10 based on the scoring guides
4. Calculate weighted total score (max 100)

IMPORTANT scoring notes:
- "Book a demo" or "Schedule a call" CTAs indicate demo-based sales model (high score for sales_model)
- Pricing like $X,XXX+ or "contact sales" suggests high-ticket offers
- B2B SaaS targeting SMBs/agencies = good buyer_reachability (founders on LinkedIn/Meta)
- Enterprise-focused with "contact sales for pricing" = potential disqualifier if 6+ month cycles
- Look for pain points in headlines and descriptions

Respond in this exact JSON format:
{{
  "domain": "{domain}",
  "company_name": "Company Name (extract from title/content)",
  "company_description": "Brief 1-2 sentence description of what they do",
  "linkedin_url": "https://linkedin.com/company/companyname (derive from company name)",
  "disqualified": false,
  "disqualifier_reason": null,
  "scores": {{
    "offer_price": {{"score": 0, "reasoning": "brief explanation based on pricing signals"}},
    "sales_model": {{"score": 0, "reasoning": "brief explanation based on CTAs found"}},
    "buyer_reachability": {{"score": 0, "reasoning": "brief explanation of target buyer"}},
    "pain_point_clarity": {{"score": 0, "reasoning": "brief explanation from headlines/content"}},
    "traction": {{"score": 0, "reasoning": "brief explanation of social proof found"}},
    "vertical_fit": {{"score": 0, "reasoning": "brief explanation of fit"}}
  }},
  "total_score": 0,
  "tier": "hot_lead|warm_lead|review_needed|disqualified",
  "recommendation": "Brief recommendation on whether to pursue and why"
}}

Return ONLY valid JSON, no other text."""


def score_company(
    domain: str,
    criteria: dict,
    model: str = "llama3.1:8b",
    scraped_data: dict = None
) -> dict:
    """Score a single company against ICP criteria using Ollama.

    If scraped_data is not provided, will scrape the website first.
    """

    # Scrape website if data not provided
    if scraped_data is None:
        scraped_data = scrape_website(domain)

    # Format for prompt
    website_content = format_scraped_data(scraped_data)

    prompt = build_scoring_prompt(domain, website_content, criteria)

    response = ollama.chat(
        model=model,
        messages=[
            {"role": "user", "content": prompt}
        ],
        options={
            "temperature": 0.3,  # Lower temperature for more consistent JSON
        }
    )

    response_text = response["message"]["content"]

    # Parse JSON response
    try:
        # Handle potential markdown code blocks
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0]
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0]

        result = json.loads(response_text.strip())

        # Add scrape status to result
        result["scrape_success"] = scraped_data.get("error") is None
        result["scrape_error"] = scraped_data.get("error")

        # Check minimum thresholds - auto-disqualify if any score is below minimum
        min_thresholds = criteria.get("minimum_thresholds", {})
        scores = result.get("scores", {})

        for criterion, min_score in min_thresholds.items():
            criterion_data = scores.get(criterion, {})
            actual_score = criterion_data.get("score", 0)

            if actual_score < min_score:
                result["disqualified"] = True
                result["disqualifier_reason"] = f"{criterion} score ({actual_score}) below minimum ({min_score})"
                result["total_score"] = 0
                result["tier"] = "disqualified"
                break

        return result
    except json.JSONDecodeError as e:
        return {
            "domain": domain,
            "company_name": "Parse Error",
            "company_description": f"Failed to parse LLM response: {str(e)}",
            "linkedin_url": "",
            "disqualified": False,
            "disqualifier_reason": None,
            "scores": {},
            "total_score": -1,
            "tier": "error",
            "recommendation": "Manual review needed - parsing failed",
            "scrape_success": scraped_data.get("error") is None,
            "scrape_error": scraped_data.get("error")
        }


def calculate_tier(score: int, thresholds: dict) -> str:
    """Determine the tier based on score and thresholds."""
    if score < 0:
        return "unknown"
    if score >= thresholds["hot_lead"]:
        return "hot_lead"
    if score >= thresholds["warm_lead"]:
        return "warm_lead"
    if score >= thresholds["review_needed"]:
        return "review_needed"
    return "disqualified"
