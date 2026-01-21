# ICP Prospect Qualifier (Free - Ollama Edition)

Score company domains against your Ideal Customer Profile (ICP) criteria using a local LLM. **No API costs.**

## Quick Start

```bash
# 1. Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# 2. Pull a model (one-time, ~4GB download)
ollama pull llama3.1:8b

# 3. Install Python dependencies
pip install -r requirements.txt

# 4. Add your domains to input/domains.csv

# 5. Run the scorer
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

# Use a different model (smaller/faster)
python score_prospects.py input/domains.csv --model mistral
```

## Recommended Models

| Model | Size | Speed | Quality |
|-------|------|-------|---------|
| `llama3.1:8b` | 4.7GB | Medium | Best |
| `mistral` | 4.1GB | Fast | Good |
| `llama3.1:70b` | 40GB | Slow | Excellent |

Pull with: `ollama pull <model-name>`

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

1. Get a large list of domains (purchased list, export, etc.)
2. Run through the scorer: `python score_prospects.py input/domains.csv`
3. Focus on hot_lead and warm_lead tiers
4. Enrich with Apollo for contact info + LinkedIn URLs
5. Start outreach

## Troubleshooting

**"Ollama is not running"**
```bash
ollama serve  # Start Ollama in a terminal
```

**Model not found**
```bash
ollama pull llama3.1:8b
```

**Slow performance**
- Use a smaller model: `--model mistral`
- Limit domains for testing: `--limit 10`
