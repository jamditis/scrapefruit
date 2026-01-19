"""
Integration scenario tests combining multiple components.
"""

import pytest


class TestIntegrationScenarios:
    """Tests for end-to-end scraping scenarios."""

    @pytest.fixture
    def engine(self):
        from core.scraping.engine import ScrapingEngine
        return ScrapingEngine()

    @pytest.fixture
    def detector(self):
        from core.poison_pills.detector import PoisonPillDetector
        return PoisonPillDetector()

    @pytest.fixture
    def css_extractor(self):
        from core.scraping.extractors.css_extractor import CSSExtractor
        return CSSExtractor()

    # Engine test_selector method
    def test_engine_css_selector(self, engine):
        """Test engine CSS selector testing."""
        html = "<html><body><p>Test 1</p><p>Test 2</p></body></html>"
        result = engine.test_selector(html, "css", "p")
        assert result["success"]
        assert result["count"] == 2

    def test_engine_xpath_selector(self, engine):
        """Test engine XPath selector testing."""
        html = "<html><body><p>Test</p></body></html>"
        result = engine.test_selector(html, "xpath", "//p")
        assert result["success"]
        assert result["count"] == 1

    def test_engine_invalid_selector(self, engine):
        """Test engine with invalid selector - returns success=True but count=0."""
        html = "<html><body><p>Test</p></body></html>"
        result = engine.test_selector(html, "css", "[[invalid")
        # Engine returns success=True even for invalid selectors, but with no matches
        assert result["count"] == 0

    def test_engine_available_methods(self, engine):
        """Test getting available methods."""
        methods = engine.get_available_methods()
        assert isinstance(methods, list)
        assert "http" in methods  # HTTP should always be available

    # Combined extraction and detection
    def test_extraction_then_detection(self, css_extractor, detector):
        """Test extraction followed by detection on same content."""
        html = """
        <html><body>
        <article>
            <h1>Article Title</h1>
            <p>This is a long article with substantial content that talks about
            many interesting topics and provides valuable information to readers.
            The content continues with more details and explanations that help
            illustrate the main points being discussed in this piece. We need
            to include enough words and characters to pass the minimum content
            length requirements of five hundred characters and fifty words.</p>
        </article>
        </body></html>
        """
        # First extract
        title = css_extractor.extract_one(html, "h1")
        content = css_extractor.extract_one(html, "p")

        assert title == "Article Title"
        assert "substantial content" in content

        # Then detect
        result = detector.detect(html)
        assert not result.is_poison

    def test_detection_on_clean_article(self, detector):
        """Test detection on clean article content."""
        html = """
        <html><body>
        <article class="post">
            <h1>The Future of Technology</h1>
            <p class="byline">By John Doe | January 15, 2024</p>
            <div class="content">
                <p>Technology continues to evolve at a rapid pace, transforming
                how we live, work, and communicate with each other. From artificial
                intelligence to renewable energy, innovation touches every aspect
                of modern life.</p>
                <p>In this article, we explore the latest trends and developments
                that are shaping our digital future. We'll look at emerging technologies,
                their potential applications, and what they mean for businesses and
                consumers alike.</p>
                <p>The pace of change shows no signs of slowing down. Companies that
                embrace new technologies will be better positioned to succeed in an
                increasingly competitive global marketplace.</p>
            </div>
        </article>
        </body></html>
        """
        result = detector.detect(html)
        assert not result.is_poison

    def test_detection_on_paywall_article(self, detector):
        """Test detection on paywalled article."""
        html = """
        <html><body>
        <article class="post">
            <h1>Exclusive Report</h1>
            <div class="paywall">
                <p>Subscribe to read this premium content. Get unlimited access
                to all our articles and analysis.</p>
            </div>
        """ + (" word " * 100) + """
        </article>
        </body></html>
        """
        result = detector.detect(html)
        assert result.is_poison
        assert result.pill_type == "paywall_detected"

    # Data extraction scenarios
    @pytest.mark.parametrize("selector_type,selector,expected", [
        ("css", "h1", "Title"),
        ("css", ".price", "$99"),
        ("css", "[data-id]", "Content"),
        ("xpath", "//h1", "Title"),
        ("xpath", "//span[@class='price']", "$99"),
    ])
    def test_selector_types(self, engine, selector_type, selector, expected):
        """Test different selector types."""
        html = """
        <html><body>
        <h1>Title</h1>
        <span class="price">$99</span>
        <div data-id="123">Content</div>
        </body></html>
        """
        result = engine.test_selector(html, selector_type, selector)
        assert result["success"]
        assert any(expected in str(m) for m in result["matches"])


