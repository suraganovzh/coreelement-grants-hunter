# Grant Hunter AI

AI-powered grant discovery and application management system for **Core Element AI** — a company developing probabilistic AI modeling for geological mineral exploration.

## Overview

Grant Hunter AI automatically:
- **Searches** 30+ grant sources daily (federal, private, international)
- **Analyzes** eligibility requirements against Core Element AI's profile
- **Scores** grants by fit (0-100%) and application complexity (1-10)
- **Notifies** via Telegram bot with daily digests and deadline reminders
- **Generates** application drafts (executive summary, technical approach, budget, impact)
- **Tracks** applications through the full lifecycle

## Architecture

```
src/
├── scrapers/          # Grant source scrapers (7 sources)
│   ├── grants_gov.py  # US Federal grants (Grants.gov API)
│   ├── sbir_scraper.py # SBIR/STTR programs
│   ├── foundation_scraper.py # Private foundations (Google, Microsoft, etc.)
│   ├── eu_horizon.py  # EU Horizon Europe + EIT RawMaterials
│   ├── world_bank.py  # World Bank, IFC, GCF, GEF, ADB, EBRD
│   ├── corporate_grants.py # Mining industry + corporate grants
│   └── kazakhstan_scraper.py # Kazakhstan-specific sources
├── analyzers/         # Grant analysis pipeline
│   ├── eligibility_checker.py # Rule-based + AI eligibility check
│   ├── fit_scorer.py  # Weighted fit scoring (0-100%)
│   ├── complexity_scorer.py # Application complexity (1-10)
│   ├── requirements_parser.py # Extract structured requirements
│   └── similar_finder.py # Find similar grants
├── generators/        # AI-powered content generation
│   ├── executive_summary.py # Gemini-powered summary generation
│   ├── technical_approach.py # Technical approach section
│   ├── budget_justification.py # Budget justification
│   └── impact_statement.py # Impact statement
├── bot/               # Telegram bot
│   ├── telegram_bot.py # Bot initialization
│   ├── handlers.py    # Command handlers
│   ├── keyboards.py   # Inline keyboards
│   ├── notifications.py # Daily digest & reminders
│   └── conversation.py # Multi-step conversations
├── database/          # SQLAlchemy models + queries
└── utils/             # API clients, rate limiting, text processing
```

## Quick Start

### 1. Clone and Setup

```bash
git clone <repo-url>
cd grant-hunter-ai
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with your API keys:
# - GROQ_API_KEY (from console.groq.com)
# - GEMINI_API_KEY (from makersuite.google.com)
# - TELEGRAM_BOT_TOKEN (from @BotFather)
# - TELEGRAM_CHAT_ID (your chat ID)
```

### 3. Initialize Database

```bash
python -m src.database.migrations.init_db
# Optional: load sample data
python -m src.database.seed_data
```

### 4. Run

```bash
# Full pipeline: scrape -> analyze -> notify
python -m src.main --mode=full

# Individual modes:
python -m src.main --mode=scrape    # Run scrapers only
python -m src.main --mode=analyze   # Analyze found grants
python -m src.main --mode=notify    # Send Telegram notifications
python -m src.main --mode=bot       # Start Telegram bot (polling)
```

### 5. Run Tests

```bash
pytest tests/ -v
```

## Docker Deployment

```bash
# Production deployment with PostgreSQL
docker-compose up -d

# Services:
# - bot:       Telegram bot (always running)
# - scheduler: Daily search cron job
# - db:        PostgreSQL database
# - backup:    Daily database backups
```

## Telegram Bot Commands

| Command | Description |
|---------|-------------|
| `/start` | Welcome message |
| `/status` | Current pipeline overview |
| `/urgent` | Grants with <7 day deadlines |
| `/pipeline` | Full pipeline by urgency |
| `/search <keyword>` | Search grants by keyword |
| `/details <id>` | Full grant details |
| `/fit <id>` | Detailed fit analysis |
| `/similar <id>` | Find similar grants |
| `/draft <id>` | Generate application draft |
| `/stats` | Overall statistics |
| `/settings` | Notification settings |

## Grant Sources

**US Federal:** Grants.gov, SBIR/STTR, NSF, DOE, ARPA-E, USGS

**Private Foundations:** Google AI, Microsoft, Amazon, Intel, BHP, Rio Tinto, Anglo American

**International:** EU Horizon Europe, EIT RawMaterials, World Bank, IFC, ADB, EBRD, Green Climate Fund

**Green Tech:** Breakthrough Energy, Global Environment Facility, ARPA-E

**Kazakhstan:** Astana Hub, QazInnovations/NATD, Ministry of Digital Development

## Configuration

All configuration is in `config/`:

- `sources.yaml` — Grant sources, URLs, API endpoints, rate limits
- `keywords.yaml` — Search keywords by category
- `filters.yaml` — Filtering criteria, scoring weights, notification settings
- `core_element_profile.yaml` — Company profile for matching and generation

## AI Integration

**Groq (LPU)** — Fast analysis tasks:
- Eligibility checking
- Grant classification
- Quick scoring
- Requirement extraction

**Gemini Pro** — Long-form generation:
- Executive summary writing
- Technical approach generation
- Budget justification
- Impact statement creation
- Deep grant analysis

## Pipeline Flow

```
New Grant Found
    → Groq: Quick eligibility check & scoring
    → If fit > 70%:
        → Gemini: Deep analysis & requirements extraction
        → Gemini: Draft outline generation
    → Store in DB
    → Send Telegram notification (if notable)
```

## GitHub Actions

| Workflow | Schedule | Description |
|----------|----------|-------------|
| `daily_search.yml` | 9:00 AM UTC daily | Full pipeline |
| `deadline_reminders.yml` | 3x daily | Deadline alerts |
| `deploy.yml` | On push to main | Deploy to VPS |

## Required Secrets

Set these in GitHub repository settings or `.env`:

| Secret | Description |
|--------|-------------|
| `GROQ_API_KEY` | Groq API key |
| `GEMINI_API_KEY` | Google Gemini API key |
| `TELEGRAM_BOT_TOKEN` | Telegram bot token from @BotFather |
| `TELEGRAM_CHAT_ID` | Target Telegram chat ID |
| `DATABASE_URL` | PostgreSQL connection string |
| `VPS_HOST` | VPS IP address (for deployment) |
| `VPS_USER` | VPS SSH username |
| `VPS_SSH_KEY` | VPS SSH private key |

## Company Profile

Core Element AI specializes in probabilistic AI modeling for geological mineral exploration:
- **Focus minerals:** Lithium, Copper, Cobalt, Aluminum, Iron Ore
- **Key metric:** 79% reduction in unsuccessful drilling, $17M+ proven savings
- **Markets:** Kazakhstan, USA, Mexico (expanding globally)
- **Technology:** TRL 7, ±15m prediction accuracy
