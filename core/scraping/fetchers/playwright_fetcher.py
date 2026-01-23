"""Playwright fetcher for JavaScript-heavy sites with stealth mode."""

import asyncio
import random
import threading
import time
from typing import Optional, Dict, Any
from dataclasses import dataclass

from playwright.async_api import async_playwright, Page, Browser, BrowserContext
from playwright_stealth import Stealth

import config
from core.scraping.fetchers.playwright_subprocess import (
    SubprocessPlaywrightFetcher,
    SubprocessPlaywrightResult,
)

# Thread-local storage for event loop reuse
_thread_local = threading.local()

# Flag to track if we've hit the signal error (per-process)
_use_subprocess_fallback = False


@dataclass
class PlaywrightResult:
    """Result from a Playwright fetch operation."""

    success: bool
    html: str = ""
    status_code: int = 0
    method: str = "playwright"
    error: Optional[str] = None
    response_time_ms: int = 0
    screenshot: Optional[bytes] = None


class PlaywrightFetcher:
    """
    Playwright-based fetcher with stealth mode for anti-bot bypass.

    Uses a persistent browser instance for efficiency.
    """

    def __init__(self):
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self._lock = asyncio.Lock()

    async def _ensure_browser(self):
        """Ensure browser is initialized."""
        if self.browser is None:
            playwright = await async_playwright().start()

            # Build launch options
            launch_options = {
                "headless": True,
                "args": [
                    "--disable-blink-features=AutomationControlled",
                    "--disable-features=IsolateOrigins,site-per-process",
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-accelerated-2d-canvas",
                    "--disable-gpu",
                ],
            }

            # Use system Chromium on ARM64 where Playwright's bundled version doesn't work
            chromium_path = getattr(config, "CHROMIUM_EXECUTABLE_PATH", None)
            if chromium_path:
                launch_options["executable_path"] = chromium_path

            self.browser = await playwright.chromium.launch(**launch_options)

    async def _get_context(self) -> BrowserContext:
        """Get or create a browser context with stealth settings."""
        await self._ensure_browser()

        user_agent = random.choice(config.USER_AGENTS)

        context = await self.browser.new_context(
            user_agent=user_agent,
            viewport={"width": 1920, "height": 1080},
            locale="en-US",
            timezone_id="America/New_York",
            permissions=["geolocation"],
            geolocation={"latitude": 40.7128, "longitude": -74.0060},
            color_scheme="light",
            java_script_enabled=True,
        )

        return context

    async def fetch_async(
        self,
        url: str,
        timeout: int = 30000,
        wait_for: Optional[str] = None,
        wait_for_timeout: int = 5000,
        take_screenshot: bool = False,
    ) -> PlaywrightResult:
        """
        Fetch a URL using Playwright with stealth mode.

        Args:
            url: The URL to fetch
            timeout: Navigation timeout in milliseconds
            wait_for: Optional CSS selector to wait for
            wait_for_timeout: Timeout for wait_for selector
            take_screenshot: Whether to capture a screenshot

        Returns:
            PlaywrightResult with success status and content
        """
        async with self._lock:
            start_time = time.time()
            context = None
            page = None

            try:
                context = await self._get_context()
                page = await context.new_page()

                # Apply stealth mode to the page
                stealth = Stealth()
                await stealth.apply_stealth_async(page)

                # Navigate
                response = await page.goto(
                    url,
                    timeout=timeout,
                    wait_until="networkidle",
                )

                # Wait for specific element if requested
                if wait_for:
                    try:
                        await page.wait_for_selector(wait_for, timeout=wait_for_timeout)
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
                    screenshot = await page.screenshot(full_page=True)

                return PlaywrightResult(
                    success=status_code == 200,
                    html=html,
                    status_code=status_code,
                    method="playwright",
                    response_time_ms=response_time,
                    screenshot=screenshot,
                )

            except Exception as e:
                response_time = int((time.time() - start_time) * 1000)
                return PlaywrightResult(
                    success=False,
                    method="playwright",
                    error=str(e),
                    response_time_ms=response_time,
                )
            finally:
                if page:
                    await page.close()
                if context:
                    await context.close()

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
    ) -> PlaywrightResult:
        """
        Synchronous wrapper for fetch_async.

        Automatically falls back to subprocess execution if signal threading
        issues are detected (common when Flask runs in a daemon thread).

        Args:
            url: The URL to fetch
            timeout: Navigation timeout in milliseconds
            wait_for: Optional CSS selector to wait for
            wait_for_timeout: Timeout for wait_for selector
            take_screenshot: Whether to capture a screenshot
            retry_count: Number of retry attempts on failure

        Returns:
            PlaywrightResult with success status and content
        """
        global _use_subprocess_fallback

        # If we've previously hit signal errors, go straight to subprocess
        if _use_subprocess_fallback:
            return self._fetch_via_subprocess(
                url, timeout, wait_for, wait_for_timeout, take_screenshot
            )

        last_error = None

        for attempt in range(retry_count + 1):
            try:
                # Try to get existing loop
                try:
                    loop = asyncio.get_running_loop()
                    # If there's a running loop, we need to run in a new thread
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(
                            self._run_in_reusable_loop,
                            url, timeout, wait_for, wait_for_timeout, take_screenshot
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

                # Handle signal error by switching to subprocess fallback
                if "signal only works in main thread" in last_error:
                    _use_subprocess_fallback = True
                    # Retry immediately with subprocess
                    return self._fetch_via_subprocess(
                        url, timeout, wait_for, wait_for_timeout, take_screenshot
                    )

                if attempt >= retry_count:
                    break
                # Exponential backoff before retry
                time.sleep((2 ** attempt) * 0.5)

        return PlaywrightResult(
            success=False,
            method="playwright",
            error=last_error,
        )

    def _fetch_via_subprocess(
        self,
        url: str,
        timeout: int,
        wait_for: Optional[str],
        wait_for_timeout: int,
        take_screenshot: bool,
    ) -> PlaywrightResult:
        """
        Fetch using subprocess to avoid signal threading issues.

        This runs Playwright in a separate Python process where it IS the
        main thread, avoiding the signal.signal() restriction.
        """
        subprocess_fetcher = SubprocessPlaywrightFetcher(
            user_agents=getattr(config, "USER_AGENTS", [])
        )

        result = subprocess_fetcher.fetch(
            url=url,
            timeout=timeout,
            wait_for=wait_for,
            wait_for_timeout=wait_for_timeout,
            take_screenshot=take_screenshot,
        )

        # Convert SubprocessPlaywrightResult to PlaywrightResult
        return PlaywrightResult(
            success=result.success,
            html=result.html,
            status_code=result.status_code,
            method="playwright",
            error=result.error,
            response_time_ms=result.response_time_ms,
            screenshot=result.screenshot,
        )

    def _run_in_reusable_loop(
        self,
        url: str,
        timeout: int,
        wait_for: Optional[str],
        wait_for_timeout: int,
        take_screenshot: bool,
    ) -> PlaywrightResult:
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

    def cleanup(self):
        """
        Synchronous cleanup for thread shutdown.

        Call this when the thread is shutting down to properly close
        the browser and event loop.
        """
        if self.browser:
            try:
                loop = self._get_or_create_loop()
                if not loop.is_closed():
                    loop.run_until_complete(self.close())
            except Exception:
                pass

        # Close the thread-local event loop
        if hasattr(_thread_local, 'loop') and not _thread_local.loop.is_closed():
            try:
                _thread_local.loop.close()
            except Exception:
                pass

    def __del__(self):
        """Cleanup on destruction."""
        if self.browser:
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

                # Try to use the thread-local loop
                if hasattr(_thread_local, 'loop') and not _thread_local.loop.is_closed():
                    _thread_local.loop.run_until_complete(self.close())
                    return

                # Try to get an existing event loop
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_closed():
                        # Loop is closed, can't clean up async resources
                        # This is expected during shutdown, just skip
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
