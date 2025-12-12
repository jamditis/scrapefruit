"""Fetcher modules for retrieving web pages."""

from core.scraping.fetchers.http_fetcher import HTTPFetcher
from core.scraping.fetchers.playwright_fetcher import PlaywrightFetcher

__all__ = ["HTTPFetcher", "PlaywrightFetcher"]
