"""Seed database with sample data for testing."""

import sys
from pathlib import Path
from datetime import date, timedelta

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.database.models import init_db, get_session, Grant
from src.utils.logger import setup_logger

logger = setup_logger("seed_data")

SAMPLE_GRANTS = [
    {
        "title": "SBIR Phase I - Critical Minerals AI Exploration Technology",
        "funder": "Department of Energy (DOE)",
        "description": "The DOE seeks innovative AI-based approaches to accelerate critical minerals exploration. Focus on lithium, cobalt, and rare earth elements.",
        "amount_min": 200000,
        "amount_max": 256000,
        "currency": "USD",
        "deadline": date.today() + timedelta(days=21),
        "url": "https://www.sbir.gov/node/example-doe-critical-minerals",
        "source": "sbir",
        "grant_type": "federal",
        "industry_tags": ["mining", "AI", "critical minerals", "cleantech"],
        "status": "qualified",
        "fit_score": 95,
        "complexity_score": 4,
        "estimated_prep_hours": 15,
    },
    {
        "title": "NSF SBIR Phase II - AI for Geological Exploration",
        "funder": "National Science Foundation",
        "description": "Continuation funding for AI/ML applications in geological sciences, subsurface prediction, and mineral deposit identification.",
        "amount_min": 750000,
        "amount_max": 1000000,
        "currency": "USD",
        "deadline": date.today() + timedelta(days=60),
        "url": "https://www.nsf.gov/funding/example-geo-ai",
        "source": "nsf",
        "grant_type": "federal",
        "industry_tags": ["AI", "geology", "geosciences"],
        "status": "found",
        "fit_score": 92,
        "complexity_score": 7,
        "estimated_prep_hours": 30,
    },
    {
        "title": "EU Horizon Europe - AI for Raw Materials Exploration",
        "funder": "European Commission",
        "description": "Funding for innovative technologies for critical raw materials exploration, including AI-driven geological prediction and sustainable mining methods.",
        "amount_min": 1000000,
        "amount_max": 2000000,
        "currency": "EUR",
        "deadline": date.today() + timedelta(days=45),
        "url": "https://ec.europa.eu/funding-tenders/example-raw-materials",
        "source": "eu_horizon",
        "grant_type": "international",
        "industry_tags": ["AI", "mining", "raw materials", "cleantech"],
        "status": "qualified",
        "fit_score": 87,
        "complexity_score": 8,
        "estimated_prep_hours": 40,
    },
    {
        "title": "ARPA-E Mining Innovation Challenge",
        "funder": "Advanced Research Projects Agency-Energy",
        "description": "Revolutionary technologies that dramatically improve the efficiency and reduce the environmental impact of mining critical minerals for clean energy technologies.",
        "amount_min": 500000,
        "amount_max": 3000000,
        "currency": "USD",
        "deadline": date.today() + timedelta(days=5),
        "url": "https://arpa-e.energy.gov/example-mining-innovation",
        "source": "arpa_e",
        "grant_type": "federal",
        "industry_tags": ["mining", "clean energy", "innovation", "AI"],
        "status": "qualified",
        "fit_score": 91,
        "complexity_score": 6,
        "estimated_prep_hours": 25,
    },
    {
        "title": "Breakthrough Energy Fellows - Mining Tech Innovation",
        "funder": "Breakthrough Energy",
        "description": "Fellowship program for scientists and engineers developing technologies to reduce greenhouse gas emissions. Includes critical minerals supply chain innovations.",
        "amount_min": 250000,
        "amount_max": 500000,
        "currency": "USD",
        "deadline": date.today() + timedelta(days=90),
        "url": "https://www.breakthroughenergy.org/fellows-example",
        "source": "breakthrough_energy",
        "grant_type": "private",
        "industry_tags": ["cleantech", "mining", "climate", "innovation"],
        "status": "found",
        "fit_score": 78,
        "complexity_score": 5,
        "estimated_prep_hours": 20,
    },
]


def seed():
    """Insert sample grants into the database."""
    init_db()
    session = get_session()

    for grant_data in SAMPLE_GRANTS:
        existing = session.query(Grant).filter(Grant.url == grant_data["url"]).first()
        if not existing:
            grant = Grant(**grant_data)
            session.add(grant)
            logger.info("Seeded: %s", grant_data["title"][:60])
        else:
            logger.info("Skipped (exists): %s", grant_data["title"][:60])

    session.commit()
    session.close()
    logger.info("Seed data complete. %d sample grants loaded.", len(SAMPLE_GRANTS))
    print(f"Seeded {len(SAMPLE_GRANTS)} sample grants.")


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    seed()
