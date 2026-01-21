import json
import anthropic
from typing import Optional


def load_icp_criteria(criteria_path: str = "icp_criteria.json") -> dict:
    """Load ICP criteria from JSON file."""
    with open(criteria_path, "r") as f:
        return json.load(f)


def build_scoring_prompt(domain: str, criteria: dict) -> str:
    """Build the prompt for Claude to score a company."""

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

    return f"""You are an ICP (Ideal Customer Profile) qualification expert. Analyze the company at domain "{domain}" and score them against the following criteria.

## Target Verticals
{verticals_text}

## Scoring Criteria
{criteria_text}

## Automatic Disqualifiers (score 0 if any apply)
{disqualifiers_text}

## Your Task

Based on your knowledge of the company at {domain}:

1. First, identify what the company does (product/service, target market, pricing model if known)
2. Check if any disqualifiers apply - if yes, explain which one and give total_score of 0
3. Score each criterion from 0-10 based on the scoring guides
4. Calculate weighted total score (max 100)

Respond in this exact JSON format:
{{
  "domain": "{domain}",
  "company_name": "Company Name",
  "company_description": "Brief 1-2 sentence description of what they do",
  "linkedin_url": "https://linkedin.com/company/companyname (best guess based on company name)",
  "disqualified": false,
  "disqualifier_reason": null,
  "scores": {{
    "offer_price": {{"score": 0, "reasoning": "brief explanation"}},
    "sales_model": {{"score": 0, "reasoning": "brief explanation"}},
    "buyer_reachability": {{"score": 0, "reasoning": "brief explanation"}},
    "pain_point_clarity": {{"score": 0, "reasoning": "brief explanation"}},
    "traction": {{"score": 0, "reasoning": "brief explanation"}},
    "vertical_fit": {{"score": 0, "reasoning": "brief explanation"}}
  }},
  "total_score": 0,
  "tier": "hot_lead|warm_lead|review_needed|disqualified",
  "recommendation": "Brief recommendation on whether to pursue"
}}

If you don't have enough information about this company, make reasonable inferences based on the domain name and any knowledge you have. If the domain is completely unknown, set total_score to -1 and tier to "unknown".

Return ONLY valid JSON, no other text."""


def score_company(
    domain: str,
    criteria: dict,
    client: anthropic.Anthropic,
    model: str = "claude-sonnet-4-20250514"
) -> dict:
    """Score a single company against ICP criteria using Claude."""

    prompt = build_scoring_prompt(domain, criteria)

    message = client.messages.create(
        model=model,
        max_tokens=1024,
        messages=[
            {"role": "user", "content": prompt}
        ]
    )

    response_text = message.content[0].text

    # Parse JSON response
    try:
        # Handle potential markdown code blocks
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0]
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0]

        result = json.loads(response_text.strip())
        return result
    except json.JSONDecodeError as e:
        return {
            "domain": domain,
            "company_name": "Parse Error",
            "company_description": f"Failed to parse response: {str(e)}",
            "linkedin_url": "",
            "disqualified": False,
            "disqualifier_reason": None,
            "scores": {},
            "total_score": -1,
            "tier": "error",
            "recommendation": "Manual review needed - parsing failed"
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
