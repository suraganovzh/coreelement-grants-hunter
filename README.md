# Grant Hunter AI

Success-driven grant discovery system for **Core Element AI** — $0/month hybrid architecture using GitHub Actions (cloud scraping) + local ARM models (AI analysis).

## Core Principle

We don't just find grants — we **win** them. The system learns from awarded grants to predict which new opportunities have the highest win probability, then generates tailored applications.

**Metric that matters: $ won, not # applied.**

**Strategy: 1-2 quality applications per week, not 20 mediocre ones.**

## Architecture

```
┌─────────────────────────────────────────┐
│ 1. GitHub Actions (Cloud, Free)         │
│    - Daily scraping (9 AM UTC)          │
│    - Weekly winner analysis (Sundays)   │
│    - Commits data to repo as JSON       │
└────────────────┬────────────────────────┘
                 │ git commit/push
┌────────────────▼────────────────────────┐
│ 2. GitHub Repo (Storage, Free)          │
│    - data/grants.json (new grants)      │
│    - data/winners*.json (awarded grants)│
│    - data/patterns.json (success data)  │
│    - data/analyzed.json (scored grants) │
│    - drafts/*.md (applications)         │
└────────────────┬────────────────────────┘
                 │ git pull
┌────────────────▼────────────────────────┐
│ 3. Surface ARM (Local, Free)            │
│    - Llama 3.2 3B: Filter grants (~0.5s)│
│    - Llama 3.1 8B: Analyze + predict    │
│    - Gemma 2 9B: Generate drafts        │
│    - Dashboard + Telegram notifications │
└─────────────────────────────────────────┘
```

## LLM Cascade

All AI tasks use a cascade with automatic fallback:

| Priority | Provider | Filter Model | Analyze Model | Generate Model |
|----------|----------|-------------|---------------|----------------|
| 1 (local) | Ollama | llama3.2:3b | llama3.1:8b | gemma2:9b |
| 2 (cloud) | Groq | llama-3.1-8b-instant | llama-3.1-70b-versatile | mixtral-8x7b-32768 |
| 3 (cloud) | Gemini | gemini-2.0-flash | gemini-1.5-pro | gemini-1.5-pro |
| 4 (fallback) | Rules | keyword matching | fit scorer | templates |

## Cost Breakdown

| Component | Cost |
|-----------|------|
| GitHub Actions | $0 (2,000 min/month free) |
| GitHub Repo | $0 (free private repo) |
| Ollama Models | $0 (local) |
| Groq / Gemini | $0 (free tiers) |
| Telegram Bot | $0 |
| Surface compute | $0 (your hardware) |
| **TOTAL** | **$0/month** |

## Quick Start

### 1. Prerequisites (Surface ARM)

```bash
# Install Ollama (Windows ARM)
winget install Ollama.Ollama

# Pull models
ollama pull llama3.2:3b      # Fast filter
ollama pull llama3.1:8b      # Deep analysis
ollama pull gemma2:9b        # Draft generation
```

### 2. Clone and Install

```bash
git clone https://github.com/suraganovzh/-oreelement-grants-hynter-.git
cd -oreelement-grants-hynter-
pip install -r requirements.txt
```

### 3. Configure Environment

```bash
cp .env.example .env
# Edit .env with your credentials:
#   TELEGRAM_BOT_TOKEN — from @BotFather
#   TELEGRAM_CHAT_ID — from getUpdates API
#   GROQ_API_KEY — from console.groq.com
#   GEMINI_API_KEY — from aistudio.google.com/apikey
#   SAM_GOV_API_KEY — from sam.gov
```

### 4. Enable GitHub Actions

1. Go to repo Settings > Actions > Enable workflows
2. Add secrets: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `SAM_GOV_API_KEY`
3. Manually trigger: Actions > Daily Grant Scraping > Run workflow

### 5. Daily Usage (Surface)

