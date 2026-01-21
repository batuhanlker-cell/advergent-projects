# ICP Prospect Qualifier

Score company domains against your Ideal Customer Profile (ICP) criteria and output a prioritized CSV ready for enrichment.

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Set up your API key
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY

# 3. Add your domains to input/domains.csv

# 4. Run the scorer
python score_prospects.py input/domains.csv
```

## Usage

```bash
# Basic usage
python score_prospects.py input/domains.csv

# Custom output file
python score_prospects.py input/domains.csv --output my_results.csv

# Include detailed reasoning in output
python score_prospects.py input/domains.csv --include-reasoning

# Only output hot leads (score >= 80)
python score_prospects.py input/domains.csv --min-score 80

# Test with first 5 domains
python score_prospects.py input/domains.csv --limit 5

# Use a different model
python score_prospects.py input/domains.csv --model claude-sonnet-4-20250514
```

## Input Format

The input file can be:
- A text file with one domain per line
- A CSV with a `domain` column
- A CSV with domains in the first column

Example:
```
domain
gohighlevel.com
close.com
lemlist.com
```

## Output

The output CSV includes:

| Column | Description |
|--------|-------------|
| company_name | Company name |
| domain | Domain scored |
| linkedin_url | Best-guess LinkedIn company URL |
| total_score | Weighted score (0-100) |
| tier | hot_lead / warm_lead / review_needed / disqualified |
| company_description | What the company does |
| recommendation | Whether to pursue |
| *_score | Individual criterion scores |

## Customizing ICP Criteria

Edit `icp_criteria.json` to adjust:

- **target_verticals**: Industries/company types you're targeting
- **scoring_criteria**: What to score and how (with weights)
- **disqualifiers**: Auto-reject conditions
- **score_thresholds**: Tier cutoffs

## Tiers

- **hot_lead** (80+): High-priority, strong ICP fit
- **warm_lead** (60-79): Good fit, worth pursuing
- **review_needed** (40-59): Manual review recommended
- **disqualified** (<40): Does not fit ICP

## Workflow

1. Export a large list of domains (from a purchased list, scrape, etc.)
2. Run through the scorer
3. Focus on hot_lead and warm_lead tiers
4. Enrich with Apollo/Clearbit for contact info
5. Start outreach
