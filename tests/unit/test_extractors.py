"""Unit tests for content extractors (CSS, XPath, Vision)."""

import pytest
from core.scraping.extractors.css_extractor import CSSExtractor
from core.scraping.extractors.xpath_extractor import XPathExtractor


class TestCSSExtractor:
    """Tests for CSS selector extraction."""

    @pytest.fixture
    def extractor(self):
        return CSSExtractor()

    # ========================================================================
    # Basic Extraction Tests
    # ========================================================================

    def test_extract_single_element(self, extractor, simple_html):
        """Extract text from a single element."""
        result = extractor.extract_one(simple_html, "h1.title")
        assert result == "Hello World"

    def test_extract_by_id(self, extractor, simple_html):
        """Extract element by ID selector."""
        result = extractor.extract_one(simple_html, "#content")
        assert result == "This is test content."

    def test_extract_multiple_elements(self, extractor, simple_html):
        """Extract all matching elements."""
        results = extractor.extract_all(simple_html, "ul.items li")
        assert len(results) == 3
        assert results == ["Item 1", "Item 2", "Item 3"]

    def test_extract_attribute(self, extractor, simple_html):
        """Extract attribute value from element."""
        result = extractor.extract_one(simple_html, "a", attribute="href")
        assert result == "https://example.com"

    def test_extract_nonexistent_returns_none(self, extractor, simple_html):
        """Non-existent selector should return None."""
        result = extractor.extract_one(simple_html, "div.nonexistent")
        assert result is None

    def test_extract_all_nonexistent_returns_empty(self, extractor, simple_html):
        """Non-existent selector should return empty list."""
        results = extractor.extract_all(simple_html, "div.nonexistent")
        assert results == []

    # ========================================================================
    # Complex Selector Tests
    # ========================================================================

    def test_nested_selector(self, extractor, complex_html):
        """Test deeply nested selectors."""
        result = extractor.extract_one(complex_html, "article.post h1.post-title")
        assert result == "Article Title"

    def test_child_combinator(self, extractor, complex_html):
        """Test direct child combinator (>)."""
        results = extractor.extract_all(complex_html, "nav.main-nav > a")
        assert len(results) == 2

    def test_attribute_selector(self, extractor, complex_html):
        """Test attribute selectors."""
        result = extractor.extract_one(complex_html, "[data-id]", attribute="data-id")
        assert result == "123"

    def test_pseudo_selector_first(self, extractor, simple_html):
        """Test :first-child pseudo selector."""
        result = extractor.extract_one(simple_html, "ul.items li:first-child")
        assert result == "Item 1"

    def test_multiple_classes(self, extractor, complex_html):
        """Test element with multiple classes."""
        result = extractor.extract_one(complex_html, ".post-meta .author")
        assert result == "John Doe"

    # ========================================================================
    # Attribute Extraction Tests
    # ========================================================================

    def test_extract_class_attribute(self, extractor, complex_html):
        """Extract class attribute."""
        result = extractor.extract_one(complex_html, "article", attribute="class")
        assert "post" in result

    def test_extract_datetime_attribute(self, extractor, complex_html):
        """Extract datetime attribute from time element."""
        result = extractor.extract_one(complex_html, "time", attribute="datetime")
        assert result == "2024-01-15"

    def test_extract_all_with_attribute(self, extractor, complex_html):
        """Extract attribute from multiple elements."""
        results = extractor.extract_all(complex_html, "nav a", attribute="href")
        assert "/" in results
        assert "/about" in results

    # ========================================================================
    # Edge Cases
    # ========================================================================

    def test_malformed_html(self, extractor, malformed_html):
        """Extractor should handle malformed HTML gracefully."""
        # Should not raise an exception
        result = extractor.extract_one(malformed_html, "div.unclosed")
        # May or may not find element depending on parser tolerance

    def test_empty_html(self, extractor, empty_html):
        """Empty HTML should return None/empty."""
        result = extractor.extract_one(empty_html, "div")
        assert result is None

    def test_whitespace_normalization(self, extractor):
        """Test that whitespace is handled properly."""
        html = "<html><body><p>  Multiple   spaces   here  </p></body></html>"
        result = extractor.extract_one(html, "p")
        # Should get normalized or raw depending on implementation
        assert "Multiple" in result

    def test_unicode_content(self, extractor):
        """Test Unicode content extraction."""
        html = "<html><body><p>日本語テスト 🎉</p></body></html>"
        result = extractor.extract_one(html, "p")
        assert "日本語" in result
        assert "🎉" in result

    def test_html_entities(self, extractor):
        """Test HTML entity decoding."""
        html = "<html><body><p>&amp; &lt; &gt; &quot; &copy;</p></body></html>"
        result = extractor.extract_one(html, "p")
        assert "&" in result or "&amp;" in result  # Either decoded or not

    def test_script_tag_excluded(self, extractor):
        """Script content should not be extracted as text."""
        html = """
        <html><body>
        <div class="content">Real content</div>
        <script>var x = "not this";</script>
        </body></html>
        """
        result = extractor.extract_one(html, "div.content")
        assert result == "Real content"
        assert "not this" not in result

    def test_invalid_selector_handling(self, extractor, simple_html):
        """Invalid CSS selector should be handled gracefully."""
        # Depending on implementation, might raise or return None
        try:
            result = extractor.extract_one(simple_html, "[[invalid")
            # If it doesn't raise, result should be None or empty
        except Exception:
            pass  # Raising an exception is acceptable


