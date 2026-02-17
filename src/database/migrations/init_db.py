"""Initialize the database schema."""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from src.database.models import init_db, get_engine
from src.utils.logger import setup_logger

logger = setup_logger("db_init")


def main():
    """Create all database tables."""
    db_url = os.getenv("DATABASE_URL", "sqlite:///data/grants_hunter.db")

    # Ensure data directory exists for SQLite
    if db_url.startswith("sqlite"):
        db_path = db_url.replace("sqlite:///", "")
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    logger.info("Initializing database: %s", db_url)
    engine = init_db(db_url)
    logger.info("Database initialized successfully. Tables created.")

    # List tables
    from sqlalchemy import inspect
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    logger.info("Tables: %s", ", ".join(tables))

    print(f"Database initialized at: {db_url}")
    print(f"Tables created: {', '.join(tables)}")


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    main()
