"""Browser-use fetcher for AI-driven browser automation.

This fetcher integrates with the browser-use package for LLM-controlled
browser automation. It's useful for complex pages that require intelligent
navigation, form filling, or bypassing anti-bot measures.

Install: pip install browser-use
         uvx browser-use install  # Install Chromium

Requires an API key for the LLM provider (OpenAI, Anthropic, etc.):
    OPENAI_API_KEY or ANTHROPIC_API_KEY in environment

See: https://github.com/browser-use/browser-use
"""

import asyncio
import time
from typing import Optional, Dict, Any
from dataclasses import dataclass, field

try:
    from browser_use import Agent, Browser
    HAS_BROWSER_USE = True
except ImportError:
    HAS_BROWSER_USE = False


@dataclass
class BrowserUseResult:
    """Result from a Browser-use fetch operation."""

    success: bool
    html: str = ""
    status_code: int = 0
    method: str = "browser_use"
    error: Optional[str] = None
    response_time_ms: int = 0
    screenshot: Optional[bytes] = None
    # Browser-use specific
    agent_history: Optional[Any] = None
    extracted_content: Optional[str] = None


class BrowserUseFetcher:
    """
    Browser-use wrapper for AI-driven browser automation.

    Uses the browser-use library which combines an LLM with Playwright
    for intelligent web automation. The agent can:
    - Navigate complex multi-step processes
    - Fill forms intelligently
    - Handle dynamic content
    - Bypass some anti-bot measures through human-like behavior

    Note: Requires an LLM API key and is slower/more expensive than
    direct fetching. Best used as a last resort or for specific tasks.
    """

    def __init__(self, llm_provider: str = "openai"):
        """
        Initialize the browser-use fetcher.

        Args:
            llm_provider: LLM provider to use ("openai", "anthropic", "ollama")
        """
        self.llm_provider = llm_provider
        self._available: Optional[bool] = None
        self._browser: Optional[Any] = None
        self._llm: Optional[Any] = None

    def is_available(self) -> bool:
        """Check if browser-use is available and configured."""
        if self._available is not None:
            return self._available

        if not HAS_BROWSER_USE:
            self._available = False
            return False

        # Check for API key or Ollama configuration
        import os
        has_key = (
            os.getenv("OPENAI_API_KEY") or
            os.getenv("ANTHROPIC_API_KEY") or
            os.getenv("BROWSER_USE_API_KEY")
        )

        # Also check for Ollama (free, local LLM)
        has_ollama = (
            self.llm_provider == "ollama" or
            os.getenv("OLLAMA_MODEL") or
            self._check_ollama_running()
        )

        self._available = bool(has_key or has_ollama)
        return self._available

    def _check_ollama_running(self) -> bool:
        """Check if Ollama server is running locally."""
        import os
        try:
            import urllib.request
            base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
            req = urllib.request.Request(f"{base_url}/api/tags", method="GET")
            with urllib.request.urlopen(req, timeout=2) as response:
                return response.status == 200
        except Exception:
            return False

    def _get_llm(self):
        """Get or create the LLM instance."""
        if self._llm is not None:
            return self._llm

        if not HAS_BROWSER_USE:
            return None

        import os

        # Try to use ChatBrowserUse if available (optimized for browser tasks)
        try:
            from browser_use import ChatBrowserUse
            self._llm = ChatBrowserUse()
            return self._llm
        except (ImportError, Exception):
            pass

        # Fallback to LangChain providers
        try:
            # Try Ollama first (free, local)
            if self.llm_provider == "ollama" or os.getenv("OLLAMA_MODEL"):
                try:
                    from langchain_ollama import ChatOllama
                    model = os.getenv("OLLAMA_MODEL", "gemma3:4b")
                    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
                    self._llm = ChatOllama(
                        model=model,
                        base_url=base_url,
                        temperature=0,
                    )
                    return self._llm
                except ImportError:
                    pass  # Fall through to cloud providers

            if os.getenv("OPENAI_API_KEY"):
                from langchain_openai import ChatOpenAI
                self._llm = ChatOpenAI(model="gpt-4o-mini")
            elif os.getenv("ANTHROPIC_API_KEY"):
                from langchain_anthropic import ChatAnthropic
                self._llm = ChatAnthropic(model="claude-3-haiku-20240307")
            return self._llm
        except (ImportError, Exception):
            return None

    async def _fetch_async(
        self,
        url: str,
        task: str = "Get the main content from this page",
        timeout: int = 60000,
        take_screenshot: bool = False,
    ) -> BrowserUseResult:
        """Async implementation of fetch."""
        start_time = time.time()

        if not self.is_available():
            return BrowserUseResult(
                success=False,
                error="browser-use not available. Install with: pip install browser-use",
                response_time_ms=int((time.time() - start_time) * 1000),
            )

        llm = self._get_llm()
        if not llm:
            return BrowserUseResult(
                success=False,
                error="No LLM provider configured. Set OPENAI_API_KEY or ANTHROPIC_API_KEY",
                response_time_ms=int((time.time() - start_time) * 1000),
            )

        try:
            browser = Browser()

            # Create agent with task
            full_task = f"Navigate to {url} and {task}"

            agent = Agent(
                task=full_task,
                llm=llm,
                browser=browser,
            )

            # Run agent with timeout
            timeout_seconds = timeout // 1000
            history = await asyncio.wait_for(
                agent.run(),
                timeout=timeout_seconds
            )

            # Extract results
            html = ""
            extracted_content = None

            # Try to get page content from the browser
            if hasattr(browser, 'page') and browser.page:
                try:
                    html = await browser.page.content()
                except Exception:
                    pass

            # Get any extracted content from agent history
            if history and hasattr(history, 'result'):
                extracted_content = str(history.result)

            response_time = int((time.time() - start_time) * 1000)

            # Take screenshot if requested
            screenshot = None
            if take_screenshot and hasattr(browser, 'page') and browser.page:
                try:
                    screenshot = await browser.page.screenshot()
                except Exception:
                    pass

            # Close browser
            try:
                await browser.close()
            except Exception:
                pass

            success = len(html) > 100 or bool(extracted_content)

            return BrowserUseResult(
                success=success,
                html=html,
                status_code=200 if success else 0,
                response_time_ms=response_time,
                screenshot=screenshot,
                agent_history=history,
                extracted_content=extracted_content,
            )

        except asyncio.TimeoutError:
            return BrowserUseResult(
                success=False,
                error=f"Agent timed out after {timeout // 1000} seconds",
                response_time_ms=int((time.time() - start_time) * 1000),
            )
        except Exception as e:
            return BrowserUseResult(
                success=False,
                error=str(e),
                response_time_ms=int((time.time() - start_time) * 1000),
            )

    def fetch(
        self,
        url: str,
        timeout: int = 60000,
        task: str = "Get the main content from this page",
        take_screenshot: bool = False,
        **kwargs,
    ) -> BrowserUseResult:
        """
        Fetch a URL using AI-driven browser automation.

        Args:
            url: The URL to fetch
            timeout: Timeout in milliseconds
            task: Natural language description of what to extract
            take_screenshot: Whether to capture a screenshot

        Returns:
            BrowserUseResult with extracted content
        """
        # Run async code
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            # Already in async context - run in thread
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    lambda: asyncio.run(self._fetch_async(url, task, timeout, take_screenshot))
                )
                return future.result(timeout=timeout // 1000 + 30)
        else:
            # Not in async context - run directly
            return asyncio.run(self._fetch_async(url, task, timeout, take_screenshot))

    def extract_data(
        self,
        url: str,
        extraction_prompt: str,
        timeout: int = 60000,
    ) -> BrowserUseResult:
        """
        Extract specific data from a URL using AI interpretation.

        This is browser-use's strength - it can understand complex
        instructions and navigate multi-step processes.

        Args:
            url: The URL to process
            extraction_prompt: Natural language description of what to extract
                Example: "Find the product price, title, and availability status"
            timeout: Timeout in milliseconds

        Returns:
            BrowserUseResult with extracted_content containing the data
        """
        return self.fetch(url, timeout=timeout, task=extraction_prompt)


# Optional: Create singleton for reuse
_browser_use_fetcher: Optional[BrowserUseFetcher] = None


def get_browser_use_fetcher() -> Optional[BrowserUseFetcher]:
    """Get the browser-use fetcher singleton, or None if unavailable."""
    global _browser_use_fetcher

    if not HAS_BROWSER_USE:
        return None

    if _browser_use_fetcher is None:
        fetcher = BrowserUseFetcher()
        if fetcher.is_available():
            _browser_use_fetcher = fetcher
        else:
            return None

    return _browser_use_fetcher
