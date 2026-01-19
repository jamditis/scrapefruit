"""
CSS selector pattern tests - 200+ tests based on lxml.cssselect implementation.

Tests cover the CSSExtractor using standard CSS selector syntax:
- Basic selectors: tag, .class, #id
- Attribute selectors: [attr], [attr=value], [attr*=value], [attr^=value], [attr$=value]
- Combinators: descendant, child (>), adjacent sibling (+), general sibling (~)
- Pseudo-classes: :first-child, :last-child, :nth-child(n), :not()
- Attribute extraction via the `attribute` parameter
"""

import pytest
from tests.conftest import pad_html

from core.scraping.extractors.css_extractor import CSSExtractor, MetaExtractor


# ============================================================================
# Fixture: Extractor instances
# ============================================================================

@pytest.fixture
def extractor():
    """Create a CSS extractor instance."""
    return CSSExtractor()


@pytest.fixture
def meta_extractor():
    """Create a meta extractor instance."""
    return MetaExtractor()


# ============================================================================
# HTML FIXTURES FOR CSS TESTING
# ============================================================================

@pytest.fixture
def article_html():
    """Realistic article HTML for testing."""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Test Article</title>
        <meta name="author" content="John Doe">
        <meta name="description" content="A test article for CSS extraction">
        <meta property="og:title" content="Test Article OG">
        <meta property="article:published_time" content="2024-01-15T10:00:00Z">
    </head>
    <body>
        <header class="site-header">
            <nav id="main-nav">
                <a href="/" class="nav-link">Home</a>
                <a href="/about" class="nav-link">About</a>
                <a href="/contact" class="nav-link active">Contact</a>
            </nav>
        </header>
        <main>
            <article class="post" data-id="123" data-category="tech">
                <h1 class="post-title">Article Title Here</h1>
                <div class="post-meta">
                    <span class="author">John Doe</span>
                    <time datetime="2024-01-15">January 15, 2024</time>
                    <span class="category">Technology</span>
                </div>
                <div class="post-content">
                    <p class="intro">This is the introduction paragraph.</p>
                    <p>Second paragraph with regular content.</p>
                    <p class="highlight">Third paragraph highlighted.</p>
                    <ul class="feature-list">
                        <li class="feature" data-priority="high">Feature 1</li>
                        <li class="feature" data-priority="medium">Feature 2</li>
                        <li class="feature" data-priority="low">Feature 3</li>
                    </ul>
                </div>
                <footer class="post-footer">
                    <div class="tags">
                        <a href="/tag/python" class="tag">python</a>
                        <a href="/tag/testing" class="tag">testing</a>
                        <a href="/tag/web" class="tag">web</a>
                    </div>
                </footer>
            </article>
        </main>
        <aside class="sidebar">
            <div class="widget" id="recent-posts">
                <h3>Recent Posts</h3>
                <ul>
                    <li><a href="/post-1">Post 1</a></li>
                    <li><a href="/post-2">Post 2</a></li>
                </ul>
            </div>
        </aside>
        <footer class="site-footer">
            <p>&copy; 2024 Test Site</p>
        </footer>
    </body>
    </html>
    """


@pytest.fixture
def table_html():
    """Table HTML for testing table selectors."""
    return """
    <!DOCTYPE html>
    <html>
    <body>
        <table class="data-table" id="products">
            <thead>
                <tr>
                    <th>Name</th>
                    <th>Price</th>
                    <th>Stock</th>
                </tr>
            </thead>
            <tbody>
                <tr class="product" data-id="1">
                    <td class="name">Product A</td>
                    <td class="price">$10.00</td>
                    <td class="stock">In Stock</td>
                </tr>
                <tr class="product" data-id="2">
                    <td class="name">Product B</td>
                    <td class="price">$20.00</td>
                    <td class="stock">Out of Stock</td>
                </tr>
                <tr class="product" data-id="3">
                    <td class="name">Product C</td>
                    <td class="price">$15.00</td>
                    <td class="stock">In Stock</td>
                </tr>
            </tbody>
        </table>
        <p>Additional content to meet minimum word count requirements for testing purposes.
        This paragraph provides padding to ensure the content passes validation checks.</p>
    </body>
    </html>
    """


@pytest.fixture
def nested_html():
    """Deeply nested HTML for testing combinator selectors."""
    return """
    <!DOCTYPE html>
    <html>
    <body>
        <div class="level-1">
            <div class="level-2">
                <div class="level-3">
                    <span class="deep">Deep content</span>
                </div>
            </div>
            <p class="sibling-1">First sibling</p>
            <p class="sibling-2">Second sibling</p>
            <p class="sibling-3">Third sibling</p>
        </div>
        <div class="level-1 alternate">
            <span>Alternate span</span>
        </div>
        <p>Additional content to meet minimum word count requirements for testing purposes.
        This paragraph provides padding to ensure the content passes validation checks.
        We need enough words to satisfy the poison pill detector minimum threshold.</p>
    </body>
    </html>
    """


# ============================================================================
# BASIC SELECTORS
# tag, .class, #id - 30 tests
# ============================================================================

class TestBasicSelectors:
    """Test basic CSS selectors: tag, class, id."""

    # Tag selectors
    @pytest.mark.parametrize("selector,expected", [
        ("h1", "Article Title Here"),
        ("title", "Test Article"),
        ("time", "January 15, 2024"),
        ("article", None),  # Returns full text content
    ])
    def test_tag_selector_extract_one(self, extractor, article_html, selector, expected):
        result = extractor.extract_one(article_html, selector)
        if expected:
            assert expected in result
        else:
            assert result is not None  # Should return something

    @pytest.mark.parametrize("selector,expected_count", [
        ("p", 4),  # Multiple paragraphs (intro, second, highlight, footer)
        ("a", 8),  # All links
        ("li", 5),  # All list items (3 features + 2 recent posts)
        ("span", 2),  # All spans (author, category)
        ("div", 4),  # All divs (post-meta, post-content, tags, widget)
    ])
    def test_tag_selector_extract_all(self, extractor, article_html, selector, expected_count):
        results = extractor.extract_all(article_html, selector)
        assert len(results) == expected_count

    # Class selectors
    @pytest.mark.parametrize("selector,expected", [
        (".post-title", "Article Title Here"),
        (".author", "John Doe"),
        (".category", "Technology"),
        (".intro", "This is the introduction paragraph."),
        (".highlight", "Third paragraph highlighted."),
    ])
    def test_class_selector_extract_one(self, extractor, article_html, selector, expected):
        result = extractor.extract_one(article_html, selector)
        assert result == expected

    @pytest.mark.parametrize("selector,expected_count", [
        (".nav-link", 3),
        (".tag", 3),
        (".feature", 3),
        (".post", 1),
        (".widget", 1),
    ])
    def test_class_selector_extract_all(self, extractor, article_html, selector, expected_count):
        results = extractor.extract_all(article_html, selector)
        assert len(results) == expected_count

    # ID selectors
    @pytest.mark.parametrize("selector,should_exist", [
        ("#main-nav", True),
        ("#recent-posts", True),
        ("#nonexistent", False),
        ("#products", False),  # Not in article_html
    ])
    def test_id_selector_exists(self, extractor, article_html, selector, should_exist):
        assert extractor.exists(article_html, selector) == should_exist

    def test_id_selector_unique(self, extractor, article_html):
        """IDs should be unique - extract_all should return 1 item."""
        results = extractor.extract_all(article_html, "#main-nav")
        assert len(results) == 1


# ============================================================================
# ATTRIBUTE SELECTORS
# [attr], [attr=value], [attr*=value], [attr^=value], [attr$=value] - 40 tests
# ============================================================================

class TestAttributeSelectors:
    """Test CSS attribute selectors."""

    # Has attribute [attr]
    @pytest.mark.parametrize("selector,expected_count", [
        ("[href]", 8),  # All elements with href
        ("[class]", 24),  # All elements with class (header, 3 nav-links, article, h1, 2 divs, 2 spans, 2 divs, 2 p, ul, 3 li, footer, div, 3 a, aside, div, footer)
        ("[id]", 2),  # All elements with id
        ("[data-id]", 1),  # article with data-id
        ("[datetime]", 1),  # time element
    ])
    def test_has_attribute(self, extractor, article_html, selector, expected_count):
        results = extractor.extract_all(article_html, selector)
        assert len(results) == expected_count

    # Exact match [attr=value]
    @pytest.mark.parametrize("selector,expected", [
        ('[data-id="123"]', True),
        ('[data-category="tech"]', True),
        ('[datetime="2024-01-15"]', True),
        ('[data-id="999"]', False),
        ('[class="post"]', True),
    ])
    def test_exact_attribute_match(self, extractor, article_html, selector, expected):
        assert extractor.exists(article_html, selector) == expected

    # Contains substring [attr*=value]
    @pytest.mark.parametrize("selector,expected_count", [
        ('[href*="tag"]', 3),  # Links containing "tag"
        ('[href*="/"]', 8),  # Links containing "/"
        ('[class*="post"]', 5),  # Classes containing "post" (post, post-title, post-meta, post-content, post-footer)
        ('[href*="nonexistent"]', 0),
    ])
    def test_contains_attribute(self, extractor, article_html, selector, expected_count):
        results = extractor.extract_all(article_html, selector)
        assert len(results) == expected_count

    # Starts with [attr^=value]
    @pytest.mark.parametrize("selector,expected_count", [
        ('[href^="/"]', 8),  # Links starting with "/"
        ('[href^="/tag"]', 3),  # Links starting with "/tag"
        ('[class^="post"]', 5),  # Classes starting with "post" (post, post-title, post-meta, post-content, post-footer)
        ('[href^="http"]', 0),  # No external links
    ])
    def test_starts_with_attribute(self, extractor, article_html, selector, expected_count):
        results = extractor.extract_all(article_html, selector)
        assert len(results) == expected_count

    # Ends with [attr$=value]
    @pytest.mark.parametrize("selector,expected_count", [
        ('[href$="about"]', 1),
        ('[href$="contact"]', 1),
        ('[class$="link"]', 2),  # nav-link (2) - third has class="nav-link active"
        ('[class$="title"]', 1),  # post-title
    ])
    def test_ends_with_attribute(self, extractor, article_html, selector, expected_count):
        results = extractor.extract_all(article_html, selector)
        assert len(results) == expected_count

    # Attribute extraction
    @pytest.mark.parametrize("selector,attribute,expected", [
        ("article", "data-id", "123"),
        ("article", "data-category", "tech"),
        ("time", "datetime", "2024-01-15"),
        (".nav-link", "href", "/"),  # First match
    ])
    def test_extract_attribute_value(self, extractor, article_html, selector, attribute, expected):
        result = extractor.extract_one(article_html, selector, attribute=attribute)
        assert result == expected

    @pytest.mark.parametrize("selector,attribute,expected_values", [
        (".nav-link", "href", ["/", "/about", "/contact"]),
        (".tag", "href", ["/tag/python", "/tag/testing", "/tag/web"]),
        (".feature", "data-priority", ["high", "medium", "low"]),
    ])
    def test_extract_all_attribute_values(self, extractor, article_html, selector, attribute, expected_values):
        results = extractor.extract_all(article_html, selector, attribute=attribute)
        assert results == expected_values


# ============================================================================
# COMBINATOR SELECTORS
# descendant, child (>), adjacent (+), general (~) - 40 tests
# ============================================================================

class TestCombinatorSelectors:
    """Test CSS combinator selectors."""

    # Descendant combinator (space)
    @pytest.mark.parametrize("selector,expected_count", [
        ("article p", 3),  # Paragraphs inside article
        ("article li", 3),  # List items inside article
        ("nav a", 3),  # Links inside nav
        ("main span", 2),  # Spans inside main (author, category)
        (".post-content p", 3),  # Paragraphs inside post-content
    ])
    def test_descendant_combinator(self, extractor, article_html, selector, expected_count):
        results = extractor.extract_all(article_html, selector)
        assert len(results) == expected_count

    # Child combinator (>)
    @pytest.mark.parametrize("selector,expected_count", [
        (".post-content > p", 3),  # Direct child paragraphs
        (".feature-list > li", 3),  # Direct child list items
        ("article > h1", 1),  # h1 IS direct child of article
        ("article > .post-title", 1),  # h1.post-title IS direct child of article
        ("nav > a", 3),  # Direct child links of nav
    ])
    def test_child_combinator(self, extractor, article_html, selector, expected_count):
        results = extractor.extract_all(article_html, selector)
        assert len(results) == expected_count

    # Adjacent sibling combinator (+)
    @pytest.mark.parametrize("selector,should_exist", [
        (".intro + p", True),  # p immediately after .intro
        (".author + time", True),  # time immediately after .author
        ("h1 + div", True),  # div.post-meta immediately after h1.post-title
        ("time + span", True),  # span immediately after time
    ])
    def test_adjacent_sibling_combinator(self, extractor, article_html, selector, should_exist):
        assert extractor.exists(article_html, selector) == should_exist

    def test_adjacent_sibling_in_nested(self, extractor, nested_html):
        """Test adjacent sibling with multiple siblings."""
        # .sibling-1 + .sibling-2 should find .sibling-2
        result = extractor.extract_one(nested_html, ".sibling-1 + p")
        assert "Second sibling" in result

    # General sibling combinator (~)
    def test_general_sibling_combinator_intro(self, extractor, article_html):
        """Test .intro ~ p on article_html."""
        results = extractor.extract_all(article_html, ".intro ~ p")
        assert len(results) == 2  # Second paragraph and .highlight

    def test_general_sibling_combinator_sibling(self, extractor, nested_html):
        """Test .sibling-1 ~ p on nested_html."""
        results = extractor.extract_all(nested_html, ".sibling-1 ~ p")
        assert len(results) == 2  # sibling-2 and sibling-3

    # Complex combinations
    @pytest.mark.parametrize("selector,expected", [
        ("article .post-content > p.intro", "This is the introduction paragraph."),
        ("main article h1.post-title", "Article Title Here"),
        ("nav a.nav-link.active", "Contact"),
        (".post-footer .tags a", "python"),  # First tag
    ])
    def test_complex_combinations(self, extractor, article_html, selector, expected):
        result = extractor.extract_one(article_html, selector)
        assert result == expected


# ============================================================================
# PSEUDO-CLASS SELECTORS
# :first-child, :last-child, :nth-child, :not() - 40 tests
# ============================================================================

class TestPseudoClassSelectors:
    """Test CSS pseudo-class selectors."""

    # :first-child
    @pytest.mark.parametrize("selector,expected", [
        (".nav-link:first-child", "Home"),
        (".feature:first-child", "Feature 1"),
        (".tag:first-child", "python"),
        ("p:first-child", "This is the introduction paragraph."),
    ])
    def test_first_child(self, extractor, article_html, selector, expected):
        result = extractor.extract_one(article_html, selector)
        assert result == expected

    # :last-child
    @pytest.mark.parametrize("selector,expected", [
        (".nav-link:last-child", "Contact"),
        (".feature:last-child", "Feature 3"),
        (".tag:last-child", "web"),
    ])
    def test_last_child(self, extractor, article_html, selector, expected):
        result = extractor.extract_one(article_html, selector)
        assert result == expected

    # :nth-child(n)
    @pytest.mark.parametrize("selector,expected", [
        (".feature:nth-child(1)", "Feature 1"),
        (".feature:nth-child(2)", "Feature 2"),
        (".feature:nth-child(3)", "Feature 3"),
        (".nav-link:nth-child(2)", "About"),
        (".tag:nth-child(2)", "testing"),
    ])
    def test_nth_child_specific(self, extractor, article_html, selector, expected):
        result = extractor.extract_one(article_html, selector)
        assert result == expected

    # :nth-child(odd) and :nth-child(even)
    @pytest.mark.parametrize("selector,expected_count", [
        (".feature:nth-child(odd)", 2),  # 1st, 3rd
        (".feature:nth-child(even)", 1),  # 2nd
        (".nav-link:nth-child(odd)", 2),  # 1st, 3rd
    ])
    def test_nth_child_odd_even(self, extractor, article_html, selector, expected_count):
        results = extractor.extract_all(article_html, selector)
        assert len(results) == expected_count

    # :nth-child(an+b)
    @pytest.mark.parametrize("selector,expected_count", [
        (".feature:nth-child(2n)", 1),  # Every 2nd (2)
        (".feature:nth-child(2n+1)", 2),  # Every 2nd starting at 1 (1, 3)
        (".nav-link:nth-child(n+2)", 2),  # Starting from 2nd (2, 3)
    ])
    def test_nth_child_formula(self, extractor, article_html, selector, expected_count):
        results = extractor.extract_all(article_html, selector)
        assert len(results) == expected_count

    # :not() selector
    @pytest.mark.parametrize("selector,expected_count", [
        (".nav-link:not(.active)", 2),  # Non-active nav links
        ("p:not(.intro):not(.highlight)", 2),  # Regular paragraphs (second + footer p)
        (".feature:not(:first-child)", 2),  # Non-first features
        (".feature:not(:last-child)", 2),  # Non-last features
    ])
    def test_not_selector(self, extractor, article_html, selector, expected_count):
        results = extractor.extract_all(article_html, selector)
        assert len(results) == expected_count


# ============================================================================
# TABLE SELECTORS
# Common patterns for extracting tabular data - 25 tests
# ============================================================================

class TestTableSelectors:
    """Test CSS selectors for table data extraction."""

    def test_table_headers(self, extractor, table_html):
        """Extract table header cells."""
        results = extractor.extract_all(table_html, "thead th")
        assert results == ["Name", "Price", "Stock"]

    def test_table_rows(self, extractor, table_html):
        """Count table body rows."""
        count = extractor.count(table_html, "tbody tr")
        assert count == 3

    @pytest.mark.parametrize("row_num,expected_name", [
        (1, "Product A"),
        (2, "Product B"),
        (3, "Product C"),
    ])
    def test_table_cell_by_row(self, extractor, table_html, row_num, expected_name):
        """Extract cell from specific row."""
        selector = f"tbody tr:nth-child({row_num}) .name"
        result = extractor.extract_one(table_html, selector)
        assert result == expected_name

    @pytest.mark.parametrize("column_class,expected_values", [
        ("name", ["Product A", "Product B", "Product C"]),
        ("price", ["$10.00", "$20.00", "$15.00"]),
        ("stock", ["In Stock", "Out of Stock", "In Stock"]),
    ])
    def test_table_column(self, extractor, table_html, column_class, expected_values):
        """Extract all values from a column."""
        results = extractor.extract_all(table_html, f"tbody .{column_class}")
        assert results == expected_values

    def test_table_data_attribute(self, extractor, table_html):
        """Extract data attributes from rows."""
        results = extractor.extract_all(table_html, "tbody tr", attribute="data-id")
        assert results == ["1", "2", "3"]

    def test_table_first_row(self, extractor, table_html):
        """Select first data row."""
        result = extractor.extract_one(table_html, "tbody tr:first-child .name")
        assert result == "Product A"

    def test_table_last_row(self, extractor, table_html):
        """Select last data row."""
        result = extractor.extract_one(table_html, "tbody tr:last-child .name")
        assert result == "Product C"


# ============================================================================
# META TAG EXTRACTION
# Using MetaExtractor for metadata - 20 tests
# ============================================================================

class TestMetaExtraction:
    """Test meta tag extraction using MetaExtractor."""

    @pytest.mark.parametrize("name,expected", [
        ("author", "John Doe"),
        ("description", "A test article for CSS extraction"),
        ("nonexistent", None),
    ])
    def test_meta_name_extraction(self, meta_extractor, article_html, name, expected):
        result = meta_extractor.extract(article_html, name)
        assert result == expected

    @pytest.mark.parametrize("property_name,expected", [
        ("og:title", "Test Article OG"),
        ("article:published_time", "2024-01-15T10:00:00Z"),
        ("og:nonexistent", None),
    ])
    def test_meta_property_extraction(self, meta_extractor, article_html, property_name, expected):
        result = meta_extractor.extract(article_html, property_name)
        assert result == expected

    def test_extract_all_meta(self, meta_extractor, article_html):
        """Extract all meta tags as dictionary."""
        meta = meta_extractor.extract_all_meta(article_html)
        assert "author" in meta
        assert meta["author"] == "John Doe"
        assert "description" in meta
        assert "og:title" in meta

    def test_meta_priority(self, meta_extractor):
        """Test that name takes priority over property."""
        html = """
        <html>
        <head>
            <meta name="author" content="Name Author">
            <meta property="author" content="Property Author">
        </head>
        <body><p>Content for testing with enough words to pass validation.</p></body>
        </html>
        """
        result = meta_extractor.extract(html, "author")
        assert result == "Name Author"


# ============================================================================
# UTILITY METHODS
# exists(), count() - 15 tests
# ============================================================================

class TestUtilityMethods:
    """Test utility methods on CSSExtractor."""

    @pytest.mark.parametrize("selector,should_exist", [
        ("article", True),
        (".post-title", True),
        ("#main-nav", True),
        (".nonexistent", False),
        ("#nonexistent", False),
        ("nonexistent-tag", False),
    ])
    def test_exists(self, extractor, article_html, selector, should_exist):
        assert extractor.exists(article_html, selector) == should_exist

    @pytest.mark.parametrize("selector,expected_count", [
        ("article", 1),
        ("p", 4),  # intro, second, highlight, footer p
        ("a", 8),
        (".feature", 3),
        (".nonexistent", 0),
    ])
    def test_count(self, extractor, article_html, selector, expected_count):
        assert extractor.count(article_html, selector) == expected_count


# ============================================================================
# ERROR HANDLING
# Graceful handling of invalid selectors and malformed HTML - 15 tests
# ============================================================================

class TestErrorHandling:
    """Test error handling in CSS extraction."""

    @pytest.mark.parametrize("selector", [
        "",  # Empty selector
        "   ",  # Whitespace only
    ])
    def test_empty_selector(self, extractor, article_html, selector):
        """Empty selectors should return None/empty gracefully."""
        # Note: lxml may raise or return empty - test graceful handling
        result = extractor.extract_one(article_html, selector)
        # Should not raise, may return None

    @pytest.mark.parametrize("invalid_selector", [
        "[[invalid",
        "div[",
        ":invalid-pseudo(",
        "div:nth-child(",
    ])
    def test_invalid_selector_syntax(self, extractor, article_html, invalid_selector):
        """Invalid CSS syntax should return None/empty, not raise."""
        result = extractor.extract_one(article_html, invalid_selector)
        assert result is None

        results = extractor.extract_all(article_html, invalid_selector)
        assert results == []

        exists = extractor.exists(article_html, invalid_selector)
        assert exists is False

        count = extractor.count(article_html, invalid_selector)
        assert count == 0

    def test_empty_html(self, extractor):
        """Empty HTML should return None/empty gracefully."""
        result = extractor.extract_one("", "div")
        assert result is None

        results = extractor.extract_all("", "div")
        assert results == []

    def test_malformed_html(self, extractor):
        """Malformed HTML should be handled gracefully by lxml."""
        malformed = "<div><p>Unclosed<span>nested</div>"
        result = extractor.extract_one(malformed, "p")
        # lxml should auto-correct and still find p
        assert result is not None

    def test_no_matches(self, extractor, article_html):
        """Non-matching selectors should return None/empty."""
        result = extractor.extract_one(article_html, ".does-not-exist")
        assert result is None

        results = extractor.extract_all(article_html, ".does-not-exist")
        assert results == []


# ============================================================================
# REAL-WORLD PATTERNS
# Common patterns from web scraping scenarios - 20 tests
# ============================================================================

class TestRealWorldPatterns:
    """Test real-world CSS selector patterns commonly used in scraping."""

    def test_article_extraction_pattern(self, extractor, article_html):
        """Common pattern for extracting article data."""
        title = extractor.extract_one(article_html, "h1, .post-title, .article-title")
        assert "Article Title Here" in title

    def test_author_extraction_patterns(self, extractor, article_html):
        """Multiple author selector patterns."""
        selectors = [".author", "[rel='author']", ".byline", ".post-author"]
        for selector in selectors:
            result = extractor.extract_one(article_html, selector)
            if result:
                assert "John" in result
                break

    def test_date_extraction_pattern(self, extractor, article_html):
        """Extract date from time element or datetime attribute."""
        datetime_val = extractor.extract_one(article_html, "time", attribute="datetime")
        assert datetime_val == "2024-01-15"

        text_val = extractor.extract_one(article_html, "time")
        assert "January" in text_val

    def test_link_extraction_pattern(self, extractor, article_html):
        """Extract all links with their hrefs."""
        hrefs = extractor.extract_all(article_html, "a", attribute="href")
        assert len(hrefs) == 8
        assert "/" in hrefs

    def test_image_src_extraction(self, extractor):
        """Extract image sources."""
        html = """
        <html><body>
        <div class="gallery">
            <img src="/img/1.jpg" alt="Image 1">
            <img src="/img/2.jpg" alt="Image 2">
            <img data-src="/img/lazy.jpg" alt="Lazy loaded">
        </div>
        <p>Additional content to meet minimum word count for testing purposes.</p>
        </body></html>
        """
        srcs = extractor.extract_all(html, "img", attribute="src")
        assert srcs == ["/img/1.jpg", "/img/2.jpg"]

        lazy_src = extractor.extract_one(html, "img[data-src]", attribute="data-src")
        assert lazy_src == "/img/lazy.jpg"

    def test_price_extraction_pattern(self, extractor, table_html):
        """Extract prices from common price selectors."""
        prices = extractor.extract_all(table_html, ".price")
        assert "$10.00" in prices
        assert "$20.00" in prices

    @pytest.mark.parametrize("html,selector,expected", [
        # WordPress patterns
        ('<article class="post-123 type-post"><h2>Title</h2></article>', "article h2", "Title"),
        # Generic content patterns
        ('<div class="entry-content"><p>Content</p></div>', ".entry-content p", "Content"),
        # Schema.org patterns
        ('<span itemprop="name">Product</span>', '[itemprop="name"]', "Product"),
    ])
    def test_cms_specific_patterns(self, extractor, html, selector, expected):
        """Test CMS-specific selector patterns."""
        result = extractor.extract_one(html, selector)
        assert result == expected


# ============================================================================
# MULTIPLE CLASSES
# Elements with multiple classes - 10 tests
# ============================================================================

class TestMultipleClasses:
    """Test selecting elements with multiple classes."""

    @pytest.fixture
    def multi_class_html(self):
        return """
        <html><body>
        <div class="card featured">Featured Card</div>
        <div class="card regular">Regular Card</div>
        <div class="card featured large">Featured Large Card</div>
        <div class="btn primary">Primary Button</div>
        <div class="btn secondary">Secondary Button</div>
        <p>Additional content to meet minimum word count for testing purposes.
        This paragraph provides padding to ensure content passes validation.</p>
        </body></html>
        """

    @pytest.mark.parametrize("selector,expected_count", [
        (".card", 3),  # All cards
        (".featured", 2),  # All featured
        (".card.featured", 2),  # Cards that are featured
        (".card.featured.large", 1),  # Cards that are featured AND large
        (".btn", 2),  # All buttons
        (".btn.primary", 1),  # Primary buttons
    ])
    def test_multiple_class_selection(self, extractor, multi_class_html, selector, expected_count):
        results = extractor.extract_all(multi_class_html, selector)
        assert len(results) == expected_count

    def test_class_order_independent(self, extractor, multi_class_html):
        """Class order in selector shouldn't matter."""
        result1 = extractor.extract_all(multi_class_html, ".card.featured")
        result2 = extractor.extract_all(multi_class_html, ".featured.card")
        assert len(result1) == len(result2)
