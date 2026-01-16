"""
Subprocess wrapper for Playwright to avoid signal threading issues.

Playwright's async machinery uses Python's signal module for timeout handling.
Since signal.signal() can ONLY be called from the main thread, and Flask runs
in a daemon thread, we need to run Playwright in a separate subprocess where
it IS the main thread.
"""

import json
import subprocess
import sys
import tempfile
import os
from pathlib import Path
from typing import Optional
from dataclasses import dataclass


@dataclass
class SubprocessPlaywrightResult:
    """Result from subprocess Playwright fetch."""
    success: bool
    html: str = ""
    status_code: int = 0
    method: str = "playwright"
    error: Optional[str] = None
    response_time_ms: int = 0
    screenshot: Optional[bytes] = None


# The script that runs in the subprocess
FETCH_SCRIPT = '''
import asyncio
import json
import sys
import time
import random

async def fetch_url(url, timeout, user_agents, wait_for=None, wait_for_timeout=5000, take_screenshot=False):
    """Fetch URL with Playwright stealth mode."""
    from playwright.async_api import async_playwright
    from playwright_stealth import Stealth

    start_time = time.time()
    result = {
        "success": False,
        "html": "",
        "status_code": 0,
        "method": "playwright",
        "error": None,
        "response_time_ms": 0,
        "screenshot_path": None,
    }

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
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

            user_agent = random.choice(user_agents) if user_agents else None

            context = await browser.new_context(
                user_agent=user_agent,
                viewport={"width": 1920, "height": 1080},
                locale="en-US",
                timezone_id="America/New_York",
                permissions=["geolocation"],
                geolocation={"latitude": 40.7128, "longitude": -74.0060},
                color_scheme="light",
                java_script_enabled=True,
            )

            page = await context.new_page()

            # Apply stealth
            stealth = Stealth()
            await stealth.apply_stealth_async(page)

            # Navigate
            response = await page.goto(url, timeout=timeout, wait_until="networkidle")

            # Wait for selector if specified
            if wait_for:
                try:
                    await page.wait_for_selector(wait_for, timeout=wait_for_timeout)
                except Exception:
                    pass

            # Small delay for JS execution
            await asyncio.sleep(0.5)

            # Get content
            html = await page.content()
            status_code = response.status if response else 0

            result["success"] = status_code == 200
            result["html"] = html
            result["status_code"] = status_code

            # Screenshot if requested
            if take_screenshot:
                import tempfile
                screenshot_file = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
                await page.screenshot(path=screenshot_file.name, full_page=True)
                result["screenshot_path"] = screenshot_file.name

            await page.close()
            await context.close()
            await browser.close()

    except Exception as e:
        result["error"] = str(e)

    result["response_time_ms"] = int((time.time() - start_time) * 1000)
    return result

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--timeout", type=int, default=30000)
    parser.add_argument("--user-agents", default="[]")
    parser.add_argument("--wait-for", default=None)
    parser.add_argument("--wait-for-timeout", type=int, default=5000)
    parser.add_argument("--screenshot", action="store_true")
    args = parser.parse_args()

    user_agents = json.loads(args.user_agents)

    result = asyncio.run(fetch_url(
        args.url,
        args.timeout,
        user_agents,
        args.wait_for,
        args.wait_for_timeout,
        args.screenshot,
    ))

    print(json.dumps(result))

if __name__ == "__main__":
    main()
'''


class SubprocessPlaywrightFetcher:
    """
    Playwright fetcher that runs in a subprocess to avoid signal threading issues.

    This solves the "signal only works in main thread" error that occurs when
    running Playwright from Flask's daemon thread.
    """

    def __init__(self, user_agents: Optional[list] = None):
        """
        Initialize subprocess fetcher.

        Args:
            user_agents: List of user agents to rotate through
        """
        self.user_agents = user_agents or []
        self._script_path = None

    def _get_script_path(self) -> str:
        """Get or create the fetch script file."""
        if self._script_path and os.path.exists(self._script_path):
            return self._script_path

        # Write script to temp file
        script_dir = Path(tempfile.gettempdir()) / "scrapefruit"
        script_dir.mkdir(exist_ok=True)

        script_path = script_dir / "playwright_fetch.py"
        script_path.write_text(FETCH_SCRIPT)

        self._script_path = str(script_path)
        return self._script_path

    def fetch(
        self,
        url: str,
        timeout: int = 30000,
        wait_for: Optional[str] = None,
        wait_for_timeout: int = 5000,
        take_screenshot: bool = False,
    ) -> SubprocessPlaywrightResult:
        """
        Fetch URL using Playwright in a subprocess.

        Args:
            url: URL to fetch
            timeout: Navigation timeout in milliseconds
            wait_for: Optional CSS selector to wait for
            wait_for_timeout: Timeout for wait_for selector
            take_screenshot: Whether to capture a screenshot

        Returns:
            SubprocessPlaywrightResult with success status and content
        """
        script_path = self._get_script_path()

        cmd = [
            sys.executable,
            script_path,
            "--url", url,
            "--timeout", str(timeout),
            "--user-agents", json.dumps(self.user_agents),
        ]

        if wait_for:
            cmd.extend(["--wait-for", wait_for])
            cmd.extend(["--wait-for-timeout", str(wait_for_timeout)])

        if take_screenshot:
            cmd.append("--screenshot")

        try:
            # Run subprocess with timeout (add buffer for process overhead)
            process_timeout = (timeout // 1000) + 60

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=process_timeout,
            )

            if result.returncode != 0:
                return SubprocessPlaywrightResult(
                    success=False,
                    error=f"Subprocess failed: {result.stderr[:500]}",
                )

            # Parse JSON result from stdout
            try:
                data = json.loads(result.stdout)
            except json.JSONDecodeError:
                return SubprocessPlaywrightResult(
                    success=False,
                    error=f"Invalid JSON from subprocess: {result.stdout[:200]}",
                )

            # Load screenshot if present
            screenshot = None
            if data.get("screenshot_path"):
                try:
                    with open(data["screenshot_path"], "rb") as f:
                        screenshot = f.read()
                    os.unlink(data["screenshot_path"])
                except Exception:
                    pass

            return SubprocessPlaywrightResult(
                success=data.get("success", False),
                html=data.get("html", ""),
                status_code=data.get("status_code", 0),
                method="playwright",
                error=data.get("error"),
                response_time_ms=data.get("response_time_ms", 0),
                screenshot=screenshot,
            )

        except subprocess.TimeoutExpired:
            return SubprocessPlaywrightResult(
                success=False,
                error=f"Subprocess timed out after {process_timeout}s",
            )
        except Exception as e:
            return SubprocessPlaywrightResult(
                success=False,
                error=f"Subprocess error: {str(e)}",
            )

    @staticmethod
    def is_available() -> bool:
        """Check if Playwright is available."""
        try:
            import playwright
            from playwright_stealth import Stealth
            return True
        except ImportError:
            return False
