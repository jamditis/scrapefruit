"""Fetcher modules for retrieving web pages."""

from core.scraping.fetchers.http_fetcher import HTTPFetcher, FetchResult
from core.scraping.fetchers.playwright_fetcher import PlaywrightFetcher, PlaywrightResult
from core.scraping.fetchers.agent_browser_fetcher import AgentBrowserFetcher, AgentBrowserResult
from core.scraping.fetchers.browser_use_fetcher import (
    BrowserUseFetcher,
    BrowserUseResult,
    get_browser_use_fetcher,
)

# Optional imports - may not be available
try:
    from core.scraping.fetchers.puppeteer_fetcher import PuppeteerFetcher, PuppeteerResult
    HAS_PUPPETEER = True
except ImportError:
    PuppeteerFetcher = None
    PuppeteerResult = None
    HAS_PUPPETEER = False

__all__ = [
    # Basic fetchers (free tier)
    "HTTPFetcher",
    "FetchResult",
    "PlaywrightFetcher",
    "PlaywrightResult",
    "PuppeteerFetcher",
    "PuppeteerResult",
    "HAS_PUPPETEER",
    # Advanced fetchers (premium tier - AI-driven)
    "AgentBrowserFetcher",
    "AgentBrowserResult",
    "BrowserUseFetcher",
    "BrowserUseResult",
    "get_browser_use_fetcher",
]
