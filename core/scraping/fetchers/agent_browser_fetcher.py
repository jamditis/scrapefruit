"""Agent-browser fetcher using native Playwright accessibility API.

This fetcher provides AI-friendly browser automation with:
- Accessibility tree snapshots with element refs (@e1, @e2, etc.)
- Semantic element identification (role, name, description)
- Click, fill, and type operations using element refs

Unlike the original CLI-based implementation, this version:
- Works on ARM64 (Raspberry Pi) using system Chromium
- Uses Playwright's native accessibility API directly
- Doesn't require npm or external CLI tools
"""

import asyncio
import random
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from playwright.async_api import Page, async_playwright

import config


@dataclass
class AgentBrowserResult:
    """Result from an Agent-browser fetch operation."""

    success: bool
    html: str = ""
    status_code: int = 0
    method: str = "agent_browser"
    error: Optional[str] = None
    response_time_ms: int = 0
    screenshot: Optional[bytes] = None
    # Agent-browser unique features
    accessibility_tree: Optional[str] = None
    element_refs: Dict[str, Dict[str, Any]] = field(default_factory=dict)


class AgentBrowserFetcher:
    """
    Playwright-based fetcher with accessibility tree support for AI-driven automation.

    Provides element refs (@e1, @e2, etc.) that map to page elements, enabling
    AI agents to interact with pages using semantic descriptions.

    This implementation uses Playwright's native accessibility API rather than
    wrapping an external CLI, making it compatible with ARM64 systems.
    """

    def __init__(self):
        self._playwright = None
        self._browser = None
        self._page: Optional[Page] = None
        self._element_refs: Dict[str, Dict[str, Any]] = {}
        self._ref_counter = 0
        self._lock = asyncio.Lock()

    def is_available(self) -> bool:
        """Check if this fetcher is available (Playwright + Chromium)."""
        try:
            # Check if Chromium is available (either bundled or system)
            chromium_path = getattr(config, "CHROMIUM_EXECUTABLE_PATH", None)
            if chromium_path:
                import os
                return os.path.exists(chromium_path)
            # On non-ARM64, Playwright's bundled Chromium should work
            return True
        except Exception:
            return False

    async def _ensure_browser(self):
        """Initialize browser if needed."""
        if self._browser is None:
            self._playwright = await async_playwright().start()

            launch_options = {
                "headless": True,
                "args": [
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                ],
            }

            # Use system Chromium on ARM64
            chromium_path = getattr(config, "CHROMIUM_EXECUTABLE_PATH", None)
            if chromium_path:
                launch_options["executable_path"] = chromium_path

            self._browser = await self._playwright.chromium.launch(**launch_options)

    async def _get_page(self) -> Page:
        """Get or create a browser page."""
        await self._ensure_browser()

        if self._page is None or self._page.is_closed():
            user_agent = random.choice(config.USER_AGENTS)
            context = await self._browser.new_context(
                user_agent=user_agent,
                viewport={"width": 1920, "height": 1080},
                locale="en-US",
            )
            self._page = await context.new_page()

        return self._page

    async def _get_accessibility_snapshot(self, page: Page) -> str:
        """
        Get accessibility tree snapshot from the page.

        Returns the ARIA snapshot as a text string.
        """
        try:
            # Use Playwright's aria_snapshot on the root element
            locator = page.locator(":root")
            snapshot = await locator.aria_snapshot()
            return snapshot if snapshot else ""
        except Exception:
            return ""

    def _parse_aria_snapshot(
        self,
        snapshot: str,
        refs: Dict[str, Dict[str, Any]],
    ) -> str:
        """
        Parse ARIA snapshot string and add element refs to interactive elements.

        The aria_snapshot format is YAML-like:
        - document:
          - heading "Example Domain" [level=1]
          - link "Learn more":
            - /url: https://example.com

        Returns the snapshot with refs added to interactive elements.
        """
        if not snapshot:
            return ""

        # Interactive roles that get refs
        interactive_roles = {
            "button", "link", "textbox", "checkbox", "radio", "combobox",
            "listbox", "option", "menuitem", "tab", "switch", "slider",
            "spinbutton", "searchbox", "menubar", "menu", "menuitemcheckbox",
            "menuitemradio", "treeitem", "gridcell", "row", "cell", "img",
        }

        output_lines = []
        lines = snapshot.split("\n")

        for line in lines:
            stripped = line.lstrip("- ")
            indent = line[:len(line) - len(line.lstrip())]

            # Parse role and name from lines like: heading "Title" [level=1]
            # or: link "Learn more":
            role_match = re.match(r'^(\w+)(?:\s+"([^"]*)")?(.*)$', stripped)

            if role_match:
                role = role_match.group(1).lower()
                name = role_match.group(2) or ""
                rest = role_match.group(3) or ""

                if role in interactive_roles:
                    self._ref_counter += 1
                    ref_id = f"@e{self._ref_counter}"

                    # Store element info
                    refs[ref_id] = {
                        "role": role,
                        "name": name,
                        "line": line,
                    }

                    # Rebuild line with ref
                    if name:
                        new_line = f'{indent}- {ref_id} {role} "{name}"{rest}'
                    else:
                        new_line = f'{indent}- {ref_id} {role}{rest}'
                    output_lines.append(new_line)
                else:
                    output_lines.append(line)
            else:
                output_lines.append(line)

        return "\n".join(output_lines)

    async def fetch_async(
        self,
        url: str,
        timeout: int = 30000,
        wait_for: Optional[str] = None,
        wait_for_timeout: int = 5000,
        capture_accessibility: bool = True,
        take_screenshot: bool = False,
    ) -> AgentBrowserResult:
        """
        Fetch a URL and capture accessibility tree.

        Args:
            url: The URL to fetch
            timeout: Navigation timeout in milliseconds
            wait_for: Optional CSS selector to wait for
            wait_for_timeout: Timeout for wait_for selector
            capture_accessibility: Whether to capture accessibility tree
            take_screenshot: Whether to capture a screenshot

        Returns:
            AgentBrowserResult with HTML, accessibility tree, and element refs
        """
        start_time = time.time()

        try:
            page = await self._get_page()

            # Navigate
            response = await page.goto(url, timeout=timeout, wait_until="networkidle")

            # Wait for specific element if requested
            if wait_for:
                try:
                    await page.wait_for_selector(wait_for, timeout=wait_for_timeout)
                except Exception:
                    pass

            # Small delay for JS execution
            await asyncio.sleep(0.5)

            # Get HTML
            html = await page.content()
            status_code = response.status if response else 0

            # Get accessibility tree
            accessibility_tree = None
            element_refs = {}

            if capture_accessibility:
                self._ref_counter = 0
                self._element_refs = {}

                snapshot = await self._get_accessibility_snapshot(page)
                if snapshot:
                    accessibility_tree = self._parse_aria_snapshot(
                        snapshot, self._element_refs
                    )
                    element_refs = self._element_refs.copy()

            # Screenshot if requested
            screenshot = None
            if take_screenshot:
                screenshot = await page.screenshot(full_page=True)

            response_time = int((time.time() - start_time) * 1000)

            return AgentBrowserResult(
                success=status_code == 200,
                html=html,
                status_code=status_code,
                method="agent_browser",
                response_time_ms=response_time,
                screenshot=screenshot,
                accessibility_tree=accessibility_tree,
                element_refs=element_refs,
            )

        except Exception as e:
            response_time = int((time.time() - start_time) * 1000)
            return AgentBrowserResult(
                success=False,
                method="agent_browser",
                error=str(e),
                response_time_ms=response_time,
            )

    def fetch(
        self,
        url: str,
        timeout: int = 30000,
        wait_for: Optional[str] = None,
        wait_for_timeout: int = 5000,
        capture_accessibility: bool = True,
        take_screenshot: bool = False,
        retry_count: int = 0,
    ) -> AgentBrowserResult:
        """
        Synchronous wrapper for fetch_async.

        Args:
            url: The URL to fetch
            timeout: Navigation timeout in milliseconds
            wait_for: Optional CSS selector to wait for
            wait_for_timeout: Timeout for wait_for selector
            capture_accessibility: Whether to capture accessibility tree
            take_screenshot: Whether to capture a screenshot
            retry_count: Number of retries on failure

        Returns:
            AgentBrowserResult with HTML, accessibility tree, and element refs
        """
        try:
            # Try to get existing loop
            try:
                loop = asyncio.get_running_loop()
                # If there's a running loop, use thread pool
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(self._run_in_new_loop, url, timeout,
                        wait_for, wait_for_timeout, capture_accessibility, take_screenshot)
                    return future.result(timeout=timeout // 1000 + 30)
            except RuntimeError:
                # No running loop, create one
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    return loop.run_until_complete(
                        self.fetch_async(
                            url=url,
                            timeout=timeout,
                            wait_for=wait_for,
                            wait_for_timeout=wait_for_timeout,
                            capture_accessibility=capture_accessibility,
                            take_screenshot=take_screenshot,
                        )
                    )
                finally:
                    # Don't close the loop to avoid EPIPE errors
                    pass
        except Exception as e:
            return AgentBrowserResult(
                success=False,
                method="agent_browser",
                error=str(e),
            )

    def _run_in_new_loop(
        self,
        url: str,
        timeout: int,
        wait_for: Optional[str],
        wait_for_timeout: int,
        capture_accessibility: bool,
        take_screenshot: bool,
    ) -> AgentBrowserResult:
        """Run fetch in a new event loop (for thread pool execution)."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(
                self.fetch_async(
                    url=url,
                    timeout=timeout,
                    wait_for=wait_for,
                    wait_for_timeout=wait_for_timeout,
                    capture_accessibility=capture_accessibility,
                    take_screenshot=take_screenshot,
                )
            )
        finally:
            pass  # Don't close loop to avoid EPIPE

    async def click_async(self, ref_or_selector: str, timeout: int = 5000) -> bool:
        """
        Click an element by ref (@e1) or CSS selector.

        Args:
            ref_or_selector: Element ref like @e1 or CSS selector
            timeout: Click timeout in milliseconds

        Returns:
            True if click succeeded
        """
        if not self._page:
            return False

        try:
            if ref_or_selector.startswith("@e"):
                # Find element by role and name from our refs
                ref_info = self._element_refs.get(ref_or_selector)
                if not ref_info:
                    return False

                role = ref_info.get("role", "")
                name = ref_info.get("name", "")

                # Use Playwright's role-based locator
                if role and name:
                    locator = self._page.get_by_role(role, name=name)
                elif name:
                    locator = self._page.get_by_text(name)
                else:
                    return False

                await locator.click(timeout=timeout)
            else:
                # CSS selector
                await self._page.click(ref_or_selector, timeout=timeout)

            return True
        except Exception:
            return False

    def click(self, ref_or_selector: str, timeout: int = 5000) -> bool:
        """Synchronous wrapper for click_async."""
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(self.click_async(ref_or_selector, timeout))
        finally:
            loop.close()

    async def fill_async(
        self, ref_or_selector: str, text: str, timeout: int = 5000
    ) -> bool:
        """
        Fill a form field (clears first).

        Args:
            ref_or_selector: Element ref like @e1 or CSS selector
            text: Text to enter
            timeout: Fill timeout in milliseconds

        Returns:
            True if fill succeeded
        """
        if not self._page:
            return False

        try:
            if ref_or_selector.startswith("@e"):
                ref_info = self._element_refs.get(ref_or_selector)
                if not ref_info:
                    return False

                role = ref_info.get("role", "")
                name = ref_info.get("name", "")

                if role in ("textbox", "searchbox", "combobox"):
                    locator = self._page.get_by_role(role, name=name)
                elif name:
                    locator = self._page.get_by_label(name)
                else:
                    return False

                await locator.fill(text, timeout=timeout)
            else:
                await self._page.fill(ref_or_selector, text, timeout=timeout)

            return True
        except Exception:
            return False

    def fill(self, ref_or_selector: str, text: str, timeout: int = 5000) -> bool:
        """Synchronous wrapper for fill_async."""
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(
                self.fill_async(ref_or_selector, text, timeout)
            )
        finally:
            loop.close()

    async def get_snapshot_async(self, interactive_only: bool = True) -> Optional[str]:
        """
        Get accessibility tree snapshot of current page.

        Args:
            interactive_only: If True, only include interactive elements

        Returns:
            Text representation of accessibility tree with refs
        """
        if not self._page:
            return None

        try:
            self._ref_counter = 0
            self._element_refs = {}

            snapshot = await self._get_accessibility_snapshot(self._page)
            if not snapshot:
                return None

            # Parse and add refs to the snapshot
            tree_text = self._parse_aria_snapshot(snapshot, self._element_refs)

            if interactive_only:
                # Filter to only lines with refs
                lines = tree_text.split("\n")
                interactive_lines = [
                    line for line in lines if re.search(r"@e\d+", line)
                ]
                return "\n".join(interactive_lines)

            return tree_text
        except Exception:
            return None

    def get_snapshot(self, interactive_only: bool = True) -> Optional[str]:
        """Synchronous wrapper for get_snapshot_async."""
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(self.get_snapshot_async(interactive_only))
        finally:
            loop.close()

    async def close_async(self):
        """Close browser and cleanup resources."""
        if self._page:
            await self._page.close()
            self._page = None

        if self._browser:
            await self._browser.close()
            self._browser = None

        if self._playwright:
            await self._playwright.stop()
            self._playwright = None

    def close(self):
        """Synchronous close."""
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(self.close_async())
        finally:
            loop.close()
