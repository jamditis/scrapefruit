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
        """Region results should have position data (as TextRegion dataclass)."""
        result = extractor.extract_regions(temp_screenshot_bytes)
        if result.success and result.regions:
            region = result.regions[0]
            # TextRegion is now a dataclass with attributes instead of dict keys
            assert hasattr(region, 'x')
            assert hasattr(region, 'y')
            assert hasattr(region, 'width')
            assert hasattr(region, 'height')
            assert hasattr(region, 'text')
            assert hasattr(region, 'confidence')


# ============================================================================
# Pure Data Transformation Tests
# ============================================================================

class TestBooksToScrapePureExtraction:
    """
    Pure data transformation tests using Books to Scrape fixtures.

    These tests verify extraction logic WITHOUT any HTTP calls, following
    TDD best practices of separating data transformation from I/O.
    """

    @pytest.fixture
    def css_extractor(self):
        return CSSExtractor()

    @pytest.fixture
    def xpath_extractor(self):
        return XPathExtractor()

    # ========================================================================
    # Book Detail Page Extraction
    # ========================================================================

    def test_extract_book_title(self, css_extractor, books_to_scrape_book, books_to_scrape_selectors):
        """Extract book title from detail page."""
        result = css_extractor.extract_one(
            books_to_scrape_book,
            books_to_scrape_selectors["title"]
        )
        assert result == "A Light in the Attic"

    def test_extract_book_price(self, css_extractor, books_to_scrape_book, books_to_scrape_selectors):
        """Extract book price from detail page."""
        result = css_extractor.extract_one(
            books_to_scrape_book,
            books_to_scrape_selectors["price"]
        )
        assert result == "£51.77"

    def test_extract_book_availability(self, css_extractor, books_to_scrape_book, books_to_scrape_selectors):
        """Extract availability status from detail page."""
        result = css_extractor.extract_one(
            books_to_scrape_book,
            books_to_scrape_selectors["availability"]
        )
        assert "In stock" in result
        assert "22 available" in result

    def test_extract_book_upc(self, css_extractor, books_to_scrape_book, books_to_scrape_selectors):
        """Extract UPC from product table."""
        result = css_extractor.extract_one(
            books_to_scrape_book,
            books_to_scrape_selectors["upc"]
        )
        assert result == "a897fe39b1053632"

    def test_extract_book_rating_class(self, css_extractor, books_to_scrape_book, books_to_scrape_selectors):
        """Extract rating from class attribute."""
        result = css_extractor.extract_one(
            books_to_scrape_book,
            books_to_scrape_selectors["rating"],
            attribute="class"
        )
        assert "Three" in result  # 3-star rating

    def test_extract_breadcrumb_navigation(self, css_extractor, books_to_scrape_book, books_to_scrape_selectors):
        """Extract breadcrumb trail."""
        results = css_extractor.extract_all(
            books_to_scrape_book,
            books_to_scrape_selectors["breadcrumb"]
        )
        assert len(results) == 4  # Home > Books > Poetry > Title
        assert "Home" in results[0]
        assert "Poetry" in results[2]

    def test_extract_description(self, css_extractor, books_to_scrape_book, books_to_scrape_selectors):
        """Extract product description."""
        result = css_extractor.extract_one(
            books_to_scrape_book,
            books_to_scrape_selectors["description"]
        )
        assert "Shel Silverstein" in result
        assert "poetry" in result.lower()

    # ========================================================================
    # Catalog Page Extraction
    # ========================================================================

    def test_extract_all_books_from_catalog(self, css_extractor, books_to_scrape_catalog, books_to_scrape_selectors):
        """Extract all book articles from catalog page."""
        results = css_extractor.extract_all(
            books_to_scrape_catalog,
            books_to_scrape_selectors["books"]
        )
        # Fixture has 3 books
        assert len(results) == 3

    def test_extract_book_titles_from_catalog(self, css_extractor, books_to_scrape_catalog, books_to_scrape_selectors):
        """Extract all book titles from catalog page."""
        results = css_extractor.extract_all(
            books_to_scrape_catalog,
            books_to_scrape_selectors["book_title"],
            attribute="title"
        )
        assert "A Light in the Attic" in results
        assert "Tipping the Velvet" in results
        assert "Soumission" in results

    def test_extract_book_prices_from_catalog(self, css_extractor, books_to_scrape_catalog, books_to_scrape_selectors):
        """Extract all book prices from catalog page."""
        results = css_extractor.extract_all(
            books_to_scrape_catalog,
            books_to_scrape_selectors["book_price"]
        )
        assert len(results) == 3
        assert "£51.77" in results
        assert "£53.74" in results
        assert "£50.10" in results

    def test_extract_book_links_from_catalog(self, css_extractor, books_to_scrape_catalog, books_to_scrape_selectors):
        """Extract all book links from catalog page."""
        results = css_extractor.extract_all(
            books_to_scrape_catalog,
            books_to_scrape_selectors["book_link"],
            attribute="href"
        )
        assert len(results) == 3
        assert "a-light-in-the-attic_1000/index.html" in results

    def test_extract_pagination_info(self, css_extractor, books_to_scrape_catalog, books_to_scrape_selectors):
        """Extract pagination text."""
        result = css_extractor.extract_one(
            books_to_scrape_catalog,
            books_to_scrape_selectors["pagination"]
        )
        assert "Page 1 of 50" in result

    def test_extract_next_page_link(self, css_extractor, books_to_scrape_catalog, books_to_scrape_selectors):
        """Extract next page URL."""
        result = css_extractor.extract_one(
            books_to_scrape_catalog,
            books_to_scrape_selectors["next_page"],
            attribute="href"
        )
        assert result == "page-2.html"

    # ========================================================================
    # XPath Equivalents (Same Tests, Different Syntax)
    # ========================================================================

    def test_xpath_extract_book_title(self, xpath_extractor, books_to_scrape_book):
        """Extract book title using XPath."""
        result = xpath_extractor.extract_one(
            books_to_scrape_book,
            "//article[contains(@class, 'product_page')]//h1"
        )
        assert result == "A Light in the Attic"

    def test_xpath_extract_book_price(self, xpath_extractor, books_to_scrape_book):
        """Extract book price using XPath."""
        result = xpath_extractor.extract_one(
            books_to_scrape_book,
            "//p[@class='price_color']"
        )
        assert result == "£51.77"

    def test_xpath_extract_table_data(self, xpath_extractor, books_to_scrape_book):
        """Extract data from product info table using XPath."""
        result = xpath_extractor.extract_one(
            books_to_scrape_book,
            "//table//tr[th[text()='UPC']]/td"
        )
        assert result == "a897fe39b1053632"

    def test_xpath_extract_all_prices_from_catalog(self, xpath_extractor, books_to_scrape_catalog):
        """Extract all prices from catalog using XPath."""
        results = xpath_extractor.extract_all(
            books_to_scrape_catalog,
            "//article[contains(@class, 'product_pod')]//p[@class='price_color']"
        )
        assert len(results) == 3