class TestResultDataclasses:
    """Tests for result dataclass structures."""

    def test_scrape_result_creation(self):
        """Test ScrapeResult dataclass creation."""
        from core.scraping.engine import ScrapeResult

        result = ScrapeResult(
            success=True,
            url="https://example.com",
            method="http",
            data={"title": "Test"},
            html="<html></html>",
        )
        assert result.success
        assert result.url == "https://example.com"
        assert result.data["title"] == "Test"

    def test_scrape_result_default_values(self):
        """Test ScrapeResult default values."""
        from core.scraping.engine import ScrapeResult

        result = ScrapeResult(
            success=False,
            url="https://example.com",
        )
        assert result.method == ""
        assert result.error is None
        assert result.cascade_attempts == []
        assert result.screenshot is None

    def test_poison_pill_result_clean(self):
        """Test PoisonPillResult clean factory."""
        from core.poison_pills.types import PoisonPillResult

        result = PoisonPillResult.clean()
        assert not result.is_poison
        assert result.pill_type is None

    def test_poison_pill_result_detected(self):
        """Test PoisonPillResult detected factory."""
        from core.poison_pills.types import PoisonPillResult, PoisonPillType

        result = PoisonPillResult.detected(
            PoisonPillType.PAYWALL_DETECTED,
            severity="high",
            message="Test message",
        )
        assert result.is_poison
        assert result.pill_type == "paywall_detected"
        assert result.severity == "high"
        assert result.details["message"] == "Test message"


class TestExtractionIntegration:
    """Integration tests for extraction components."""

    @pytest.fixture
    def css_extractor(self):
        from core.scraping.extractors.css_extractor import CSSExtractor
        return CSSExtractor()

    @pytest.fixture
    def xpath_extractor(self):
        from core.scraping.extractors.xpath_extractor import XPathExtractor
        return XPathExtractor()

    def test_css_and_xpath_same_result(self, css_extractor, xpath_extractor):
        """Test that CSS and XPath produce same results."""
        html = "<html><body><p class='test'>Content</p></body></html>"

        css_result = css_extractor.extract_one(html, ".test")
        xpath_result = xpath_extractor.extract_one(html, "//p[@class='test']")

        assert css_result == xpath_result == "Content"

    def test_extract_complex_structure(self, css_extractor):
        """Test extracting data from complex HTML structure."""
        html = """
        <html><body>
        <div class="product">
            <h2 class="name">Product Name</h2>
            <span class="price" data-value="99.99">$99.99</span>
            <div class="description">
                <p>Short description here.</p>
                <ul class="features">
                    <li>Feature 1</li>
                    <li>Feature 2</li>
                    <li>Feature 3</li>
                </ul>
            </div>
        </div>
        </body></html>
        """
        # Extract multiple data points
        name = css_extractor.extract_one(html, ".name")
        price_text = css_extractor.extract_one(html, ".price")
        price_value = css_extractor.extract_one(html, ".price", attribute="data-value")
        features = css_extractor.extract_all(html, ".features li")

        assert name == "Product Name"
        assert "$99.99" in price_text
        assert price_value == "99.99"
        assert len(features) == 3
        assert "Feature 1" in features

    def test_extract_table_data(self, css_extractor):
        """Test extracting data from table structure."""
        html = """
        <html><body>
        <table>
            <tr><th>Name</th><th>Price</th></tr>
            <tr><td>Item A</td><td>$10</td></tr>
            <tr><td>Item B</td><td>$20</td></tr>
        </table>
        </body></html>
        """
        headers = css_extractor.extract_all(html, "th")
        names = css_extractor.extract_all(html, "tr td:first-child")
        prices = css_extractor.extract_all(html, "tr td:last-child")

        assert headers == ["Name", "Price"]
        assert names == ["Item A", "Item B"]
        assert prices == ["$10", "$20"]


# ============================================================================
# ADDITIONAL INTEGRATION SCENARIOS
# 30+ more tests for comprehensive coverage
# ============================================================================

