"""
Grants.gov API client.

Official API for US federal grants.
Docs: https://www.grants.gov/web/grants/s2s/grantor/schemas.html
"""

import requests

from src.utils.logger import setup_logger

logger = setup_logger("grants_gov_api")

GRANTS_GOV_API = "https://www.grants.gov/grantsws/rest/opportunities/search/"


def search_grants_gov(keywords, deadline_from=None, max_results=25):
    """Search grants.gov API for open opportunities.

    Args:
        keywords: Search terms.
        deadline_from: Filter by deadline date (YYYY-MM-DD).
        max_results: Maximum number of results.

    Returns:
        List of grant opportunity dicts.
    """
    params = {
        "keyword": keywords,
        "oppStatuses": "posted",
        "sortBy": "openDate|desc",
        "rows": max_results,
    }

    if deadline_from:
        params["closeDateFrom"] = deadline_from

    try:
        response = requests.get(GRANTS_GOV_API, params=params, timeout=30)
        if response.status_code == 200:
            data = response.json()
            return parse_grants_gov_response(data)
        else:
            logger.warning("Grants.gov API returned status %d", response.status_code)
    except requests.RequestException as e:
        logger.warning("Grants.gov API request failed: %s", e)

    return []


def parse_grants_gov_response(data):
    """Parse grants.gov API response into standardized grant dicts."""
    grants = []
    opportunities = data.get("oppHits", [])

    for opp in opportunities:
        grant = {
            "id": f"gov-{opp.get('id', '')}",
            "title": opp.get("title", ""),
            "funder": opp.get("agency", "Unknown Federal Agency"),
            "description": opp.get("description", ""),
            "amount_min": 0,
            "amount_max": _parse_amount(opp.get("awardCeiling", 0)),
            "currency": "USD",
            "deadline": opp.get("closeDate", ""),
            "url": f"https://www.grants.gov/search-results-detail/{opp.get('id', '')}",
            "source": "grants_gov_api",
            "grant_type": "federal",
            "industry_tags": _extract_tags(opp),
            "eligibility": opp.get("eligibilities", ""),
            "requirements": "",
            "focus_areas": [],
        }
        grants.append(grant)

    logger.info("Parsed %d grants from grants.gov API", len(grants))
    return grants


def _parse_amount(value):
    """Parse amount from various formats."""
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value.replace(",", "").replace("$", ""))
        except ValueError:
            return 0
    return 0


def _extract_tags(opportunity):
    """Extract relevant tags from a grants.gov opportunity."""
    tags = []
    category = opportunity.get("category", "")
    if category:
        tags.append(category)

    cfda = opportunity.get("cfdaNumber", "")
    if cfda:
        tags.append(f"CFDA: {cfda}")

    return tags
