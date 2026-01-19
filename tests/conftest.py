"""Pytest configuration and shared fixtures."""

import os
import sys
import pytest
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# ============================================================================
# HTML Fixtures
# ============================================================================

@pytest.fixture
def simple_html():
    """Basic HTML page for testing - meets minimum content length."""
    # Padding to meet minimum content requirements (500 chars, 50 words)
    return """
    <!DOCTYPE html>
    <html>
    <head><title>Test Page</title></head>
    <body>
        <h1 class="title">Hello World</h1>
        <p id="content">This is test content.</p>
        <ul class="items">
            <li>Item 1</li>
            <li>Item 2</li>
            <li>Item 3</li>
        </ul>
        <a href="https://example.com">Link</a>
        <p>Additional content paragraph to meet minimum word count requirements for the poison pill detector.
        This paragraph contains enough words to pass the content length validation check. We need at least
        fifty words in the document for it to be considered valid content rather than an error page or
        blocked response. This ensures our tests are checking the correct detection logic.</p>
    </body>
    </html>
    """


@pytest.fixture
def complex_html():
    """Complex HTML with nested structures."""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Complex Page</title>
        <meta name="description" content="Test description">
    </head>
    <body>
        <header>
            <nav class="main-nav">
                <a href="/" class="nav-link">Home</a>
                <a href="/about" class="nav-link">About</a>
            </nav>
        </header>
        <main>
            <article class="post" data-id="123">
                <h1 class="post-title">Article Title</h1>
                <div class="post-meta">
                    <span class="author">John Doe</span>
                    <time datetime="2024-01-15">Jan 15, 2024</time>
                </div>
                <div class="post-content">
                    <p>First paragraph with <strong>bold</strong> text and additional content to ensure we have enough words.</p>
                    <p>Second paragraph with <a href="#">a link</a> and more descriptive content for testing purposes.</p>
                    <p>Third paragraph that contains even more text content to help reach the minimum word count
                    required by the poison pill detector. This ensures our complex HTML fixture is truly valid
                    and will not be flagged as content too short during testing.</p>
                </div>
                <div class="tags">
                    <span class="tag">python</span>
                    <span class="tag">testing</span>
                    <span class="tag">web</span>
                </div>
            </article>
        </main>
        <footer>
            <p>&copy; 2024 Test Site</p>
        </footer>
    </body>
    </html>
    """


@pytest.fixture
def malformed_html():
    """Malformed HTML for robustness testing."""
    return """
    <html>
    <head><title>Broken
    <body>
        <div class="unclosed">
            <p>Paragraph without closing
            <span>Nested span
        <div class="another">More content</div>
        <img src="broken.jpg" alt="No closing tag"
        <a href="link">Link without </a closing
    </body>
    """


@pytest.fixture
def empty_html():
    """Empty/minimal HTML."""
    return "<html><body></body></html>"


@pytest.fixture
def js_heavy_html():
    """JavaScript-heavy SPA page."""
    return """
    <!DOCTYPE html>
    <html>
    <head><title>SPA App</title></head>
    <body>
        <div id="root"></div>
        <script>
            window.__INITIAL_STATE__ = {};
            // React app would render here
        </script>
    </body>
    </html>
    """


# ============================================================================
# Poison Pill Fixtures
# ============================================================================

def _pad_content(base_html, padding_text=None):
    """Add padding to HTML to meet minimum content requirements."""
    if padding_text is None:
        padding_text = """
        <p>This is additional content to ensure we meet the minimum word count requirement.
        The poison pill detector requires at least 50 words and 500 characters before it will
        check for other types of issues. This paragraph provides that padding while still
        allowing the specific poison pill pattern to be detected first in the check order.
        Adding more content here to ensure we definitely exceed the minimum threshold of
        five hundred characters that the detector uses to identify content too short errors.</p>
        """
    # Insert before closing body tag
    return base_html.replace("</body>", padding_text + "</body>")


@pytest.fixture
def paywall_html():
    """HTML with paywall indicators - meets minimum length."""
    base = """
    <html>
    <body>
        <div class="paywall">
            <h2>Subscribe to read this article</h2>
            <p>This is premium content for members only.</p>
            <button>Subscribe Now</button>
        </div>
    </body>
    </html>
    """
    return _pad_content(base)


@pytest.fixture
def rate_limited_html():
    """HTML indicating rate limiting - meets minimum length."""
    base = """
    <html>
    <body>
        <h1>Too Many Requests</h1>
        <p>You have exceeded the rate limit. Please try again later.</p>
        <p>Request limit: 100 per hour</p>
    </body>
    </html>
    """
    return _pad_content(base)


@pytest.fixture
def cloudflare_html():
    """Cloudflare challenge page - meets minimum length."""
    base = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Just a moment...</title>
    </head>
    <body>
        <div class="cf-browser-verification">
            <h1>Checking your browser before accessing</h1>
            <p>This process is automatic.</p>
        </div>
        <script>window.cf_chl_opt = {};</script>
    </body>
    </html>
    """
    return _pad_content(base)


