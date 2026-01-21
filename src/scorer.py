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
            criteria_text += f"  - Score {score}: {desc}\n"

    disqualifiers_text = "\n".join(
        f"- {d['name']}: {d['description']}"
        for d in criteria["disqualifiers"]
    )

    verticals_text = "\n".join(f"- {v}" for v in criteria["target_verticals"])

    return f"""You are an ICP (Ideal Customer Profile) qualification expert for Advergent, a paid ads agency. Analyze this company and score them against the criteria below.

SCORING PHILOSOPHY: We prioritize signals we can reliably detect (vertical fit, sales model, traction) over signals that are often hidden (exact pricing). When information is unavailable, give benefit of doubt to companies that match our core ICP patterns.

## Company Information
Domain: {domain}

{website_data}

## Target Verticals
{verticals_text}

## Scoring Criteria (5 Metrics)
{criteria_text}

## Automatic Disqualifiers
{disqualifiers_text}

## Your Task

Based on the website data above:

1. Identify what the company does (product/service, target market, pricing model if visible)
2. Check if any disqualifiers apply - if yes, set disqualified=true with reason
3. Score each of the 5 criteria from 0-10 based on the scoring guides
4. For offer_price: If pricing is NOT visible:
   - If sales_model >= 8, set offer_price = 8
   - Else if vertical_fit >= 8 AND sales_model >= 6, set offer_price = 7
   - Only use 5 if genuinely unclear mid-market positioning

IMPORTANT SCORING NOTES:
- "Book a Demo" / "Talk to Sales" CTAs = high sales_model score (8-10)
- No visible pricing + demo model = high offer_price score (8)
- Customer logos, testimonials, case studies = traction signals
- B2B SaaS, agencies, consultancies = high vertical_fit
- Founders/CEOs/marketers as buyers = high buyer_reachability
- Developers/engineers as buyers = low buyer_reachability

Respond in this exact JSON format:
{{
  "domain": "{domain}",
  "company_name": "Company Name",
  "company_description": "Brief 1-2 sentence description",
  "linkedin_url": "https://linkedin.com/company/companyname",
  "disqualified": false,
  "disqualifier_reason": null,
  "scores": {{
    "vertical_fit": {{"score": 0, "reasoning": "brief explanation"}},
    "sales_model": {{"score": 0, "reasoning": "brief explanation"}},
    "traction": {{"score": 0, "reasoning": "brief explanation"}},
    "buyer_reachability": {{"score": 0, "reasoning": "brief explanation"}},
    "offer_price": {{"score": 0, "reasoning": "brief explanation"}}
  }},
  "recommendation": "Specific action recommendation"
}}

Return ONLY valid JSON, no other text."""


def calculate_total_score(scores: dict) -> float:
    """Calculate weighted total score based on V2 formula."""
    weights = {
        "vertical_fit": 0.25,
        "sales_model": 0.25,
        "traction": 0.25,
        "buyer_reachability": 0.15,
        "offer_price": 0.10
    }

    weighted_sum = 0
    for metric, weight in weights.items():
        score_data = scores.get(metric, {})
        score = score_data.get("score", 0) if isinstance(score_data, dict) else 0
        weighted_sum += score * weight

    return weighted_sum * 10


def apply_confidence_multiplier(total_score: float, scores: dict) -> tuple[float, str]:
    """Apply confidence multiplier based on core metrics.

    Returns (adjusted_score, confidence_level)
    """
    core_metrics = ["vertical_fit", "sales_model", "traction"]

    # Count core metrics >= 8
    high_core_count = 0
    for metric in core_metrics:
        score_data = scores.get(metric, {})
        score = score_data.get("score", 0) if isinstance(score_data, dict) else 0
        if score >= 8:
            high_core_count += 1

    # Check if any metric <= 2
    any_low = False
    for metric, score_data in scores.items():
        score = score_data.get("score", 0) if isinstance(score_data, dict) else 0
        if score <= 2:
            any_low = True
            break

    # Apply multiplier
    if high_core_count >= 3:
        adjusted_score = total_score * 1.10
        confidence_level = "high"
    elif high_core_count >= 2 and not any_low:
        adjusted_score = total_score * 1.05
        confidence_level = "medium"
    else:
        adjusted_score = total_score
        confidence_level = "low" if high_core_count == 0 else "medium"

    # Cap at 100
    return min(adjusted_score, 100), confidence_level


