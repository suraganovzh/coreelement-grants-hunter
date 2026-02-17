"""Abstract base class for all grant scrapers."""

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from src.utils.logger import setup_logger
from src.utils.rate_limiter import RateLimiter

logger = setup_logger("scraper")


@dataclass
class GrantResult:
    """Standardized grant result from any scraper."""

    title: str
    funder: str = ""
    description: str = ""
    amount_min: int | None = None
    amount_max: int | None = None
    currency: str = "USD"
    deadline: date | None = None
    url: str = ""
    source: str = ""
    grant_type: str = ""
    industry_tags: list[str] = field(default_factory=list)
    eligibility_text: str = ""
    requirements_text: str = ""
    evaluation_criteria: str = ""


class BaseScraper(ABC):
    """Abstract base class for grant scrapers.

    All scrapers must implement:
        - name: property returning the scraper name
        - search(): method that returns a list of GrantResult
    """

    def __init__(self, rate_limit_calls: int = 10, rate_limit_period: float = 60.0):
        self._limiter = RateLimiter(calls=rate_limit_calls, period=rate_limit_period)
        self._client = httpx.Client(
            timeout=30.0,
            follow_redirects=True,
            headers={
                "User-Agent": "GrantHunterAI/1.0 (Core Element AI; grant-discovery-bot)"
            },
        )

    @property
    @abstractmethod
    def name(self) -> str:
        """Name of the scraper source."""

    @abstractmethod
    def search(self, keywords: list[str] | None = None) -> list[GrantResult]:
        """Execute search and return list of found grants.

        Args:
            keywords: Optional keyword overrides; uses config defaults if None.
        """

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=4, max=30))
    def _fetch(self, url: str, params: dict | None = None, headers: dict | None = None) -> httpx.Response:
        """Fetch URL with rate limiting and retries.

        Args:
            url: URL to fetch.
            params: Optional query parameters.
            headers: Optional extra headers.

        Returns:
            httpx.Response object.
        """
        self._limiter.acquire()
        logger.debug("[%s] Fetching: %s", self.name, url)
        start = time.monotonic()

        response = self._client.get(url, params=params, headers=headers)
        response.raise_for_status()

        elapsed = time.monotonic() - start
        logger.debug("[%s] Response: %d in %.1fs", self.name, response.status_code, elapsed)
        return response

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=4, max=30))
    def _post(self, url: str, json: dict | None = None, data: dict | None = None, headers: dict | None = None) -> httpx.Response:
        """POST request with rate limiting and retries."""
        self._limiter.acquire()
        logger.debug("[%s] POST: %s", self.name, url)

        response = self._client.post(url, json=json, data=data, headers=headers)
        response.raise_for_status()
        return response

    def _parse_html(self, html_content: str):
        """Parse HTML with BeautifulSoup."""
        from bs4 import BeautifulSoup
        return BeautifulSoup(html_content, "lxml")

    def close(self):
        """Close HTTP client."""
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def __repr__(self):
        return f"<{self.__class__.__name__}(name='{self.name}')>"
