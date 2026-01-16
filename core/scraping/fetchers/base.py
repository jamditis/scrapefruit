"""Abstract base classes for fetchers.

This module defines the interfaces that all fetchers must implement,
enabling polymorphism, better type safety, and easier testing.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Dict, Any


@dataclass
class BaseFetchResult:
    """
    Base result from any fetch operation.

    All fetcher-specific result classes should include these fields
    to ensure consistent handling in the scraping engine.
    """

    success: bool
    html: str = ""
    status_code: int = 0
    method: str = ""
    error: Optional[str] = None
    response_time_ms: int = 0
    screenshot: Optional[bytes] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary for serialization."""
        return {
            "success": self.success,
            "html": self.html,
            "status_code": self.status_code,
            "method": self.method,
            "error": self.error,
            "response_time_ms": self.response_time_ms,
            "has_screenshot": self.screenshot is not None,
        }


class BaseFetcher(ABC):
    """
    Abstract base class for all fetchers.

    Fetchers are responsible for retrieving web page content using
    various methods (HTTP requests, browser automation, AI agents, etc.).

    All fetchers must implement:
    - fetch(): Main method to retrieve page content
    - is_available(): Check if fetcher dependencies are available

    The fetch() method should:
    - Accept a URL and optional configuration
    - Return a result object with success status and content
    - Handle errors gracefully (return error in result, don't raise)
    - Track response time for performance monitoring
    """

    # Subclasses should override this with their method name
    METHOD_NAME: str = "base"

    @abstractmethod
    def fetch(
        self,
        url: str,
        timeout: int = 30000,
        retry_count: int = 0,
        **kwargs,
    ) -> BaseFetchResult:
        """
        Fetch content from a URL.

        Args:
            url: The URL to fetch
            timeout: Request timeout in milliseconds
            retry_count: Number of retry attempts on failure
            **kwargs: Fetcher-specific options

        Returns:
            BaseFetchResult (or subclass) with success status and content
        """
        pass

    @classmethod
    def is_available(cls) -> bool:
        """
        Check if this fetcher is available (dependencies installed, configured).

        Returns:
            True if fetcher can be used, False otherwise

        Override this method to check for:
        - Required packages (e.g., playwright, pyppeteer)
        - External services (e.g., Ollama running)
        - API keys (e.g., OPENAI_API_KEY set)
        """
        return True

    def cleanup(self) -> None:
        """
        Clean up resources (browser instances, connections, etc.).

        Called during application shutdown or when fetcher is no longer needed.
        Override in subclasses that manage persistent resources.
        """
        pass


class BrowserFetcher(BaseFetcher):
    """
    Base class for browser-based fetchers (Playwright, Puppeteer).

    Adds browser-specific functionality:
    - Screenshot capture
    - Wait for selector/network idle
    - JavaScript execution context
    """

    @abstractmethod
    async def fetch_async(
        self,
        url: str,
        timeout: int = 30000,
        wait_for: Optional[str] = None,
        wait_for_timeout: int = 5000,
        take_screenshot: bool = False,
    ) -> BaseFetchResult:
        """
        Async version of fetch for browser automation.

        Args:
            url: The URL to fetch
            timeout: Navigation timeout in milliseconds
            wait_for: CSS selector to wait for before capturing content
            wait_for_timeout: Timeout for wait_for selector
            take_screenshot: Whether to capture a full-page screenshot

        Returns:
            BaseFetchResult with HTML content and optional screenshot
        """
        pass