def determine_tier(total_score: float, scores: dict, thresholds: dict) -> str:
    """Determine tier based on score and alternate hot lead condition."""

    if total_score >= thresholds.get("hot_lead", 75):
        return "hot_lead"

    # Check alternate hot lead condition: score 65-74 with all core metrics >= 7
    alt_threshold = thresholds.get("hot_lead_alternate", {})
    min_score = alt_threshold.get("min_score", 65)
    core_min = alt_threshold.get("core_metrics_min", 7)

    if total_score >= min_score:
        core_metrics = ["vertical_fit", "sales_model", "traction"]
        all_core_above_min = True
        for metric in core_metrics:
            score_data = scores.get(metric, {})
            score = score_data.get("score", 0) if isinstance(score_data, dict) else 0
            if score < core_min:
                all_core_above_min = False
                break
        if all_core_above_min:
            return "hot_lead"

    if total_score >= thresholds.get("warm_lead", 55):
        return "warm_lead"

    if total_score >= thresholds.get("review_needed", 40):
        return "review_needed"

    return "disqualified"


def apply_offer_price_inference(scores: dict) -> dict:
    """Apply offer_price inference rules if pricing was unclear."""
    offer_price_data = scores.get("offer_price", {})
    offer_score = offer_price_data.get("score", 0) if isinstance(offer_price_data, dict) else 0

    sales_model_data = scores.get("sales_model", {})
    sales_score = sales_model_data.get("score", 0) if isinstance(sales_model_data, dict) else 0

    vertical_fit_data = scores.get("vertical_fit", {})
    vertical_score = vertical_fit_data.get("score", 0) if isinstance(vertical_fit_data, dict) else 0

    # Only apply inference if offer_price is in the "unclear" range (5-7)
    if 5 <= offer_score <= 7:
        if sales_score >= 8:
            scores["offer_price"]["score"] = 8
            scores["offer_price"]["reasoning"] += " [Inferred: sales_model >= 8]"
        elif vertical_score >= 8 and sales_score >= 6:
            scores["offer_price"]["score"] = 7
            scores["offer_price"]["reasoning"] += " [Inferred: vertical_fit >= 8 & sales_model >= 6]"

    return scores


def score_company(
    domain: str,
    criteria: dict,
    model: str = "llama3.1:8b",
    scraped_data: dict = None
) -> dict:
    """Score a single company against ICP criteria using Ollama."""

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
            "temperature": 0.3,
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

        # Add scrape status
        result["scrape_success"] = scraped_data.get("error") is None
        result["scrape_error"] = scraped_data.get("error")

        scores = result.get("scores", {})

        # Apply offer_price inference
        scores = apply_offer_price_inference(scores)
        result["scores"] = scores

        # Calculate total score
        total_score = calculate_total_score(scores)

        # Apply confidence multiplier
        total_score, confidence_level = apply_confidence_multiplier(total_score, scores)

        result["total_score"] = round(total_score, 1)
        result["confidence_level"] = confidence_level

        # Determine tier
        if result.get("disqualified"):
            result["tier"] = "disqualified"
            result["total_score"] = 0
        else:
            result["tier"] = determine_tier(total_score, scores, criteria.get("score_thresholds", {}))

        # Check minimum thresholds - auto-disqualify if below
        min_thresholds = criteria.get("minimum_thresholds", {})
        for criterion, min_score in min_thresholds.items():
            criterion_data = scores.get(criterion, {})
            actual_score = criterion_data.get("score", 0) if isinstance(criterion_data, dict) else 0

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
            "confidence_level": "low",
            "recommendation": "Manual review needed - parsing failed",
            "scrape_success": scraped_data.get("error") is None,
            "scrape_error": scraped_data.get("error")
        }
