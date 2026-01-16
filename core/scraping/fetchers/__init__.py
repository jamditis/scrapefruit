"""Fetcher modules for retrieving web pages and media."""

from core.scraping.fetchers.base import BaseFetcher, BrowserFetcher, BaseFetchResult
from core.scraping.fetchers.http_fetcher import HTTPFetcher, FetchResult, HeadResult
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

# Video fetcher - requires yt-dlp and whisper
try:
    from core.scraping.fetchers.video_fetcher import (
        VideoFetcher,
        VideoFetchResult,
        VideoMetadata,
        TranscriptSegment,
        get_video_fetcher,
    )
    HAS_VIDEO_FETCHER = True
except ImportError:
    VideoFetcher = None
    VideoFetchResult = None
    VideoMetadata = None
    TranscriptSegment = None
    get_video_fetcher = None
    HAS_VIDEO_FETCHER = False

__all__ = [
    # Base classes
    "BaseFetcher",
    "BrowserFetcher",
    "BaseFetchResult",
    # Basic fetchers (free tier)
    "HTTPFetcher",
    "FetchResult",
    "HeadResult",
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
    # Video/media fetcher
    "VideoFetcher",
    "VideoFetchResult",
    "VideoMetadata",
    "TranscriptSegment",
    "get_video_fetcher",
    "HAS_VIDEO_FETCHER",
]
