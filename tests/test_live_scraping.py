"""
Live scraping tests using real URLs from the Rosen Archive.

These tests verify:
1. The sample analyzer (auto-rule extractor) works correctly
2. The cascade scraper fetches and extracts data properly
3. Different URL types (articles, blog posts, videos) are handled

Run with: pytest tests/test_live_scraping.py -v -s
"""

import pytest
import csv
import sys
import os
from pathlib import Path
from urllib.parse import urlparse

# Fix Windows console encoding issues
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.scraping.engine import ScrapingEngine, ScrapeResult
from core.scraping.fetchers.http_fetcher import HTTPFetcher
from core.scraping.extractors.css_extractor import CSSExtractor


# Test URL batches from different domains
TEST_URLS = {
    "archive_pressthink": [
        "http://archive.pressthink.org/2005/03/08/nlsn_blg_p.html",
        "http://archive.pressthink.org/2004/08/27/rnc_jitter_p.html",
        "http://archive.pressthink.org/2006/09/20/rts_gft_p.html",
    ],
    "pressthink_org": [
        "https://pressthink.org/2016/09/asymmetry-between-the-major-parties-fries-the-circuits-of-the-mainstream-press/",
    ],
    "medium": [
        "https://medium.com/centerforcooperativemedia/beyond-the-democracy-desk-why-u-s-newsrooms-need-to-become-explicitly-pro-democracy-a650d7ddd0cd",
    ],
    "guardian": [
        "https://www.theguardian.com/commentisfree/2020/jan/10/were-not-eli-sanders-supporters-the-press-has-underestimated-his-chances-again-sanders",
    ],
    "vox": [
        "https://www.vox.com/policy-and-politics/21495104/donald-trump-media-2020-election-jay-rosen",
    ],
}

# Common article rules for testing extraction (flexible for different sites)
ARTICLE_RULES = [
    {"name": "page_title", "selector_type": "css", "selector_value": "title", "is_required": False},
    {"name": "title", "selector_type": "css", "selector_value": "h1, h2.title, h3.title, .title, .headline", "is_required": False},
    {"name": "meta_description", "selector_type": "css", "selector_value": "meta[name='description']", "attribute": "content"},
    {"name": "og_title", "selector_type": "css", "selector_value": "meta[property='og:title']", "attribute": "content"},
    {"name": "og_description", "selector_type": "css", "selector_value": "meta[property='og:description']", "attribute": "content"},
    {"name": "author", "selector_type": "css", "selector_value": "meta[name='author'], .author, .byline, [rel='author']", "attribute": None},
    {"name": "content", "selector_type": "css", "selector_value": "article, .post-content, .entry-content, .article-body, main, body", "attribute": None},
]

# Archive.pressthink.org specific rules
ARCHIVE_PRESSTHINK_RULES = [
    {"name": "page_title", "selector_type": "css", "selector_value": "title", "is_required": True},
    {"name": "title", "selector_type": "css", "selector_value": "h3.title", "is_required": False},
    {"name": "subhead", "selector_type": "css", "selector_value": "h4.subhead", "is_required": False},
    {"name": "date", "selector_type": "css", "selector_value": ".date", "is_required": False},
    {"name": "content", "selector_type": "css", "selector_value": "body", "is_required": False},
]


class TestHTTPFetcher:
    """Test basic HTTP fetching."""

    @pytest.fixture
    def fetcher(self):
        return HTTPFetcher()

    @pytest.mark.integration
    def test_fetch_archive_pressthink(self, fetcher):
        """Test fetching from archive.pressthink.org (should work with HTTP)."""
        url = TEST_URLS["archive_pressthink"][0]
        result = fetcher.fetch(url)

        print(f"\n--- HTTP Fetch: {url} ---")
        print(f"Success: {result.success}")
        print(f"Status: {result.status_code}")
        print(f"Response time: {result.response_time_ms}ms")
        print(f"HTML length: {len(result.html)} chars")

        assert result.success, f"Failed to fetch: {result.error}"
        assert result.status_code == 200
        assert len(result.html) > 1000, "HTML too short"

    @pytest.mark.integration
    def test_fetch_medium(self, fetcher):
        """Test fetching from Medium (may require JS or get blocked)."""
        url = TEST_URLS["medium"][0]
        result = fetcher.fetch(url)

        print(f"\n--- HTTP Fetch: {url} ---")
        print(f"Success: {result.success}")
        print(f"Status: {result.status_code}")
        print(f"Response time: {result.response_time_ms}ms")
        print(f"HTML length: {len(result.html)} chars")

        # Medium might block or require JS, so just check we got a response
        assert result.status_code > 0