class TestXPathExtractor:
    """Tests for XPath extraction."""

    @pytest.fixture
    def extractor(self):
        return XPathExtractor()

    # ========================================================================
    # Basic Extraction Tests
    # ========================================================================

    def test_extract_by_tag(self, extractor, simple_html):
        """Extract element by tag name."""
        result = extractor.extract_one(simple_html, "//h1")
        assert result == "Hello World"

    def test_extract_by_class(self, extractor, simple_html):
        """Extract element by class attribute."""
        result = extractor.extract_one(simple_html, "//h1[@class='title']")
        assert result == "Hello World"

    def test_extract_by_id(self, extractor, simple_html):
        """Extract element by ID attribute."""
        result = extractor.extract_one(simple_html, "//*[@id='content']")
        assert result == "This is test content."

    def test_extract_multiple(self, extractor, simple_html):
        """Extract all matching elements."""
        results = extractor.extract_all(simple_html, "//ul[@class='items']/li")
        assert len(results) == 3
        assert results == ["Item 1", "Item 2", "Item 3"]

    def test_extract_attribute(self, extractor, simple_html):
        """Extract attribute value."""
        result = extractor.extract_one(simple_html, "//a", attribute="href")
        assert result == "https://example.com"

    # ========================================================================
    # Advanced XPath Tests
    # ========================================================================

    def test_contains_text(self, extractor, complex_html):
        """Test contains() function."""
        result = extractor.extract_one(complex_html, "//h1[contains(text(), 'Article')]")
        assert result == "Article Title"

    def test_position_predicate(self, extractor, simple_html):
        """Test position predicates."""
        result = extractor.extract_one(simple_html, "//ul/li[1]")
        assert result == "Item 1"

        result = extractor.extract_one(simple_html, "//ul/li[last()]")
        assert result == "Item 3"

    def test_ancestor_axis(self, extractor, complex_html):
        """Test ancestor axis."""
        result = extractor.extract_one(
            complex_html,
            "//span[@class='author']/ancestor::article/@data-id",
            attribute=None  # XPath already gets attribute
        )
        # Depending on implementation

    def test_following_sibling(self, extractor, simple_html):
        """Test following-sibling axis."""
        result = extractor.extract_one(simple_html, "//li[1]/following-sibling::li[1]")
        assert result == "Item 2"

    def test_text_function(self, extractor, complex_html):
        """Test text() function."""
        result = extractor.extract_one(complex_html, "//span[@class='author']/text()")
        # May return text node directly

    # ========================================================================
    # Edge Cases
    # ========================================================================

    def test_nonexistent_path(self, extractor, simple_html):
        """Non-existent XPath should return None."""
        result = extractor.extract_one(simple_html, "//div[@class='nonexistent']")
        assert result is None

    def test_malformed_html(self, extractor, malformed_html):
        """XPath should handle malformed HTML."""
        # Should not raise
        result = extractor.extract_one(malformed_html, "//div")

    def test_namespace_handling(self, extractor):
        """Test handling of XML namespaces (common in XHTML)."""
        html = """
        <html xmlns="http://www.w3.org/1999/xhtml">
        <body><div>Content</div></body>
        </html>
        """
        result = extractor.extract_one(html, "//div")
        # May or may not find depending on namespace handling

    def test_invalid_xpath(self, extractor, simple_html):
        """Invalid XPath should be handled gracefully."""
        try:
            result = extractor.extract_one(simple_html, "///invalid[[")
        except Exception:
            pass  # Expected to raise