class TestDetectorExtractorIntegration:
    """Tests combining poison pill detection with extraction."""

    @pytest.fixture
    def detector(self):
        from core.poison_pills.detector import PoisonPillDetector
        return PoisonPillDetector()

    @pytest.fixture
    def css_extractor(self):
        from core.scraping.extractors.css_extractor import CSSExtractor
        return CSSExtractor()

    @pytest.fixture
    def xpath_extractor(self):
        from core.scraping.extractors.xpath_extractor import XPathExtractor
        return XPathExtractor()

    def test_detect_then_extract_clean_content(self, detector, css_extractor):
        """Detect clean content then extract data."""
        html = """
        <html><body>
        <article>
            <h1>News Article Title</h1>
            <p class="author">By Jane Reporter</p>
            <div class="content">
                <p>This is a comprehensive news article covering important events
                that occurred recently. The article provides detailed information
                and analysis of the situation, including quotes from experts and
                relevant background context.</p>
                <p>Additional paragraphs continue to provide more information
                about the topic, ensuring readers have a complete understanding
                of the events being reported.</p>
            </div>
        </article>
        </body></html>
        """
        # First check for poison pills
        detection = detector.detect(html)
        assert not detection.is_poison

        # Then extract data
        title = css_extractor.extract_one(html, "h1")
        author = css_extractor.extract_one(html, ".author")
        content = css_extractor.extract_all(html, ".content p")

        assert title == "News Article Title"
        assert "Jane Reporter" in author
        assert len(content) == 2

    def test_skip_extraction_on_poison(self, detector, css_extractor):
        """When poison is detected, extraction might be skipped or handled differently."""
        html = """
        <html><body>
        <div class="paywall">
            <h1>Premium Content</h1>
            <p>Subscribe to read this article. Members only access.</p>
        </div>
        """ + (" padding word " * 50) + """
        </body></html>
        """
        detection = detector.detect(html)
        assert detection.is_poison
        assert detection.pill_type == "paywall_detected"

        # Even though poisoned, we can still extract what's visible
        title = css_extractor.extract_one(html, "h1")
        assert title == "Premium Content"

    @pytest.mark.parametrize("poison_html,expected_types", [
        ('<h1>Error 429</h1><p>Too many requests - rate limit exceeded quota throttled. ' + 'word ' * 90 + '</p>', ["rate_limited"]),
        ('<div class="g-recaptcha">Complete captcha challenge verify human</div><p>Content here ' + 'word ' * 90 + '</p>', ["captcha", "anti_bot"]),  # "captcha" in ANTI_BOT_PATTERNS
        ('<h1>Access Denied</h1><p>Cloudflare protection active. ' + 'word ' * 90 + '</p>', ["anti_bot"]),
        ('<h1>Page Not Found</h1><p>404 error page not found. ' + 'word ' * 90 + '</p>', ["dead_link"]),
    ])
    def test_detect_various_poison_types(self, detector, poison_html, expected_types):
        """Test detection of various poison pill types."""
        html = f"<html><body>{poison_html}</body></html>"
        result = detector.detect(html)
        assert result.is_poison
        assert result.pill_type in expected_types


class TestEngineIntegration:
    """Tests for scraping engine integration."""

    @pytest.fixture
    def engine(self):
        from core.scraping.engine import ScrapingEngine
        return ScrapingEngine()

    def test_engine_test_selector_with_attribute(self, engine):
        """Test engine selector testing with attribute extraction."""
        html = """
        <html><body>
        <a href="/link1">Link 1</a>
        <a href="/link2">Link 2</a>
        </body></html>
        """
        result = engine.test_selector(html, "css", "a", attribute="href")
        assert result["success"]
        assert "/link1" in result["matches"]
        assert "/link2" in result["matches"]

    def test_engine_test_xpath_with_attribute(self, engine):
        """Test engine XPath selector with attribute extraction."""
        html = """
        <html><body>
        <img src="/img1.jpg" alt="Image 1">
        <img src="/img2.jpg" alt="Image 2">
        </body></html>
        """
        result = engine.test_selector(html, "xpath", "//img/@src")
        assert result["success"]
        assert "/img1.jpg" in result["matches"]

    def test_engine_empty_results(self, engine):
        """Test engine with selector that matches nothing."""
        html = "<html><body><p>Content</p></body></html>"
        result = engine.test_selector(html, "css", ".nonexistent")
        assert result["success"]  # Operation succeeded, just no matches
        assert result["count"] == 0

    @pytest.mark.parametrize("html,selector,expected_count", [
        ("<ul><li>1</li><li>2</li><li>3</li></ul>", "li", 3),
        ("<div><p>A</p><p>B</p></div>", "p", 2),
        ("<table><tr><td>1</td><td>2</td></tr></table>", "td", 2),
        # Note: void elements like <input> have no text content, so extract_all returns []
        ("<div><span>A</span><span>B</span><span>C</span></div>", "span", 3),
    ])
    def test_engine_count_accuracy(self, engine, html, selector, expected_count):
        """Test that engine counts text matches accurately."""
        full_html = f"<html><body>{html}</body></html>"
        result = engine.test_selector(full_html, "css", selector)
        assert result["count"] == expected_count


