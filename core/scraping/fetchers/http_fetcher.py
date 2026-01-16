"""HTTP fetcher using requests library with user-agent rotation."""

import random
import time
from typing import Optional, Dict, Any
from dataclasses import dataclass

import requests
from requests.exceptions import RequestException

import config


@dataclass
class FetchResult:
    """Result from a fetch operation."""

    success: bool
    html: str = ""
    status_code: int = 0
    method: str = "http"
    error: Optional[str] = None
    response_time_ms: int = 0


@dataclass
class HeadResult:
    """Result from a HEAD request operation."""

    success: bool
    status_code: int = 0
    content_type: str = ""
    content_length: Optional[int] = None
    error: Optional[str] = None


class HTTPFetcher:
    """Simple HTTP fetcher with user-agent rotation and retry logic."""

    def __init__(self):
        self.user_agents = config.USER_AGENTS
        self.session = requests.Session()

    def get_random_user_agent(self) -> str:
        """Get a random user agent."""
        return random.choice(self.user_agents)

    def get_headers(self, custom_headers: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        """Build request headers."""
        headers = {
            "User-Agent": self.get_random_user_agent(),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Cache-Control": "max-age=0",
        }

        if custom_headers:
            headers.update(custom_headers)

        return headers

    def fetch(
        self,
        url: str,
        timeout: int = 30,
        retry_count: int = 3,
        custom_headers: Optional[Dict[str, str]] = None,
    ) -> FetchResult:
        """
        Fetch a URL using HTTP request.

        Args:
            url: The URL to fetch
            timeout: Request timeout in seconds
            retry_count: Number of retries on failure
            custom_headers: Additional headers to include

        Returns:
            FetchResult with success status and content
        """
        last_error = None

        for attempt in range(retry_count):
            start_time = time.time()

            try:
                response = self.session.get(
                    url,
                    headers=self.get_headers(custom_headers),
                    timeout=timeout,
                    allow_redirects=True,
                )

                response_time = int((time.time() - start_time) * 1000)

                # Check for success
                if response.status_code == 200:
                    return FetchResult(
                        success=True,
                        html=response.text,
                        status_code=response.status_code,
                        method="http",
                        response_time_ms=response_time,
                    )

                # Non-200 status codes
                if response.status_code in (403, 429):
                    # Rate limited or blocked - might need Playwright
                    return FetchResult(
                        success=False,
                        status_code=response.status_code,
                        method="http",
                        error=f"HTTP {response.status_code}: Access denied or rate limited",
                        response_time_ms=response_time,
                    )

                if response.status_code >= 400:
                    last_error = f"HTTP {response.status_code}"
                    continue

            except RequestException as e:
                last_error = str(e)
                response_time = int((time.time() - start_time) * 1000)

                # Wait before retry
                if attempt < retry_count - 1:
                    time.sleep(1 * (attempt + 1))
                continue

        return FetchResult(
            success=False,
            method="http",
            error=last_error or "Unknown error",
            response_time_ms=response_time if "response_time" in locals() else 0,
        )

    def head(self, url: str, timeout: int = 10) -> HeadResult:
        """
        Perform HEAD request to check URL status.

        Args:
            url: The URL to check
            timeout: Request timeout in seconds

        Returns:
            HeadResult with status, content type, and length
        """
        try:
            response = self.session.head(
                url,
                headers=self.get_headers(),
                timeout=timeout,
                allow_redirects=True,
            )
            content_length = response.headers.get("Content-Length")
            return HeadResult(
                success=response.status_code == 200,
                status_code=response.status_code,
                content_type=response.headers.get("Content-Type", ""),
                content_length=int(content_length) if content_length else None,
            )
        except RequestException as e:
            return HeadResult(
                success=False,
                status_code=0,
                error=str(e),
            )