@pytest.fixture
def captcha_html():
    """HTML with CAPTCHA challenge - meets minimum length."""
    base = """
    <html>
    <body>
        <h1>Complete the challenge below</h1>
        <div class="g-recaptcha" data-sitekey="xxx"></div>
        <form>
            <button type="submit">Submit</button>
        </form>
    </body>
    </html>
    """
    return _pad_content(base)


@pytest.fixture
def not_found_html():
    """404 page HTML - meets minimum length."""
    base = """
    <html>
    <head><title>404 - Page Not Found</title></head>
    <body>
        <h1>Page not found</h1>
        <p>Sorry, we couldn't find the page you requested.</p>
    </body>
    </html>
    """
    return _pad_content(base)


@pytest.fixture
def login_required_html():
    """Login required page - meets minimum length."""
    base = """
    <html>
    <body>
        <h1>Please log in to continue</h1>
        <p>Sign in to view this content.</p>
        <form>
            <input type="email" placeholder="Email">
            <input type="password" placeholder="Password">
            <button>Log In</button>
        </form>
    </body>
    </html>
    """
    return _pad_content(base)


# ============================================================================
# Mock Objects
# ============================================================================

@pytest.fixture
def mock_fetch_result():
    """Factory for creating mock fetch results."""
    def _create(success=True, html="<html><body>Test</body></html>",
                status_code=200, error=None, method="http"):
        from dataclasses import dataclass
        from typing import Optional

        @dataclass
        class MockResult:
            success: bool
            html: str
            status_code: int
            error: Optional[str]
            method: str
            response_time_ms: int = 100
            screenshot: Optional[bytes] = None

        return MockResult(
            success=success,
            html=html,
            status_code=status_code,
            error=error,
            method=method,
        )

    return _create


# ============================================================================
# Temporary Files
# ============================================================================

@pytest.fixture
def temp_image(tmp_path):
    """Create a temporary test image for vision tests."""
    try:
        from PIL import Image, ImageDraw

        # Create simple image with text
        img = Image.new('RGB', (400, 200), color='white')
        draw = ImageDraw.Draw(img)
        draw.text((50, 50), "Test Text 123", fill='black')
        draw.text((50, 100), "Price: $99.99", fill='black')

        img_path = tmp_path / "test_image.png"
        img.save(img_path)

        return img_path
    except ImportError:
        pytest.skip("PIL not available for image tests")


@pytest.fixture
def temp_screenshot_bytes(temp_image):
    """Get screenshot as bytes."""
    with open(temp_image, 'rb') as f:
        return f.read()


# ============================================================================
# Books to Scrape Fixtures (Deterministic Scraping Target)
# ============================================================================

