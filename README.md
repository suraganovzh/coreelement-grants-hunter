# Grant Hunter AI

Success-driven grant discovery system for **Core Element AI** — $0/month hybrid architecture using GitHub Actions (cloud scraping) + local ARM models (AI analysis).

## Core Principle

We don't just find grants — we **win** them. The system learns from awarded grants to predict which new opportunities have the highest win probability, then generates tailored applications.

**Metric that matters: $ won, not # applied.**

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
│    - Telegram push notifications        │
└─────────────────────────────────────────┘
```

## Cost Breakdown

| Component | Cost |
|-----------|------|
| GitHub Actions | $0 (2,000 min/month free) |
| GitHub Repo | $0 (free private repo) |
| Ollama Models | $0 (local) |
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
git clone <repo-url>
cd grant-hunter-ai
pip install -r requirements.txt
```

### 3. Configure Telegram

```bash
cp .env.example .env
# Edit .env with Telegram credentials

# Setup:
# 1. Telegram → @BotFather → /newbot → "Core Element Grant Hunter"
# 2. Copy bot token to .env
# 3. Send /start to your bot
# 4. Get chat_id: https://api.telegram.org/bot<TOKEN>/getUpdates
# 5. Copy chat.id to .env
```

### 4. Enable GitHub Actions

1. Go to repo Settings → Actions → Enable workflows
2. Optionally add secrets: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`
3. Manually trigger: Actions → Daily Grant Scraping → Run workflow

### 5. Daily Usage (Surface)

```bash
# Pull latest scraped data, filter, analyze, notify
python -m src.local.daily_workflow

# Generate drafts for a specific grant
python -m src.local.generate --grant-id <id>

# View high-priority grants
cat data/analyzed.json | python -c "
import json,sys
for g in json.load(sys.stdin):
  if g.get('analysis',{}).get('priority')=='copy_now':
    print(f\"  {g['title'][:60]} | Win: {g['analysis']['win_probability']}%\")
"
```

## Local AI Models

| Model | Task | Speed | Use |
|-------|------|-------|-----|
| **Llama 3.2 3B** | Eligibility filter | ~0.5s/grant | Quick pass/fail check |
| **Llama 3.1 8B** | Deep analysis | ~3s/grant | Pattern match, win prediction |
| **Gemma 2 9B** | Draft generation | ~30s/section | Executive summary, tech approach |

All models run via Ollama on Snapdragon X Elite (ARM). With graceful fallback to rule-based analysis if Ollama is unavailable.

## Pipeline Flow

```
GitHub Actions (daily):
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

## Project Structure

```
grant-hunter-ai/
├── .github/workflows/        # GitHub Actions (cloud scraping)
│   ├── daily_search.yml      # Daily scrape + weekly winners
│   └── deadline_reminders.yml # Telegram deadline alerts
├── src/
│   ├── scrapers/             # Grant source scrapers (7 sources)
│   │   ├── grants_gov.py     # US Federal grants
│   │   ├── sbir_scraper.py   # SBIR/STTR
│   │   ├── eu_horizon.py     # EU Horizon Europe
│   │   ├── foundation_scraper.py
│   │   ├── corporate_grants.py
│   │   ├── world_bank.py
│   │   ├── kazakhstan_scraper.py
│   │   └── winners/          # Awarded grant scrapers
│   │       ├── grants_gov_awards.py
│   │       └── sbir_awards.py
│   ├── analyzers/            # Analysis pipeline
│   │   ├── pattern_extractor.py  # Learn from winners
│   │   ├── eligibility_checker.py
│   │   ├── fit_scorer.py
│   │   ├── complexity_scorer.py
│   │   └── similar_finder.py
│   ├── local/                # ARM processing (Surface)
│   │   ├── daily_workflow.py # Main daily pipeline
│   │   ├── filter.py        # Llama 3.2 3B filter
│   │   ├── analyze.py       # Llama 3.1 8B analysis
│   │   ├── generate.py      # Gemma 2 9B drafts
│   │   └── telegram_notify.py
│   ├── generators/           # Content generation
│   ├── bot/                  # Telegram bot (full version)
│   ├── database/             # SQLAlchemy models
│   └── utils/                # Shared utilities
├── config/                   # YAML configuration
├── templates/                # Grant application templates
├── data/                     # Git-tracked scraped data
├── drafts/                   # Generated application drafts
└── tests/                    # Test suite
```

## Grant Sources

**US Federal:** Grants.gov, SBIR/STTR, NSF, DOE, ARPA-E, USGS

**Private:** Google AI, Microsoft, Amazon, BHP, Rio Tinto, Anglo American, Breakthrough Energy

**International:** EU Horizon Europe, EIT RawMaterials, World Bank, IFC, ADB, EBRD, Green Climate Fund

**Kazakhstan:** Astana Hub, QazInnovations/NATD, Ministry of Digital Development

## Success-Driven Features

**Winner Analysis** — Weekly scraping of awarded grants from grants.gov and sbir.gov to build a database of winning patterns.

**Pattern Extraction** — Identifies top keywords, funder preferences, typical amounts, and repeat winners to predict success probability.

**Priority Classification:**
- `copy_now` — Win probability >15%, pattern match >80%, apply immediately
- `test_first` — Win probability 8-15%, worth investigating
- `skip` — Win probability <8%, don't waste time

## GitHub Actions

| Workflow | Schedule | Description |
|----------|----------|-------------|
| `daily_search.yml` | 9 AM UTC daily | Scrape new grants |
| `daily_search.yml` | 10 AM UTC Sunday | Scrape winners + extract patterns |
| `deadline_reminders.yml` | 9 AM UTC daily | Telegram deadline alerts |

## Secrets (Optional)

Only needed for Telegram notifications from GitHub Actions:

| Secret | Description |
|--------|-------------|
| `TELEGRAM_BOT_TOKEN` | Telegram bot token |
| `TELEGRAM_CHAT_ID` | Target chat ID |

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
- **Markets:** Kazakhstan, USA, Mexico (expanding globally)
