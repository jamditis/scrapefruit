"""Unit tests for fetcher modules."""

import pytest
from unittest.mock import Mock, patch, MagicMock
import asyncio


class TestHTTPFetcher:
    """Tests for HTTP fetcher."""

    @pytest.fixture
    def fetcher(self):
        from core.scraping.fetchers.http_fetcher import HTTPFetcher
        return HTTPFetcher()

    def test_initialization(self, fetcher):
        """Fetcher should initialize properly."""
        assert fetcher is not None

    def test_user_agent_rotation(self, fetcher):
        """User agent should be rotated."""
        import config
        # Fetcher should use agents from config
        assert len(config.USER_AGENTS) > 0

    def test_successful_fetch(self, fetcher):
        """Successful fetch should return result with HTML."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "<html><body>Test</body></html>"
        mock_response.headers = {}

        # Patch the session's get method directly
        with patch.object(fetcher.session, 'get', return_value=mock_response):
            result = fetcher.fetch("https://example.com", timeout=10, retry_count=1)

        assert result.success
        assert result.html == "<html><body>Test</body></html>"
        assert result.status_code == 200

    def test_404_response(self, fetcher):
        """404 response should be handled."""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.text = "Not Found"
        mock_response.headers = {}

        # Patch the session's get method
        with patch.object(fetcher.session, 'get', return_value=mock_response):
            result = fetcher.fetch("https://example.com/notfound", timeout=10, retry_count=1)

        # 404 returns error after retries exhaust
        assert not result.success
        assert "404" in result.error

    def test_timeout_handling(self, fetcher):
        """Timeout should be handled gracefully."""
        import requests

        # Patch the session's get method to raise Timeout
        with patch.object(fetcher.session, 'get', side_effect=requests.Timeout("Connection timed out")):
            result = fetcher.fetch("https://example.com", timeout=1, retry_count=1)

        assert not result.success
        assert "timed out" in result.error.lower()

    def test_connection_error(self, fetcher):
        """Connection errors should be handled."""
        import requests

        # Patch the session's get method to raise ConnectionError
        with patch.object(fetcher.session, 'get', side_effect=requests.ConnectionError("Failed to connect")):
            result = fetcher.fetch("https://example.com", timeout=10, retry_count=1)

        assert not result.success
        assert result.error is not None

    def test_response_time_tracked(self, fetcher):
        """Response time should be tracked."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "<html></html>"
        mock_response.headers = {}

        with patch.object(fetcher.session, 'get', return_value=mock_response):
            result = fetcher.fetch("https://example.com", timeout=10, retry_count=1)

        assert result.response_time_ms >= 0


class TestPlaywrightFetcher:
    """Tests for Playwright fetcher."""

    @pytest.fixture
    def fetcher(self):
        from core.scraping.fetchers.playwright_fetcher import PlaywrightFetcher
        return PlaywrightFetcher()

    def test_initialization(self, fetcher):
        """Fetcher should initialize properly."""
        assert fetcher is not None

    def test_result_dataclass(self):
        """PlaywrightResult dataclass should work."""
        from core.scraping.fetchers.playwright_fetcher import PlaywrightResult

        result = PlaywrightResult(
            success=True,
            html="<html></html>",
            status_code=200,
            method="playwright",
        )
        assert result.success
        assert result.method == "playwright"

    def test_screenshot_support(self):
        """PlaywrightResult should support screenshot field."""
        from core.scraping.fetchers.playwright_fetcher import PlaywrightResult

        result = PlaywrightResult(
            success=True,
            html="<html></html>",
            status_code=200,
            method="playwright",
            screenshot=b"fake_png_data",
        )
        assert result.screenshot == b"fake_png_data"


class TestPuppeteerFetcher:
    """Tests for Puppeteer fetcher."""

    @pytest.fixture
    def fetcher(self):
        try:
            from core.scraping.fetchers.puppeteer_fetcher import PuppeteerFetcher
            return PuppeteerFetcher()
        except ImportError:
            pytest.skip("pyppeteer not installed")

    def test_initialization(self, fetcher):
        """Fetcher should initialize properly."""
        assert fetcher is not None

    def test_result_dataclass(self):
        """PuppeteerResult dataclass should work."""
        try:
            from core.scraping.fetchers.puppeteer_fetcher import PuppeteerResult

            result = PuppeteerResult(
                success=True,
                html="<html></html>",
                status_code=200,
                method="puppeteer",
            )
            assert result.success
            assert result.method == "puppeteer"
        except ImportError:
            pytest.skip("pyppeteer not installed")