BOOKS_TO_SCRAPE_BOOK_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <title>A Light in the Attic | Books to Scrape - Sandbox</title>
</head>
<body>
<div class="container-fluid page">
    <div class="page_inner">
        <ul class="breadcrumb">
            <li><a href="index.html">Home</a></li>
            <li><a href="catalogue/category/books_1/index.html">Books</a></li>
            <li><a href="catalogue/category/books/poetry_23/index.html">Poetry</a></li>
            <li class="active">A Light in the Attic</li>
        </ul>
        <div id="content_inner">
            <article class="product_page">
                <div class="row">
                    <div class="col-sm-6">
                        <div id="product_gallery" class="carousel">
                            <div class="thumbnail">
                                <img src="media/cache/fe/72/fe72f0532301ec28892ae79a629a293c.jpg"
                                     alt="A Light in the Attic" class="thumbnail">
                            </div>
                        </div>
                    </div>
                    <div class="col-sm-6 product_main">
                        <h1>A Light in the Attic</h1>
                        <p class="price_color">£51.77</p>
                        <p class="instock availability">
                            <i class="icon-ok"></i>
                            In stock (22 available)
                        </p>
                        <p class="star-rating Three">
                            <i class="icon-star"></i>
                            <i class="icon-star"></i>
                            <i class="icon-star"></i>
                            <i class="icon-star"></i>
                            <i class="icon-star"></i>
                        </p>
                    </div>
                </div>
                <table class="table table-striped">
                    <tr><th>UPC</th><td>a897fe39b1053632</td></tr>
                    <tr><th>Product Type</th><td>Books</td></tr>
                    <tr><th>Price (excl. tax)</th><td>£51.77</td></tr>
                    <tr><th>Price (incl. tax)</th><td>£51.77</td></tr>
                    <tr><th>Tax</th><td>£0.00</td></tr>
                    <tr><th>Availability</th><td>In stock (22 available)</td></tr>
                    <tr><th>Number of reviews</th><td>0</td></tr>
                </table>
                <div id="product_description" class="sub-header">
                    <h2>Product Description</h2>
                </div>
                <p>It's hard to imagine a world without A Light in the Attic. This now-classic
                collection of poetry and drawings from Shel Silverstein celebrates its 20th
                anniversary with this special edition. Silverstein's humorous and creative verse
                can amuse the dowdiest of readers. Lemon-faced adults and fidgety kids sit still
                and read these rhythmic words and laugh and smile and love that Silverstein.
                Special features include twelve new poems as well as classroom ideas and a reading
                group guide.</p>
            </article>
        </div>
    </div>
