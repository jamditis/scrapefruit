"""Playwright fetcher for JavaScript-heavy sites with stealth mode."""

import asyncio
import random
import time
from typing import Optional, Dict, Any
from dataclasses import dataclass

from playwright.async_api import async_playwright, Page, Browser, BrowserContext
from playwright_stealth import Stealth

import config


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
            self.browser = await playwright.chromium.launch(
                headless=True,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--disable-features=IsolateOrigins,site-per-process",
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-accelerated-2d-canvas",
                    "--disable-gpu",
                ],
            )

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

    def fetch(
        self,
        url: str,
        timeout: int = 30000,
        wait_for: Optional[str] = None,
        wait_for_timeout: int = 5000,
        take_screenshot: bool = False,
    ) -> PlaywrightResult:
        """
        Synchronous wrapper for fetch_async.

        Creates event loop if needed. Handles threading issues with signal.
        """
        import threading

        # Check if we're in a thread (Flask runs in threads)
        is_main_thread = threading.current_thread() is threading.main_thread()

        try:
            # Try to get existing loop
            try:
                loop = asyncio.get_running_loop()
                # If there's a running loop, we need to run in a new thread
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(self._run_in_new_loop, url, timeout, wait_for, wait_for_timeout, take_screenshot)
                    return future.result(timeout=timeout // 1000 + 30)
            except RuntimeError:
                # No running loop
                pass

            # Create new event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            try:
                return loop.run_until_complete(
                    self.fetch_async(
                        url,
                        timeout=timeout,
                        wait_for=wait_for,
                        wait_for_timeout=wait_for_timeout,
                        take_screenshot=take_screenshot,
                    )
                )
            finally:
                loop.close()

        except Exception as e:
            error_msg = str(e)
            # Handle signal error gracefully
            if "signal only works in main thread" in error_msg:
                error_msg = "Playwright unavailable in threaded context. Try HTTP or restart the application."
            return PlaywrightResult(
                success=False,
                method="playwright",
                error=error_msg,
            )

    def _run_in_new_loop(
        self,
        url: str,
        timeout: int,
        wait_for: Optional[str],
        wait_for_timeout: int,
        take_screenshot: bool,
    ) -> PlaywrightResult:
        """Run fetch in a completely new event loop in a separate thread."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(
                self.fetch_async(url, timeout, wait_for, wait_for_timeout, take_screenshot)
            )
        finally:
            loop.close()

    async def close(self):
        """Close the browser."""
        if self.browser:
            await self.browser.close()
            self.browser = None

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
