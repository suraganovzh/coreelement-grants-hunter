"""
Horizon Europe Funding & Tenders API client.

Searches the EU Funding & Tenders portal for open calls,
focusing on CL4 (Climate, Energy, Mobility) topics
related to critical raw materials.
"""

import requests

from src.utils.logger import setup_logger

logger = setup_logger("horizon_europe_api")

FTOP_API = "https://ec.europa.eu/info/funding-tenders/opportunities/data/"
FTOP_SEARCH = "https://api.tech.ec.europa.eu/search-api/prod/rest/search"


def search_horizon_europe(topic_codes=None, status="open"):
    """Search Horizon Europe opportunities.

    Args:
        topic_codes: List of specific topic codes to search.
        status: Filter by status (open, closed, forthcoming).

    Returns:
        List of standardized grant dicts.
    """
    if not topic_codes:
        topic_codes = [
            "HORIZON-CL4-2026-RESILIENCE-01-MAT-PROD-11",
            "HORIZON-CL4-2026-RESILIENCE-01-MAT-PROD-12",
        ]

    grants = []
    for code in topic_codes:
        try:
            result = _fetch_topic(code)
            if result:
                grants.append(result)
        except Exception as e:
            logger.warning("Failed to fetch topic %s: %s", code, e)

    return grants


def _fetch_topic(topic_code):
    """Fetch details for a specific Horizon Europe topic."""
    try:
        params = {
            "apiKey": "SEDIA",
            "text": topic_code,
            "pageSize": 5,
        }
        response = requests.get(FTOP_SEARCH, params=params, timeout=30)

        if response.status_code == 200:
            data = response.json()
            results = data.get("results", [])
            if results:
                return _parse_topic(results[0], topic_code)
    except requests.RequestException as e:
        logger.debug("Horizon Europe API request failed for %s: %s", topic_code, e)

    return None


def _parse_topic(result, topic_code):
    """Parse a Horizon Europe topic result into a standardized grant dict."""
    metadata = result.get("metadata", {})

    return {
        "id": f"eu-{topic_code.lower().replace('-', '_')}",
        "title": metadata.get("title", [topic_code])[0] if isinstance(metadata.get("title"), list) else topic_code,
        "funder": "European Commission - Horizon Europe",
        "description": metadata.get("description", [""])[0] if isinstance(metadata.get("description"), list) else "",
        "amount_min": 5000000,
        "amount_max": 7000000,
        "currency": "EUR",
        "deadline": metadata.get("deadlineDates", [""])[0] if isinstance(metadata.get("deadlineDates"), list) else "",
        "url": f"https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/opportunities/topic-details/{topic_code.lower()}",
        "source": "horizon_europe_api",
        "grant_type": "eu",
        "industry_tags": ["critical raw materials", "exploration", "extraction", "EU", "Horizon Europe"],
        "eligibility": "EU-based consortia. Non-EU partners can participate. Partnership pathway: Core Element AI via EU consortium member.",
        "requirements": "",
        "focus_areas": ["critical raw materials", "sustainable extraction"],
    }