</div>
</body>
</html>
"""


BOOKS_TO_SCRAPE_CATALOG_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <title>All products | Books to Scrape - Sandbox</title>
</head>
<body>
<div class="container-fluid page">
    <div class="page_inner">
        <div class="row">
            <div class="col-sm-8 col-md-9">
                <div class="page-header action">
                    <h1>All products <small>1000 results</small></h1>
                </div>
                <section>
                    <div>
                        <ol class="row">
                            <li class="col-xs-6 col-sm-4 col-md-3 col-lg-3">
                                <article class="product_pod">
                                    <div class="image_container">
                                        <a href="a-light-in-the-attic_1000/index.html">
                                            <img src="media/cache/2c/da/2cdad67c44b002e7ead0cc35693c0e8b.jpg"
                                                 alt="A Light in the Attic" class="thumbnail">
                                        </a>
                                    </div>
                                    <p class="star-rating Three">
                                        <i class="icon-star"></i>
                                    </p>
                                    <h3><a href="a-light-in-the-attic_1000/index.html"
                                           title="A Light in the Attic">A Light in the ...</a></h3>
                                    <div class="product_price">
                                        <p class="price_color">£51.77</p>
                                        <p class="instock availability"><i class="icon-ok"></i> In stock</p>
                                        <form>
                                            <button type="submit" class="btn btn-primary btn-block"
                                                    data-loading-text="Adding...">Add to basket</button>
                                        </form>
                                    </div>
                                </article>
                            </li>
                            <li class="col-xs-6 col-sm-4 col-md-3 col-lg-3">
                                <article class="product_pod">
                                    <div class="image_container">
                                        <a href="tipping-the-velvet_999/index.html">
                                            <img src="media/cache/26/0c/260c6ae16bce31c8f8c95daddd9f4a1c.jpg"
                                                 alt="Tipping the Velvet" class="thumbnail">
                                        </a>
                                    </div>
                                    <p class="star-rating One">
                                        <i class="icon-star"></i>
                                    </p>
                                    <h3><a href="tipping-the-velvet_999/index.html"
                                           title="Tipping the Velvet">Tipping the Velvet</a></h3>
                                    <div class="product_price">
                                        <p class="price_color">£53.74</p>
                                        <p class="instock availability"><i class="icon-ok"></i> In stock</p>
                                        <form>
                                            <button type="submit" class="btn btn-primary btn-block"
                                                    data-loading-text="Adding...">Add to basket</button>
                                        </form>
                                    </div>
                                </article>
                            </li>
                            <li class="col-xs-6 col-sm-4 col-md-3 col-lg-3">
                                <article class="product_pod">
                                    <div class="image_container">
                                        <a href="soumission_998/index.html">
                                            <img src="media/cache/3e/ef/3eef99c9d9adef34639f510662022571.jpg"
                                                 alt="Soumission" class="thumbnail">
                                        </a>
                                    </div>
                                    <p class="star-rating One">
                                        <i class="icon-star"></i>
                                    </p>
                                    <h3><a href="soumission_998/index.html"
                                           title="Soumission">Soumission</a></h3>
                                    <div class="product_price">
                                        <p class="price_color">£50.10</p>
                                        <p class="instock availability"><i class="icon-ok"></i> In stock</p>
                                        <form>
                                            <button type="submit" class="btn btn-primary btn-block"
                                                    data-loading-text="Adding...">Add to basket</button>
                                        </form>
                                    </div>
                                </article>
                            </li>
                        </ol>
                    </div>
                </section>
                <div>
                    <ul class="pager">
                        <li class="current">Page 1 of 50</li>
                        <li class="next"><a href="page-2.html">next</a></li>
                    </ul>
                </div>
            </div>
        </div>
    </div>
    <footer class="site-footer">
        <p class="about">Welcome to our online bookstore where you can browse and purchase
        a wide selection of books from various genres including fiction, non-fiction,
        science, technology, and many more categories to choose from today.</p>
    </footer>
</div>
</body>
</html>
"""


@pytest.fixture
def books_to_scrape_book():
    """Realistic book detail page HTML from Books to Scrape sandbox."""
    return BOOKS_TO_SCRAPE_BOOK_HTML


@pytest.fixture
def books_to_scrape_catalog():
    """Realistic catalog listing page HTML from Books to Scrape sandbox."""
    return BOOKS_TO_SCRAPE_CATALOG_HTML


@pytest.fixture
def books_to_scrape_selectors():
    """Common CSS selectors for Books to Scrape site."""
    return {
        # Book detail page selectors
        "title": "article.product_page h1",
        "price": "p.price_color",
        "availability": "p.instock.availability",
        "description": "#product_description + p",
        "upc": "table tr:nth-child(1) td",
        "rating": "p.star-rating",
        "breadcrumb": "ul.breadcrumb li",
        # Catalog page selectors
        "books": "article.product_pod",
        "book_title": "article.product_pod h3 a",
        "book_price": "article.product_pod .price_color",
        "book_link": "article.product_pod .image_container a",
        "pagination": "ul.pager li.current",
        "next_page": "ul.pager li.next a",
    }


# ============================================================================
# Utility Functions for Tests
# ============================================================================

def pad_html(base_html: str) -> str:
    """
    Add padding to HTML to meet minimum content requirements.

    Use this helper for inline test HTML that needs to pass the
    poison pill detector's content length check (500 chars, 50 words).
    """
    return _pad_content(base_html)