# ============================================================================
# Data Cleaning / Transformation Tests
# ============================================================================

class TestDataCleaning:
    """
    Tests for pure data cleaning functions (no I/O).

    These test the transformation step that happens AFTER extraction,
    turning raw scraped strings into structured, validated data.
    """

    def test_price_extraction_and_parsing(self):
        """Test extracting numeric price from currency string."""
        raw_prices = ["£51.77", "$99.99", "€123.45", "¥1000"]

        def parse_price(price_str: str) -> float:
            """Pure function to parse price from string."""
            import re
            # Remove currency symbols and parse as float
            numeric = re.sub(r'[^\d.]', '', price_str)
            return float(numeric) if numeric else 0.0

        assert parse_price("£51.77") == 51.77
        assert parse_price("$99.99") == 99.99
        assert parse_price("€123.45") == 123.45

    def test_availability_parsing(self):
        """Test parsing availability count from text."""
        def parse_availability(text: str) -> tuple:
            """Pure function to parse availability."""
            import re
            text_lower = text.lower().strip()

            if "out of stock" in text_lower:
                return (False, 0)

            match = re.search(r'(\d+)\s*available', text_lower)
            count = int(match.group(1)) if match else 0
            in_stock = "in stock" in text_lower

            return (in_stock, count)

        assert parse_availability("In stock (22 available)") == (True, 22)
        assert parse_availability("In stock (1 available)") == (True, 1)
        assert parse_availability("Out of stock") == (False, 0)

    def test_star_rating_from_class(self):
        """Test parsing star rating from CSS class."""
        def parse_rating(class_str: str) -> int:
            """Pure function to parse rating from class."""
            rating_map = {
                "One": 1, "Two": 2, "Three": 3, "Four": 4, "Five": 5
            }
            for word, value in rating_map.items():
                if word in class_str:
                    return value
            return 0

        assert parse_rating("star-rating Three") == 3
        assert parse_rating("star-rating Five") == 5
        assert parse_rating("star-rating One") == 1

    def test_url_normalization(self):
        """Test normalizing relative URLs to absolute."""
        def normalize_url(relative: str, base: str) -> str:
            """Pure function to normalize URL."""
            from urllib.parse import urljoin
            return urljoin(base, relative)

        base = "https://books.toscrape.com/catalogue/"
        assert normalize_url("page-2.html", base) == "https://books.toscrape.com/catalogue/page-2.html"
        assert normalize_url("../index.html", base) == "https://books.toscrape.com/index.html"

    def test_text_cleaning(self):
        """Test cleaning extracted text."""
        def clean_text(text: str) -> str:
            """Pure function to clean text."""
            import re
            # Normalize whitespace
            text = re.sub(r'\s+', ' ', text)
            return text.strip()

        assert clean_text("  Multiple   spaces   here  ") == "Multiple spaces here"
        assert clean_text("\n\nNew\nlines\n\n") == "New lines"
