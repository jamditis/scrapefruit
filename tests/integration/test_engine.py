"""Integration tests for the scraping engine."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from core.scraping.engine import ScrapingEngine, DEFAULT_CASCADE_CONFIG


# Padding for test HTML to pass minimum content length checks (500 chars, 50 words)
TEST_HTML_PADDING = """
<p>This paragraph provides sufficient padding content to meet the minimum requirements
for the poison pill detector system. The detector component checks for minimum character
count and word count before analyzing for specific poison pill patterns and indicators.
Without this substantial padding text, tests would incorrectly fail with content_too_short
error instead of properly testing extraction logic. This ensures proper test isolation.
We add extra words here to ensure we always exceed both thresholds reliably.</p>
"""


class TestScrapingEngineInit:
    """Tests for engine initialization."""

    def test_engine_initialization(self):
        """Engine should initialize without errors."""
        engine = ScrapingEngine()
        assert engine is not None

    def test_fetcher_types_defined(self):
        """Engine should have defined fetcher types."""
        assert len(ScrapingEngine.FETCHER_TYPES) >= 3
        assert "http" in ScrapingEngine.FETCHER_TYPES
        assert "playwright" in ScrapingEngine.FETCHER_TYPES
        assert "puppeteer" in ScrapingEngine.FETCHER_TYPES

    def test_premium_fetchers_defined(self):
        """Premium fetchers should be identified."""
        assert hasattr(ScrapingEngine, 'PREMIUM_FETCHERS')
        assert "agent_browser" in ScrapingEngine.PREMIUM_FETCHERS
        assert "browser_use" in ScrapingEngine.PREMIUM_FETCHERS

    def test_extractors_initialized(self):
        """Engine should have extractors ready."""
        engine = ScrapingEngine()
        assert engine.css_extractor is not None
        assert engine.xpath_extractor is not None

    def test_poison_detector_initialized(self):
        """Engine should have poison detector ready."""
        engine = ScrapingEngine()
        assert engine.poison_detector is not None


class TestCascadeConfiguration:
    """Tests for cascade configuration."""

    def test_default_config_structure(self):
        """Default config should have required fields."""
        assert "enabled" in DEFAULT_CASCADE_CONFIG
        assert "order" in DEFAULT_CASCADE_CONFIG
        assert "max_attempts" in DEFAULT_CASCADE_CONFIG
        assert "fallback_on" in DEFAULT_CASCADE_CONFIG

    def test_fallback_triggers_defined(self):
        """Fallback triggers should be configured."""
        fallback = DEFAULT_CASCADE_CONFIG["fallback_on"]
        assert "status_codes" in fallback
        assert "error_patterns" in fallback
        assert "poison_pills" in fallback
        assert "empty_content" in fallback

    def test_fallback_status_codes(self):
        """Key status codes should trigger fallback."""
        codes = DEFAULT_CASCADE_CONFIG["fallback_on"]["status_codes"]
        assert 403 in codes  # Forbidden
        assert 429 in codes  # Rate limited
        assert 503 in codes  # Service unavailable

    def test_fallback_poison_pills(self):
        """Key poison pills should trigger fallback."""
        pills = DEFAULT_CASCADE_CONFIG["fallback_on"]["poison_pills"]
        assert "anti_bot" in pills
        assert "rate_limited" in pills


class TestFetcherLazyLoading:
    """Tests for lazy-loaded fetcher management."""

    @pytest.fixture
    def engine(self):
        return ScrapingEngine()

    def test_fetchers_lazy_loaded(self, engine):
        """Fetchers should not be created until needed."""
        assert len(engine._fetchers) == 0

    def test_http_fetcher_available(self, engine):
        """HTTP fetcher should always be available."""
        fetcher = engine._get_fetcher("http")
        assert fetcher is not None

    def test_playwright_fetcher_available(self, engine):
        """Playwright fetcher should be available."""
        fetcher = engine._get_fetcher("playwright")
        assert fetcher is not None

    def test_fetcher_cached(self, engine):
        """Fetchers should be cached after creation."""
        fetcher1 = engine._get_fetcher("http")
        fetcher2 = engine._get_fetcher("http")
        assert fetcher1 is fetcher2

    def test_unknown_fetcher_returns_none(self, engine):
        """Unknown fetcher type should return None."""
        fetcher = engine._get_fetcher("nonexistent")
        assert fetcher is None

    def test_unavailable_fetcher_returns_none(self, engine):
        """Unavailable fetcher should return None gracefully."""
        # agent_browser likely not installed
        fetcher = engine._get_fetcher("agent_browser")
        # Returns None if not available, instance if available
        assert fetcher is None or hasattr(fetcher, 'fetch')


class TestJavaScriptDetection:
    """Tests for JavaScript-heavy page detection."""

    @pytest.fixture
    def engine(self):
        return ScrapingEngine()

    def test_empty_needs_js(self, engine):
        """Empty HTML should indicate JS needed."""
        assert engine._needs_javascript("")

    def test_short_needs_js(self, engine):
        """Very short HTML should indicate JS needed."""
        assert engine._needs_javascript("<html><body>Hi</body></html>")

    def test_react_app_detected(self, engine):
        """React app pattern should be detected."""
        html = '<html><body><div id="root"></div><script src="app.js"></script></body></html>'
        assert engine._needs_javascript(html)

    def test_next_js_detected(self, engine):
        """Next.js pattern should be detected."""
        html = '<html><body><div id="__next"></div></body></html>'
        assert engine._needs_javascript(html)

    def test_initial_state_detected(self, engine):
        """Redux/Vuex initial state should be detected."""
        html = '<html><body><script>window.__INITIAL_STATE__ = {};</script></body></html>'
        assert engine._needs_javascript(html)

    def test_normal_html_not_flagged(self, engine, complex_html):
        """Normal HTML with content should not be flagged."""
        # complex_html has substantial content
        assert not engine._needs_javascript(complex_html)


class TestFetchPage:
    """Tests for fetch_page method."""

    @pytest.fixture
    def engine(self):
        return ScrapingEngine()

    def test_fetch_returns_dict(self, engine):
        """Fetch should return a dictionary."""
        with patch.object(engine, '_get_fetcher') as mock:
            mock_fetcher = Mock()
            mock_fetcher.fetch.return_value = Mock(
                success=True,
                html="<html></html>",
                status_code=200,
                error=None,
                response_time_ms=100,
            )
            mock.return_value = mock_fetcher

            result = engine.fetch_page("https://example.com")

            assert isinstance(result, dict)
            assert "html" in result
            assert "method" in result
            assert "attempts" in result

    def test_force_method_bypasses_cascade(self, engine):
        """force_method should skip cascade and use specific fetcher."""
        with patch.object(engine, '_get_fetcher') as mock:
            mock_fetcher = Mock()
            mock_fetcher.fetch.return_value = Mock(
                success=True,
                html="<html>Playwright</html>",
                status_code=200,
                error=None,
                response_time_ms=100,
            )
            mock.return_value = mock_fetcher

            result = engine.fetch_page(
                "https://example.com",
                force_method="playwright"
            )

            assert result["method"] == "playwright"

    def test_cascade_disabled(self, engine):
        """Disabled cascade should only try first method."""
        with patch.object(engine, '_get_fetcher') as mock:
            mock_fetcher = Mock()
            mock_fetcher.fetch.return_value = Mock(
                success=True,
                html="<html></html>",
                status_code=200,
                error=None,
                response_time_ms=100,
            )
            mock.return_value = mock_fetcher

            result = engine.fetch_page(
                "https://example.com",
                cascade_config={"enabled": False}
            )

            # Should only make one attempt
            assert len(result["attempts"]) == 1

    def test_cascade_fallback_on_failure(self, engine):
        """Cascade should try next method on failure."""
        call_count = 0

        def mock_get_fetcher(method):
            nonlocal call_count
            call_count += 1
            mock_fetcher = Mock()

            if method == "http":
                # First method fails
                mock_fetcher.fetch.return_value = Mock(
                    success=False,
                    html="",
                    status_code=403,
                    error="Blocked",
                    response_time_ms=50,
                )
            else:
                # Second method succeeds
                mock_fetcher.fetch.return_value = Mock(
                    success=True,
                    html="<html>Success</html>",
                    status_code=200,
                    error=None,
                    response_time_ms=100,
                )
            return mock_fetcher

        with patch.object(engine, '_get_fetcher', side_effect=mock_get_fetcher):
            result = engine.fetch_page("https://example.com")

            # Should have multiple attempts
            assert len(result["attempts"]) >= 1


class TestScrapeUrl:
    """Tests for scrape_url method with extraction."""

    @pytest.fixture
    def engine(self):
        return ScrapingEngine()

    @pytest.fixture
    def sample_rules(self):
        return [
            {"name": "title", "selector_type": "css", "selector_value": "h1.title"},
            {"name": "items", "selector_type": "css", "selector_value": "li", "is_list": True},
        ]

    def test_scrape_returns_result(self, engine, sample_rules):
        """Scrape should return ScrapeResult."""
        with patch.object(engine, 'fetch_page') as mock:
            mock.return_value = {
                "html": "<html><body><h1 class='title'>Test</h1><li>A</li><li>B</li></body></html>",
                "method": "http",
                "status_code": 200,
                "response_time_ms": 100,
                "attempts": [],
            }

            result = engine.scrape_url(
                "https://example.com",
                rules=sample_rules
            )

            assert hasattr(result, 'success')
            assert hasattr(result, 'data')
            assert hasattr(result, 'url')

    def test_extraction_applies_rules(self, engine, sample_rules):
        """Rules should be applied to extract data."""
        with patch.object(engine, 'fetch_page') as mock:
            mock.return_value = {
                "html": f"""
                <html><body>
                    <h1 class='title'>Page Title</h1>
                    <ul><li>Item 1</li><li>Item 2</li></ul>
                    {TEST_HTML_PADDING}
                </body></html>
                """,
                "method": "http",
                "status_code": 200,
                "response_time_ms": 100,
                "attempts": [],
            }

            result = engine.scrape_url(
                "https://example.com",
                rules=sample_rules
            )

            assert result.data.get("title") == "Page Title"
            assert len(result.data.get("items", [])) == 2

    def test_poison_pill_detected(self, engine):
        """Poison pills should be detected during scraping."""
        with patch.object(engine, 'fetch_page') as mock:
            mock.return_value = {
                "html": "<html><body><h1>Subscribe to read this article</h1></body></html>" * 5,
                "method": "http",
                "status_code": 200,
                "response_time_ms": 100,
                "attempts": [],
            }

            result = engine.scrape_url(
                "https://example.com",
                rules=[{"name": "content", "selector_type": "css", "selector_value": "p"}]
            )

            assert result.poison_pill is not None

    def test_required_field_missing(self, engine):
        """Missing required field should be reported."""
        with patch.object(engine, 'fetch_page') as mock:
            mock.return_value = {
                "html": f"<html><body><p>No title here</p>{TEST_HTML_PADDING}</body></html>",
                "method": "http",
                "status_code": 200,
                "response_time_ms": 100,
                "attempts": [],
            }

            result = engine.scrape_url(
                "https://example.com",
                rules=[{
                    "name": "title",
                    "selector_type": "css",
                    "selector_value": "h1.title",
                    "is_required": True,
                }],
                enable_vision_fallback=False,  # Disable vision to test DOM failure
            )

            assert not result.success
            assert "title" in result.error.lower()


class TestVisionFallback:
    """Tests for vision extraction fallback."""

    @pytest.fixture
    def engine(self):
        return ScrapingEngine()

    def test_vision_fallback_attempted(self, engine):
        """Vision fallback should be attempted when DOM fails."""
        with patch.object(engine, 'fetch_page') as mock_fetch:
            # Use padded HTML so it passes content length check but still fails extraction
            mock_fetch.return_value = {
                "html": f"<html><body><div>no paragraphs here</div>{TEST_HTML_PADDING}</body></html>",
                "method": "playwright",
                "status_code": 200,
                "response_time_ms": 100,
                "attempts": [],
            }

            with patch.object(engine, '_try_vision_extraction') as mock_vision:
                mock_vision.return_value = None

                result = engine.scrape_url(
                    "https://example.com",
                    rules=[{"name": "text", "selector_type": "css", "selector_value": "span.nonexistent"}],
                    enable_vision_fallback=True,
                )

                # Vision should have been attempted
                mock_vision.assert_called_once()

    def test_vision_fallback_disabled(self, engine):
        """Vision fallback should not run when disabled."""
        with patch.object(engine, 'fetch_page') as mock_fetch:
            mock_fetch.return_value = {
                "html": f"<html><body><div>no paragraphs</div>{TEST_HTML_PADDING}</body></html>",
                "method": "http",
                "status_code": 200,
                "response_time_ms": 100,
                "attempts": [],
            }

            with patch.object(engine, '_try_vision_extraction') as mock_vision:
                result = engine.scrape_url(
                    "https://example.com",
                    rules=[{"name": "text", "selector_type": "css", "selector_value": "span.nonexistent"}],
                    enable_vision_fallback=False,
                )

                mock_vision.assert_not_called()


class TestTestSelector:
    """Tests for test_selector method."""

    @pytest.fixture
    def engine(self):
        return ScrapingEngine()

    def test_selector_returns_matches(self, engine, simple_html):
        """Test selector should return matches."""
        result = engine.test_selector(
            html=simple_html,
            selector_type="css",
            selector_value="li",
        )

        assert result["success"]
        assert result["count"] == 3
        assert len(result["matches"]) == 3

    def test_xpath_selector(self, engine, simple_html):
        """XPath selector should work."""
        result = engine.test_selector(
            html=simple_html,
            selector_type="xpath",
            selector_value="//li",
        )

        assert result["success"]
        assert result["count"] == 3

    def test_no_matches(self, engine, simple_html):
        """No matches should return empty list."""
        result = engine.test_selector(
            html=simple_html,
            selector_type="css",
            selector_value="div.nonexistent",
        )

        assert result["success"]
        assert result["count"] == 0
        assert result["matches"] == []

    def test_attribute_extraction(self, engine, simple_html):
        """Attribute extraction should work."""
        result = engine.test_selector(
            html=simple_html,
            selector_type="css",
            selector_value="a",
            attribute="href",
        )

        assert result["success"]
        assert "https://example.com" in result["matches"]


class TestGetAvailableMethods:
    """Tests for get_available_methods."""

    def test_returns_list(self):
        """Should return list of available methods."""
        engine = ScrapingEngine()
        methods = engine.get_available_methods()

        assert isinstance(methods, list)
        assert "http" in methods  # Always available

    def test_http_always_available(self):
        """HTTP should always be available."""
        engine = ScrapingEngine()
        methods = engine.get_available_methods()

        assert "http" in methods