```bash
# Pull latest scraped data, filter, analyze, notify
python -m src.local.daily_workflow

# Generate draft for a specific grant
python -m src.local.generate --grant-id <id>

# List available grants for drafting
python -m src.local.generate --list

# Open dashboard
# Windows:
start dashboard/index.html
# Or serve locally:
python -m http.server 8080
# Then open http://localhost:8080/dashboard/
```

## Dashboard

Open `dashboard/index.html` in your browser for a local visual interface:

- **Summary cards** — copy_now count, test_first count, total potential, urgent deadlines
- **Priority grants table** — sorted by win probability, filterable by priority
- **Winners panel** — recent awarded grants from 7+ federal sources
- **Patterns panel** — top keywords and funders with frequency bars
- **Application tracker** — track your submissions: Draft > Submitted > Won/Lost with win rate

Dark theme, no external dependencies, works with `file://` or localhost.

## Project Structure

```
-oreelement-grants-hynter-/
├── .github/workflows/
│   ├── daily_scrape.yml          # Daily grant scraping (9 AM UTC)
│   ├── weekly_winners.yml        # Weekly winner analysis (Sunday 10 AM UTC)
│   └── deadline_reminders.yml    # Telegram deadline alerts
├── src/
│   ├── scrapers/                 # Grant source scrapers (7+ sources)
│   │   ├── grants_gov.py         # US Federal grants
│   │   ├── sbir_scraper.py       # SBIR/STTR
│   │   ├── eu_horizon.py         # EU Horizon Europe
│   │   ├── foundation_scraper.py # Private foundations
│   │   ├── corporate_grants.py   # Mining/energy companies
│   │   ├── world_bank.py         # International development
│   │   ├── kazakhstan_scraper.py # Kazakhstan sources
│   │   └── winners/              # Awarded grant scrapers
│   │       ├── grants_gov_awards.py
│   │       ├── sbir_awards.py
│   │       ├── usaspending.py
│   │       ├── nsf_awards.py
│   │       ├── doe_awards.py
│   │       ├── nih_reporter.py
│   │       └── sam_gov.py
│   ├── analyzers/                # Analysis pipeline
│   │   ├── pattern_extractor.py  # Learn from winners
│   │   ├── eligibility_checker.py
│   │   ├── fit_scorer.py
│   │   ├── complexity_scorer.py
│   │   └── similar_finder.py
│   ├── local/                    # ARM processing (Surface)
│   │   ├── daily_workflow.py     # Main daily pipeline
│   │   ├── llm_cascade.py       # Centralised LLM cascade
│   │   ├── filter.py            # Llama 3.2 3B filter
│   │   ├── analyze.py           # Llama 3.1 8B analysis
│   │   ├── generate.py          # Gemma 2 9B drafts
│   │   └── telegram_notify.py   # Push notifications
│   ├── bot/                      # Telegram bot (full interactive)
│   │   └── telegram_notify.py   # Re-export for convenience
│   ├── generators/               # Content generation templates
│   ├── database/                 # SQLAlchemy models
│   └── utils/                    # Shared utilities
├── dashboard/
│   └── index.html                # Local visual dashboard
├── config/                       # YAML configuration
│   ├── core_element_profile.yaml # Company profile
│   ├── sources.yaml              # Grant sources
│   └── keywords.yaml             # Search keywords
├── templates/                    # Grant application templates
├── data/                         # Git-tracked scraped data
├── drafts/                       # Generated application drafts
├── tests/                        # Test suite
├── requirements.txt
├── .env.example
└── README.md
```

## Pipeline Flow

```
GitHub Actions (daily 9 AM UTC):
  Scrape 30+ sources → data/grants.json
  Scrape winners (weekly) → data/winners*.json → data/patterns.json

Surface ARM (on-demand):
  git pull
  → Llama 3.2 3B: Filter 50 grants → 12 qualified (~25s)
  → Llama 3.1 8B: Analyze 12 grants → 3 copy_now, 5 test_first (~36s)
  → Telegram: Send summary + priority grants
  → Gemma 2 9B (optional): Generate drafts for top 2-3 (~90s)
  → git push results
```

