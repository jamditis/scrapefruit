"""Fetcher modules for retrieving web pages."""

from core.scraping.fetchers.http_fetcher import HTTPFetcher, FetchResult
from core.scraping.fetchers.playwright_fetcher import PlaywrightFetcher, PlaywrightResult
from core.scraping.fetchers.puppeteer_fetcher import PuppeteerFetcher, PuppeteerResult
from core.scraping.fetchers.agent_browser_fetcher import AgentBrowserFetcher, AgentBrowserResult

__all__ = [
    "HTTPFetcher",
    "FetchResult",
    "PlaywrightFetcher",
    "PlaywrightResult",
    "PuppeteerFetcher",
    "PuppeteerResult",
    "AgentBrowserFetcher",
    "AgentBrowserResult",
]