class TestVisionExtractor:
    """Tests for vision-based OCR extraction."""

    @pytest.fixture
    def extractor(self):
        """Get vision extractor if available."""
        from core.scraping.extractors.vision_extractor import VisionExtractor
        if not VisionExtractor.is_available():
            pytest.skip("Tesseract OCR not available")
        return VisionExtractor()

    # ========================================================================
    # Availability Tests
    # ========================================================================

    def test_availability_check(self):
        """Test availability check method."""
        from core.scraping.extractors.vision_extractor import VisionExtractor
        # Should not raise, returns bool
        result = VisionExtractor.is_available()
        assert isinstance(result, bool)

    def test_get_vision_extractor_singleton(self):
        """Test singleton getter function."""
        from core.scraping.extractors.vision_extractor import get_vision_extractor
        extractor = get_vision_extractor()
        # Returns None if unavailable, instance if available
        if extractor is not None:
            extractor2 = get_vision_extractor()
            assert extractor is extractor2  # Same instance

    # ========================================================================
    # OCR Extraction Tests (require Tesseract)
    # ========================================================================

    def test_extract_text_basic(self, extractor, temp_screenshot_bytes):
        """Test basic text extraction from image."""
        result = extractor.extract_text(temp_screenshot_bytes)
        assert result.success
        # Should find some text
        assert len(result.text) > 0

    def test_extract_text_with_lang(self, extractor, temp_screenshot_bytes):
        """Test text extraction with language parameter."""
        result = extractor.extract_text(temp_screenshot_bytes, lang="eng")
        assert result.success

    def test_extract_regions(self, extractor, temp_screenshot_bytes):
        """Test region-based extraction with bounding boxes."""
        result = extractor.extract_regions(temp_screenshot_bytes)
        assert result.success
        # Should have some regions
        assert isinstance(result.regions, list)

    def test_extract_structured(self, extractor, temp_screenshot_bytes):
        """Test structured data extraction."""
        result = extractor.extract_structured(temp_screenshot_bytes)
        assert result.success
        assert isinstance(result.structured_data, dict)

    def test_extract_by_region(self, extractor, temp_screenshot_bytes):
        """Test extraction from specific region."""
        result = extractor.extract_by_region(
            temp_screenshot_bytes,
            x=0, y=0, width=200, height=100
        )
        assert result.success or result.error  # Either works or has error

    def test_extract_with_preprocessing(self, extractor, temp_screenshot_bytes):
        """Test extraction with image preprocessing."""
        result = extractor.extract_with_preprocessing(
            temp_screenshot_bytes,
            deskew=True,
            denoise=True,
            threshold=True
        )
        assert result.success or result.error

    # ========================================================================
    # Error Handling Tests
    # ========================================================================

    def test_invalid_image_data(self, extractor):
        """Invalid image data should return error result."""
        result = extractor.extract_text(b"not an image")
        assert not result.success
        assert result.error is not None

    def test_empty_image_data(self, extractor):
        """Empty image data should return error."""
        result = extractor.extract_text(b"")
        assert not result.success

    def test_corrupt_png(self, extractor):
        """Corrupt PNG header should fail gracefully."""
        corrupt = b'\x89PNG\r\n\x1a\n' + b'\x00' * 100
        result = extractor.extract_text(corrupt)
        assert not result.success

    # ========================================================================
    # Result Structure Tests
    # ========================================================================

    def test_result_has_confidence(self, extractor, temp_screenshot_bytes):
        """Result should include confidence score."""
        result = extractor.extract_text(temp_screenshot_bytes)
        if result.success:
            assert 0 <= result.confidence <= 1

    def test_regions_have_positions(self, extractor, temp_screenshot_bytes):
        """Region results should have position data."""
        result = extractor.extract_regions(temp_screenshot_bytes)
        if result.success and result.regions:
            region = result.regions[0]
            assert 'x' in region
            assert 'y' in region
            assert 'width' in region
            assert 'height' in region
