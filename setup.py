from setuptools import setup, find_packages

setup(
    name="grant-hunter-ai",
    version="1.0.0",
    description="AI-powered grant discovery and application management for Core Element AI",
    author="Core Element AI",
    packages=find_packages(),
    python_requires=">=3.11",
    install_requires=[
        "python-dotenv>=1.0.1",
        "PyYAML>=6.0.2",
        "groq>=0.15.0",
        "google-generativeai>=0.8.4",
        "python-telegram-bot>=21.9",
        "SQLAlchemy>=2.0.36",
        "alembic>=1.14.1",
        "APScheduler>=3.11.0",
        "beautifulsoup4>=4.12.3",
        "requests>=2.32.3",
        "httpx>=0.28.1",
        "tenacity>=9.0.0",
        "pandas>=2.2.3",
        "pydantic>=2.10.4",
    ],
)