## Data Structures

### analyzed.json (your main working file)
```json
{
  "id": "abc123",
  "title": "SBIR Phase I - AI for Critical Mineral Exploration",
  "funder": "DOE",
  "url": "https://grants.gov/...",
  "deadline": "2026-04-15",
  "amount_min": 50000,
  "amount_max": 250000,
  "analysis": {
    "priority": "copy_now",
    "win_probability": 22,
    "pattern_match_score": 85,
    "success_factors": {
      "keywords": ["critical minerals", "AI", "exploration"],
      "value_props": ["$17M+ savings"],
      "partnerships": ["Colorado School of Mines"]
    },
    "risk_factors": ["High competition"],
    "llm_source": "ollama"
  }
}
```

### patterns.json (learned from winners)
```json
{
  "keyword_patterns": [{"keyword": "critical minerals", "frequency": 0.45, "count": 23}],
  "funder_patterns": [{"funder": "DOE SBIR Phase 1", "total_awards": 15, "avg_amount": 200000}],
  "company_patterns": [{"company": "GeoTech AI Inc.", "total_wins": 3, "total_amount": 750000}]
}
```

## Grant Sources

**US Federal:** Grants.gov, SBIR/STTR, NSF, DOE, NIH, ARPA-E, USASpending, SAM.gov

**Private:** Google AI, Microsoft, Amazon, BHP, Rio Tinto, Anglo American, Breakthrough Energy

**International:** EU Horizon Europe, EIT RawMaterials, World Bank, IFC, ADB, EBRD, Green Climate Fund

**Kazakhstan:** Astana Hub, QazInnovations/NATD, Ministry of Digital Development

## Success-Driven Features

**Winner Analysis** — Weekly scraping of awarded grants from 7+ federal sources.

**Pattern Extraction** — Top keywords, funder preferences, typical amounts, repeat winners.

**Priority Classification:**
- `copy_now` — Win probability >15%, pattern match >80%, apply immediately
- `test_first` — Win probability 8-15%, worth investigating
- `skip` — Win probability <8%, don't waste time

## GitHub Actions

| Workflow | Schedule | Description |
|----------|----------|-------------|
| `daily_scrape.yml` | 9 AM UTC daily | Scrape new grants |
| `weekly_winners.yml` | 10 AM UTC Sunday | Scrape winners + extract patterns |
| `deadline_reminders.yml` | 9 AM UTC daily | Telegram deadline alerts |

## GitHub Secrets

| Secret | Required | Description |
|--------|----------|-------------|
| `TELEGRAM_BOT_TOKEN` | Yes | Telegram bot token |
| `TELEGRAM_CHAT_ID` | Yes | Target chat ID |
| `GROQ_API_KEY` | Yes | Groq cloud LLM fallback |
| `GEMINI_API_KEY` | Yes | Google Gemini fallback |
| `SAM_GOV_API_KEY` | Yes | SAM.gov access |

## Performance

Daily processing on Surface ARM (Snapdragon X Elite):
- Scrape 50-100 grants: ~5 min (GitHub Actions, cloud)
- Filter 50 grants: ~25s (Llama 3.2 3B, local)
- Analyze 12 qualified: ~36s (Llama 3.1 8B, local)
- Generate 3 drafts: ~90s (Gemma 2 9B, local)
- **Total local time: ~3 minutes**

## Company Profile

Core Element AI — Probabilistic AI modeling for geological mineral exploration:
- **Focus:** Li, Cu, Co, Al, Fe for green energy transition
- **Results:** 79% drilling reduction, $17M+ savings, ±15m accuracy
- **Team:** PhD Stanford/MIT, NASA/Berkeley, 30+ years mining
- **Partners:** ERG, Colorado School of Mines, Stanford Mineral-X, Lawrence Berkeley Lab
- **Markets:** Kazakhstan, USA, Mexico (expanding globally)