class TestMultipleExtractorWorkflows:
    """Tests for workflows using multiple extractors."""

    @pytest.fixture
    def css_extractor(self):
        from core.scraping.extractors.css_extractor import CSSExtractor
        return CSSExtractor()

    @pytest.fixture
    def xpath_extractor(self):
        from core.scraping.extractors.xpath_extractor import XPathExtractor
        return XPathExtractor()

    @pytest.fixture
    def meta_extractor(self):
        from core.scraping.extractors.css_extractor import MetaExtractor
        return MetaExtractor()

    def test_combined_extraction_workflow(self, css_extractor, xpath_extractor, meta_extractor):
        """Test workflow using CSS, XPath, and Meta extractors together."""
        html = """
        <html>
        <head>
            <title>Product Page</title>
            <meta name="description" content="Great product for sale">
            <meta property="og:price" content="49.99">
        </head>
        <body>
        <div class="product">
            <h1>Amazing Product</h1>
            <span class="price">$49.99</span>
            <div class="specs">
                <dl>
                    <dt>Color</dt><dd>Blue</dd>
                    <dt>Size</dt><dd>Medium</dd>
                </dl>
            </div>
        </div>
        </body>
        </html>
        """
        # Use CSS for main content
        name = css_extractor.extract_one(html, ".product h1")
        price = css_extractor.extract_one(html, ".price")

        # Use XPath for specs
        spec_names = xpath_extractor.extract_all(html, "//dt")
        spec_values = xpath_extractor.extract_all(html, "//dd")

        # Use Meta for metadata
        description = meta_extractor.extract(html, "description")
        og_price = meta_extractor.extract(html, "og:price")

        assert name == "Amazing Product"
        assert "$49.99" in price
        assert spec_names == ["Color", "Size"]
        assert spec_values == ["Blue", "Medium"]
        assert description == "Great product for sale"
        assert og_price == "49.99"

    def test_fallback_extraction_css_to_xpath(self, css_extractor, xpath_extractor):
        """Test fallback from CSS to XPath when CSS fails."""
        html = """
        <html><body>
        <div data-content="special">Target content</div>
        </body></html>
        """
        # CSS might not find this easily without complex selector
        css_result = css_extractor.extract_one(html, ".not-found")

        if not css_result:
            # Fallback to XPath
            xpath_result = xpath_extractor.extract_one(html, "//div[@data-content='special']")
            assert xpath_result == "Target content"

    @pytest.mark.parametrize("html,css_sel,xpath_sel,expected", [
        ("<p class='text'>Hello</p>", ".text", "//p[@class='text']", "Hello"),
        ("<span id='unique'>World</span>", "#unique", "//span[@id='unique']", "World"),
        ("<div data-id='123'>Data</div>", "[data-id='123']", "//div[@data-id='123']", "Data"),
    ])
    def test_equivalent_selectors(self, css_extractor, xpath_extractor, html, css_sel, xpath_sel, expected):
        """Test that equivalent CSS and XPath selectors produce same results."""
        full_html = f"<html><body>{html}</body></html>"
        css_result = css_extractor.extract_one(full_html, css_sel)
        xpath_result = xpath_extractor.extract_one(full_html, xpath_sel)

        assert css_result == xpath_result == expected