class TestCSSExtractor:
    """Test CSS extraction on fetched HTML."""

    @pytest.fixture
    def extractor(self):
        return CSSExtractor()

    @pytest.fixture
    def fetcher(self):
        return HTTPFetcher()

    @pytest.mark.integration
    def test_extract_title_from_archive(self, extractor, fetcher):
        """Test extracting title from archive.pressthink.org."""
        url = TEST_URLS["archive_pressthink"][0]
        fetch_result = fetcher.fetch(url)
        assert fetch_result.success, f"Failed to fetch: {fetch_result.error}"

        title = extractor.extract_one(fetch_result.html, "h1, .title, title")
        print(f"\n--- Title extraction: {url} ---")
        print(f"Title: {title}")

        assert title is not None, "No title found"
        assert len(title) > 5, "Title too short"

    @pytest.mark.integration
    def test_extract_meta_tags(self, extractor, fetcher):
        """Test extracting meta tags."""
        url = TEST_URLS["archive_pressthink"][0]
        fetch_result = fetcher.fetch(url)
        assert fetch_result.success

        # Extract various meta tags
        results = {}
        results["title"] = extractor.extract_one(fetch_result.html, "title")
        results["description"] = extractor.extract_one(
            fetch_result.html, "meta[name='description']", attribute="content"
        )

        print(f"\n--- Meta extraction: {url} ---")
        for key, value in results.items():
            print(f"{key}: {value[:100] if value else 'None'}...")

        assert results["title"] is not None


class TestScrapingEngine:
    """Test the full scraping engine with cascade."""

    @pytest.fixture
    def engine(self):
        return ScrapingEngine()

    @pytest.mark.integration
    def test_scrape_archive_pressthink_http(self, engine):
        """Test scraping archive.pressthink.org with HTTP method."""
        url = TEST_URLS["archive_pressthink"][0]

        result = engine.scrape_url(
            url=url,
            rules=ARCHIVE_PRESSTHINK_RULES,  # Use site-specific rules
            cascade_config={"enabled": False, "order": ["http"]},
        )

        print(f"\n--- Engine scrape (HTTP only): {url} ---")
        print(f"Success: {result.success}")
        print(f"Method: {result.method}")
        print(f"Response time: {result.response_time_ms}ms")
        print(f"Poison pill: {result.poison_pill}")
        print(f"Data extracted: {list(result.data.keys())}")
        for key, value in result.data.items():
            val_str = str(value)[:100] if value else "None"
            print(f"  {key}: {val_str}...")

        assert result.success, f"Failed: {result.error}"
        assert result.method == "http"
        assert "page_title" in result.data or "title" in result.data

    @pytest.mark.integration
    def test_scrape_with_cascade(self, engine):
        """Test scraping with cascade fallback enabled."""
        url = TEST_URLS["archive_pressthink"][1]

        result = engine.scrape_url(
            url=url,
            rules=ARTICLE_RULES,
            cascade_config={
                "enabled": True,
                "order": ["http", "playwright"],
                "max_attempts": 2,
            },
        )

        print(f"\n--- Engine scrape (cascade): {url} ---")
        print(f"Success: {result.success}")
        print(f"Method used: {result.method}")
        print(f"Cascade attempts: {len(result.cascade_attempts)}")
        for attempt in result.cascade_attempts:
            print(f"  - {attempt.get('method')}: {attempt.get('success')}")
        print(f"Data extracted: {list(result.data.keys())}")

        assert result.success, f"Failed: {result.error}"

    @pytest.mark.integration
    @pytest.mark.slow
    def test_scrape_medium_needs_js(self, engine):
        """Test scraping Medium which may need JS rendering."""
        url = TEST_URLS["medium"][0]

        result = engine.scrape_url(
            url=url,
            rules=ARTICLE_RULES,
            cascade_config={
                "enabled": True,
                "order": ["http", "playwright"],
                "max_attempts": 2,
                "fallback_on": {
                    "status_codes": [403, 429, 503],
                    "error_patterns": ["blocked", "captcha"],
                    "empty_content": True,
                    "min_content_length": 500,
                },
            },
        )

        print(f"\n--- Engine scrape (Medium): {url} ---")
        print(f"Success: {result.success}")
        print(f"Method used: {result.method}")
        print(f"Cascade attempts: {len(result.cascade_attempts)}")
        print(f"Poison pill: {result.poison_pill}")
        print(f"Data keys: {list(result.data.keys())}")

        # Medium is tricky - might fail but should at least try
        if result.success:
            assert len(result.data) > 0


