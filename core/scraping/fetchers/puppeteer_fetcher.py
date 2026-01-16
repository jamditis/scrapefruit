"""Puppeteer fetcher using pyppeteer for alternative browser automation."""

import asyncio
import random
import threading
import time
from typing import Optional, Dict, Any, TYPE_CHECKING
from dataclasses import dataclass

# Lazy import pyppeteer - not all systems have it
try:
    from pyppeteer import launch
    HAS_PYPPETEER = True
except ImportError:
    HAS_PYPPETEER = False
    launch = None

if TYPE_CHECKING:
    from pyppeteer.browser import Browser
    from pyppeteer.page import Page

import config

# Thread-local storage for event loop reuse
_thread_local = threading.local()


@dataclass
class PuppeteerResult:
    """Result from a Puppeteer fetch operation."""

    success: bool
    html: str = ""
    status_code: int = 0
    method: str = "puppeteer"
    error: Optional[str] = None
    response_time_ms: int = 0
    screenshot: Optional[bytes] = None


class PuppeteerFetcher:
    """
    Puppeteer-based fetcher using pyppeteer.

    Provides an alternative browser fingerprint to Playwright,
    useful when sites specifically detect/block Playwright.
    """

    def __init__(self):
        if not HAS_PYPPETEER:
            raise ImportError("pyppeteer is required. Install with: pip install pyppeteer")
        self.browser: Optional["Browser"] = None
        self._lock = asyncio.Lock()

    async def _ensure_browser(self):
        """Ensure browser is initialized."""
        if self.browser is None:
            self.browser = await launch(
                headless=True,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--disable-features=IsolateOrigins,site-per-process",
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-accelerated-2d-canvas",
                    "--disable-gpu",
                    "--window-size=1920,1080",
                ],
                ignoreHTTPSErrors=True,
            )

    async def _apply_stealth(self, page: "Page"):
        """Apply stealth techniques to bypass bot detection."""
        # Override webdriver property
        await page.evaluateOnNewDocument(
            """() => {
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
            }"""
        )

        # Override plugins
        await page.evaluateOnNewDocument(
            """() => {
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [
                        {name: 'Chrome PDF Plugin'},
                        {name: 'Chrome PDF Viewer'},
                        {name: 'Native Client'}
                    ]
                });
            }"""
        )

        # Override languages
        await page.evaluateOnNewDocument(
            """() => {
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['en-US', 'en']
                });
            }"""
        )

        # Override permissions query
        await page.evaluateOnNewDocument(
            """() => {
                const originalQuery = window.navigator.permissions.query;
                window.navigator.permissions.query = (parameters) => (
                    parameters.name === 'notifications' ?
                        Promise.resolve({ state: Notification.permission }) :
                        originalQuery(parameters)
                );
            }"""
        )

        # Override chrome runtime
        await page.evaluateOnNewDocument(
            """() => {
                window.chrome = {
                    runtime: {}
                };
            }"""
        )

    async def fetch_async(
        self,
        url: str,
        timeout: int = 30000,
        wait_for: Optional[str] = None,
        wait_for_timeout: int = 5000,
        take_screenshot: bool = False,
    ) -> PuppeteerResult:
        """
        Fetch a URL using Puppeteer with stealth mode.

        Args:
            url: The URL to fetch
            timeout: Navigation timeout in milliseconds
            wait_for: Optional CSS selector to wait for
            wait_for_timeout: Timeout for wait_for selector
            take_screenshot: Whether to capture a screenshot

        Returns:
            PuppeteerResult with success status and content
        """
        async with self._lock:
            start_time = time.time()
            page = None

            try:
                await self._ensure_browser()

                page = await self.browser.newPage()

                # Set random user agent
                user_agent = random.choice(config.USER_AGENTS)
                await page.setUserAgent(user_agent)

                # Set viewport
                await page.setViewport({"width": 1920, "height": 1080})

                # Apply stealth techniques
                await self._apply_stealth(page)

                # Set extra headers
                await page.setExtraHTTPHeaders({
                    "Accept-Language": "en-US,en;q=0.9",
                    "Accept-Encoding": "gzip, deflate, br",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                })

                # Navigate with timeout
                response = await page.goto(
                    url,
                    options={
                        "timeout": timeout,
                        "waitUntil": ["networkidle0", "domcontentloaded"],
                    },
                )

                # Wait for specific element if requested
                if wait_for:
                    try:
                        await page.waitForSelector(
                            wait_for,
                            options={"timeout": wait_for_timeout}
                        )
                    except Exception:
                        pass  # Continue even if element not found

                # Small delay to let JS execute
                await asyncio.sleep(0.5)

                # Get content
                html = await page.content()
                status_code = response.status if response else 0

                response_time = int((time.time() - start_time) * 1000)

                # Screenshot if requested
                screenshot = None
                if take_screenshot:
                    screenshot = await page.screenshot(options={"fullPage": True})

                return PuppeteerResult(
                    success=status_code == 200,
                    html=html,
                    status_code=status_code,
                    method="puppeteer",
                    response_time_ms=response_time,
                    screenshot=screenshot,
                )

            except Exception as e:
                response_time = int((time.time() - start_time) * 1000)
                return PuppeteerResult(
                    success=False,
                    method="puppeteer",
                    error=str(e),
                    response_time_ms=response_time,
                )
            finally:
                if page:
                    await page.close()

    def _get_or_create_loop(self) -> asyncio.AbstractEventLoop:
        """Get or create a thread-local event loop for reuse."""
        if not hasattr(_thread_local, 'loop') or _thread_local.loop.is_closed():
            _thread_local.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(_thread_local.loop)
        return _thread_local.loop

    def fetch(
        self,
        url: str,
        timeout: int = 30000,
        wait_for: Optional[str] = None,
        wait_for_timeout: int = 5000,
        take_screenshot: bool = False,
        retry_count: int = 0,
    ) -> PuppeteerResult:
        """
        Synchronous wrapper for fetch_async.

        Reuses thread-local event loop to prevent memory leaks.

        Args:
            url: The URL to fetch
            timeout: Navigation timeout in milliseconds
            wait_for: Optional CSS selector to wait for
            wait_for_timeout: Timeout for wait_for selector
            take_screenshot: Whether to capture a screenshot
            retry_count: Number of retry attempts on failure

        Returns:
            PuppeteerResult with success status and content
        """
        last_error = None

        for attempt in range(retry_count + 1):
            try:
                # Check if there's already a running loop
                try:
                    loop = asyncio.get_running_loop()
                    # If there's a running loop, we need to run in a new thread
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(
                            self._run_in_reusable_loop, url, timeout, wait_for, wait_for_timeout, take_screenshot
                        )
                        result = future.result(timeout=timeout // 1000 + 30)
                        if result.success or attempt >= retry_count:
                            return result
                        last_error = result.error
                        # Exponential backoff before retry
                        time.sleep((2 ** attempt) * 0.5)
                        continue
                except RuntimeError:
                    # No running loop
                    pass

                # Reuse thread-local event loop
                loop = self._get_or_create_loop()

                result = loop.run_until_complete(
                    self.fetch_async(
                        url,
                        timeout=timeout,
                        wait_for=wait_for,
                        wait_for_timeout=wait_for_timeout,
                        take_screenshot=take_screenshot,
                    )
                )

                if result.success or attempt >= retry_count:
                    return result

                last_error = result.error
                # Exponential backoff before retry
                time.sleep((2 ** attempt) * 0.5)

            except Exception as e:
                last_error = str(e)
                if attempt >= retry_count:
                    break
                # Exponential backoff before retry
                time.sleep((2 ** attempt) * 0.5)

        return PuppeteerResult(
            success=False,
            method="puppeteer",
            error=last_error,
        )

    def _run_in_reusable_loop(
        self,
        url: str,
        timeout: int,
        wait_for: Optional[str],
        wait_for_timeout: int,
        take_screenshot: bool,
    ) -> PuppeteerResult:
        """Run fetch using thread-local reusable event loop."""
        loop = self._get_or_create_loop()
        return loop.run_until_complete(
            self.fetch_async(url, timeout, wait_for, wait_for_timeout, take_screenshot)
        )

    async def close(self):
        """Close the browser."""
        if self.browser:
            await self.browser.close()
            self.browser = None

    def __del__(self):
        """Cleanup on destruction."""
        if hasattr(self, 'browser') and self.browser:
            try:
                # Try to get a running loop first
                try:
                    loop = asyncio.get_running_loop()
                    if not loop.is_closed():
                        loop.create_task(self.close())
                    return
                except RuntimeError:
                    # No running loop
                    pass

                # Try to get an existing event loop
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_closed():
                        # Loop is closed, can't clean up async resources
                        return
                    if loop.is_running():
                        loop.create_task(self.close())
                    else:
                        loop.run_until_complete(self.close())
                except RuntimeError:
                    # No event loop available, skip cleanup
                    pass
            except Exception:
                # Suppress all errors during cleanup
                pass