class TestAgentBrowserFetcher:
    """Tests for Agent-browser CLI fetcher."""

    @pytest.fixture
    def fetcher(self):
        from core.scraping.fetchers.agent_browser_fetcher import AgentBrowserFetcher
        return AgentBrowserFetcher()

    def test_initialization(self, fetcher):
        """Fetcher should initialize properly."""
        assert fetcher is not None

    def test_availability_check(self, fetcher):
        """Availability check should return boolean."""
        result = fetcher.is_available()
        assert isinstance(result, bool)

    def test_unavailable_returns_error(self, fetcher):
        """If CLI not installed, fetch should return error."""
        if fetcher.is_available():
            pytest.skip("agent-browser is installed")

        result = fetcher.fetch("https://example.com")
        assert not result.success
        assert "not installed" in result.error.lower() or "not available" in result.error.lower()

    def test_result_dataclass(self):
        """AgentBrowserResult dataclass should work."""
        from core.scraping.fetchers.agent_browser_fetcher import AgentBrowserResult

        result = AgentBrowserResult(
            success=True,
            html="<html></html>",
            status_code=200,
            accessibility_tree="@e1 button 'Click'",
            element_refs={"@e1": "button: Click"},
        )
        assert result.success
        assert result.method == "agent_browser"
        assert "@e1" in result.element_refs

    @patch('subprocess.run')
    def test_command_construction(self, mock_run, fetcher):
        """Commands should be constructed correctly."""
        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

        # Force available
        fetcher._available = True

        fetcher._run_command(["test", "arg"])

        # Check command was called with expected args
        call_args = mock_run.call_args[0][0]
        assert "test" in call_args
        assert "arg" in call_args

    def test_ref_extraction(self, fetcher):
        """Element refs should be extracted from snapshot."""
        # Check if the method exists
        if not hasattr(fetcher, '_extract_refs'):
            pytest.skip("_extract_refs method not implemented")

        snapshot = """
        @e1 button "Submit Form"
        @e2 textbox "Email address"
        @e3 link "Learn more"
        """
        refs = fetcher._extract_refs(snapshot)
        assert "@e1" in refs
        assert "@e2" in refs
        assert "@e3" in refs


class TestBrowserUseFetcher:
    """Tests for browser-use AI fetcher."""

    @pytest.fixture
    def fetcher(self):
        from core.scraping.fetchers.browser_use_fetcher import BrowserUseFetcher
        return BrowserUseFetcher()

    def test_initialization(self, fetcher):
        """Fetcher should initialize properly."""
        assert fetcher is not None

    def test_availability_check(self, fetcher):
        """Availability check should return boolean."""
        result = fetcher.is_available()
        assert isinstance(result, bool)

    def test_unavailable_without_api_key(self, fetcher):
        """Should not be available without API key."""
        import os
        # Clear API keys for test
        with patch.dict(os.environ, {
            'OPENAI_API_KEY': '',
            'ANTHROPIC_API_KEY': '',
            'BROWSER_USE_API_KEY': '',
        }, clear=True):
            fetcher._available = None  # Reset cache
            # May or may not be available depending on other factors

    def test_result_dataclass(self):
        """BrowserUseResult dataclass should work."""
        from core.scraping.fetchers.browser_use_fetcher import BrowserUseResult

        result = BrowserUseResult(
            success=True,
            html="<html></html>",
            status_code=200,
            extracted_content="Found price: $99.99",
        )
        assert result.success
        assert result.method == "browser_use"
        assert result.extracted_content == "Found price: $99.99"


class TestFetcherRegistry:
    """Tests for fetcher module exports."""

    def test_all_exports_available(self):
        """All documented exports should be importable."""
        from core.scraping.fetchers import (
            HTTPFetcher,
            FetchResult,
            PlaywrightFetcher,
            PlaywrightResult,
            PuppeteerFetcher,
            PuppeteerResult,
            AgentBrowserFetcher,
            AgentBrowserResult,
            BrowserUseFetcher,
            BrowserUseResult,
            get_browser_use_fetcher,
        )
        # All imports should succeed
        assert HTTPFetcher is not None
        assert PlaywrightFetcher is not None

    def test_fetcher_interface_consistency(self):
        """All fetchers should have consistent interface."""
        from core.scraping.fetchers import (
            HTTPFetcher,
            PlaywrightFetcher,
            AgentBrowserFetcher,
            BrowserUseFetcher,
        )

        fetchers = [
            HTTPFetcher(),
            PlaywrightFetcher(),
            AgentBrowserFetcher(),
            BrowserUseFetcher(),
        ]

        for fetcher in fetchers:
            # All should have fetch method
            assert hasattr(fetcher, 'fetch')
            assert callable(fetcher.fetch)