class TestBatchScraping:
    """Test scraping multiple URLs in sequence."""

    @pytest.fixture
    def engine(self):
        return ScrapingEngine()

    @pytest.mark.integration
    @pytest.mark.slow
    def test_batch_archive_pressthink(self, engine):
        """Test scraping a batch of archive.pressthink.org URLs."""
        urls = TEST_URLS["archive_pressthink"]
        results = []

        print(f"\n--- Batch scrape: {len(urls)} URLs ---")

        for url in urls:
            result = engine.scrape_url(
                url=url,
                rules=ARTICLE_RULES,
                cascade_config={"enabled": False, "order": ["http"]},
            )
            results.append(result)
            print(f"  {url[:50]}... -> {'✓' if result.success else '✗'} ({result.method})")

        successes = sum(1 for r in results if r.success)
        print(f"\nTotal: {successes}/{len(urls)} successful")

        assert successes >= len(urls) * 0.8, f"Too many failures: {successes}/{len(urls)}"


class TestAutoRuleExtraction:
    """Test the sample analyzer / auto-rule extraction functionality."""

    @pytest.mark.integration
    def test_fetch_samples_api(self):
        """Test the fetch-samples API endpoint for auto-rule extraction."""
        import requests

        # This test requires the app to be running
        base_url = "http://127.0.0.1:5150"

        try:
            # Check if server is running
            response = requests.get(f"{base_url}/api/settings", timeout=2)
            if response.status_code != 200:
                pytest.skip("Server not running")
        except requests.exceptions.ConnectionError:
            pytest.skip("Server not running at localhost:5150")

        # Test fetch-samples endpoint
        urls = TEST_URLS["archive_pressthink"][:2]
        response = requests.post(
            f"{base_url}/api/scraping/fetch-samples",
            json={"urls": urls},
            timeout=60,
        )

        print(f"\n--- Fetch Samples API ---")
        print(f"Status: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print(f"Samples fetched: {len(data.get('samples', []))}")
            print(f"Suggested rules: {len(data.get('suggested_rules', []))}")

            for rule in data.get("suggested_rules", [])[:5]:
                print(f"  - {rule.get('name')}: {rule.get('selector_value')}")

            assert len(data.get("samples", [])) > 0


def load_urls_from_csv(csv_path: str, limit: int = 50) -> list:
    """Load unique URLs from the CSV file."""
    urls = []
    seen = set()

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader)  # skip header
        for row in reader:
            if len(row) > 2 and row[2].startswith("http"):
                url = row[2]
                if url not in seen:
                    seen.add(url)
                    urls.append(url)
                    if len(urls) >= limit:
                        break

    return urls


if __name__ == "__main__":
    # Run a quick test
    print("Loading URLs from CSV...")
    csv_path = Path(__file__).parent / "Rosen Archive URL List - test_runs.csv"

    if csv_path.exists():
        urls = load_urls_from_csv(str(csv_path), limit=10)
        print(f"Loaded {len(urls)} unique URLs")

        engine = ScrapingEngine()
        print("\nTesting scraping engine...")

        for url in urls[:3]:
            print(f"\nScraping: {url[:60]}...")
            result = engine.scrape_url(
                url=url,
                rules=ARTICLE_RULES,
                cascade_config={"enabled": True, "order": ["http", "playwright"]},
            )
            print(f"  Success: {result.success}, Method: {result.method}")
            if result.data:
                print(f"  Data keys: {list(result.data.keys())}")
    else:
        print(f"CSV not found: {csv_path}")