class TestPoisonPillResultIntegration:
    """Tests for PoisonPillResult dataclass usage."""

    def test_result_to_dict_compatibility(self):
        """Test that result can be converted to dict for JSON serialization."""
        from core.poison_pills.types import PoisonPillResult, PoisonPillType
        from dataclasses import asdict

        result = PoisonPillResult.detected(
            PoisonPillType.RATE_LIMITED,
            severity="high",
            message="API rate limit exceeded",
            retry_possible=True,
        )

        result_dict = asdict(result)
        assert result_dict["is_poison"] is True
        assert result_dict["pill_type"] == "rate_limited"
        assert result_dict["retry_possible"] is True

    def test_all_poison_types_have_actions(self):
        """Test that all poison types have recommended actions."""
        from core.poison_pills.types import PoisonPillResult, PoisonPillType

        for pill_type in PoisonPillType:
            result = PoisonPillResult.detected(pill_type)
            assert result.recommended_action, f"No action for {pill_type.name}"

    @pytest.mark.parametrize("pill_type,expected_severity", [
        ("CONTENT_TOO_SHORT", "medium"),
        ("PAYWALL_DETECTED", "medium"),
        ("CAPTCHA", "medium"),  # Default severity
        ("DEAD_LINK", "medium"),
    ])
    def test_default_severities(self, pill_type, expected_severity):
        """Test default severity levels for poison types."""
        from core.poison_pills.types import PoisonPillResult, PoisonPillType

        result = PoisonPillResult.detected(PoisonPillType[pill_type])
        assert result.severity == expected_severity


class TestExtractionErrorHandling:
    """Tests for error handling in extraction workflows."""

    @pytest.fixture
    def css_extractor(self):
        from core.scraping.extractors.css_extractor import CSSExtractor
        return CSSExtractor()

    @pytest.fixture
    def xpath_extractor(self):
        from core.scraping.extractors.xpath_extractor import XPathExtractor
        return XPathExtractor()

    def test_graceful_handling_of_invalid_html(self, css_extractor, xpath_extractor):
        """Test graceful handling when HTML is severely malformed."""
        malformed = "<html><body><div>Not closed<p>Text"

        # Should not raise, should return something or None
        css_result = css_extractor.extract_one(malformed, "p")
        xpath_result = xpath_extractor.extract_one(malformed, "//p")

        # Both should handle gracefully
        assert css_result is None or "Text" in css_result
        assert xpath_result is None or "Text" in xpath_result

    def test_empty_html_handling(self, css_extractor, xpath_extractor):
        """Test handling of empty HTML input."""
        empty_inputs = ["", " ", "\n", "\t"]

        for empty in empty_inputs:
            css_result = css_extractor.extract_one(empty, "p")
            xpath_result = xpath_extractor.extract_one(empty, "//p")
            assert css_result is None
            assert xpath_result is None

    def test_unicode_in_selectors(self, css_extractor):
        """Test selectors with unicode characters."""
        html = """
        <html><body>
        <div class="日本語">Japanese content</div>
        <div class="中文">Chinese content</div>
        </body></html>
        """
        # Note: Class names with non-ASCII might not work in all browsers
        # but lxml should handle it
        result = css_extractor.extract_one(html, "div")
        assert result is not None


class TestBooksToScrapeIntegration:
    """Integration tests using Books to Scrape fixtures."""

    @pytest.fixture
    def css_extractor(self):
        from core.scraping.extractors.css_extractor import CSSExtractor
        return CSSExtractor()

    @pytest.fixture
    def detector(self):
        from core.poison_pills.detector import PoisonPillDetector
        return PoisonPillDetector()

    def test_full_book_extraction(self, css_extractor, detector, books_to_scrape_book, books_to_scrape_selectors):
        """Test full extraction workflow on book detail page."""
        # First verify content is clean
        detection = detector.detect(books_to_scrape_book)
        assert not detection.is_poison

        # Extract all data using predefined selectors
        selectors = books_to_scrape_selectors
        data = {
            "title": css_extractor.extract_one(books_to_scrape_book, selectors["title"]),
            "price": css_extractor.extract_one(books_to_scrape_book, selectors["price"]),
            "upc": css_extractor.extract_one(books_to_scrape_book, selectors["upc"]),
        }

        assert data["title"] == "A Light in the Attic"
        assert "£51.77" in data["price"]
        assert data["upc"] == "a897fe39b1053632"

    def test_catalog_extraction(self, css_extractor, detector, books_to_scrape_catalog, books_to_scrape_selectors):
        """Test extraction from catalog listing page."""
        detection = detector.detect(books_to_scrape_catalog)
        assert not detection.is_poison

        selectors = books_to_scrape_selectors

        # Extract multiple products
        titles = css_extractor.extract_all(books_to_scrape_catalog, selectors["book_title"], attribute="title")
        prices = css_extractor.extract_all(books_to_scrape_catalog, selectors["book_price"])
        links = css_extractor.extract_all(books_to_scrape_catalog, selectors["book_link"], attribute="href")

        assert len(titles) == 3
        assert len(prices) == 3
        assert len(links) == 3
        assert "A Light in the Attic" in titles
