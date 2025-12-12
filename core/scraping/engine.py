"""Scraping engine with cascade fallback strategy."""

import re
from typing import Optional, List, Dict, Any
from dataclasses import dataclass

from core.scraping.fetchers.http_fetcher import HTTPFetcher, FetchResult
from core.scraping.fetchers.playwright_fetcher import PlaywrightFetcher, PlaywrightResult
from core.scraping.extractors.css_extractor import CSSExtractor
from core.scraping.extractors.xpath_extractor import XPathExtractor
from core.poison_pills.detector import PoisonPillDetector
import config


@dataclass
class ScrapeResult:
    """Result from a scraping operation."""

    success: bool
    url: str
    method: str = ""
    data: Dict[str, Any] = None
    html: str = ""
    html_preview: str = ""
    error: Optional[str] = None
    response_time_ms: int = 0
    poison_pill: Optional[str] = None

    def __post_init__(self):
        if self.data is None:
            self.data = {}


class ScrapingEngine:
    """
    Main scraping engine implementing cascade strategy:
    1. Try HTTP request first (fast)
    2. Fall back to Playwright if HTTP fails or content is JS-heavy
    """

    def __init__(self):
        self.http_fetcher = HTTPFetcher()
        self.playwright_fetcher = PlaywrightFetcher()
        self.css_extractor = CSSExtractor()
        self.xpath_extractor = XPathExtractor()
        self.poison_detector = PoisonPillDetector()

    def fetch_page(
        self,
        url: str,
        force_playwright: bool = False,
        timeout: int = 30000,
    ) -> Dict[str, Any]:
        """
        Fetch a page using cascade strategy.

        Args:
            url: URL to fetch
            force_playwright: Skip HTTP and use Playwright directly
            timeout: Timeout in milliseconds

        Returns:
            Dict with html, method, status_code, error
        """
        if force_playwright:
            result = self.playwright_fetcher.fetch(url, timeout=timeout)
            return {
                "html": result.html,
                "method": "playwright",
                "status_code": result.status_code,
                "error": result.error,
                "response_time_ms": result.response_time_ms,
            }

        # Try HTTP first
        http_result = self.http_fetcher.fetch(url, timeout=timeout // 1000)

        if http_result.success:
            # Check if content needs JavaScript
            if self._needs_javascript(http_result.html):
                # Fall back to Playwright
                pw_result = self.playwright_fetcher.fetch(url, timeout=timeout)
                return {
                    "html": pw_result.html,
                    "method": "playwright",
                    "status_code": pw_result.status_code,
                    "error": pw_result.error,
                    "response_time_ms": http_result.response_time_ms + pw_result.response_time_ms,
                }

            return {
                "html": http_result.html,
                "method": "http",
                "status_code": http_result.status_code,
                "error": None,
                "response_time_ms": http_result.response_time_ms,
            }

        # HTTP failed - check if it's worth trying Playwright
        if http_result.status_code in (403, 429) or "blocked" in (http_result.error or "").lower():
            pw_result = self.playwright_fetcher.fetch(url, timeout=timeout)
            return {
                "html": pw_result.html,
                "method": "playwright",
                "status_code": pw_result.status_code,
                "error": pw_result.error if not pw_result.success else None,
                "response_time_ms": http_result.response_time_ms + pw_result.response_time_ms,
            }

        return {
            "html": "",
            "method": "http",
            "status_code": http_result.status_code,
            "error": http_result.error,
            "response_time_ms": http_result.response_time_ms,
        }

    def _needs_javascript(self, html: str) -> bool:
        """
        Detect if page needs JavaScript to render content.

        Looks for signs of JS-heavy frameworks or minimal content.
        """
        if not html:
            return True

        # Check content length
        if len(html) < 1000:
            return True

        # Check for SPA frameworks
        spa_indicators = [
            r'<div\s+id=["\']root["\']>\s*</div>',
            r'<div\s+id=["\']app["\']>\s*</div>',
            r'<div\s+id=["\']__next["\']',
            r'window\.__INITIAL_STATE__',
            r'window\.__NUXT__',
            r'ng-app=',
            r'data-reactroot',
        ]

        for pattern in spa_indicators:
            if re.search(pattern, html, re.IGNORECASE):
                return True

        # Check for minimal body content
        body_match = re.search(r'<body[^>]*>(.*?)</body>', html, re.DOTALL | re.IGNORECASE)
        if body_match:
            body_content = body_match.group(1)
            # Remove scripts and styles
            body_content = re.sub(r'<script[^>]*>.*?</script>', '', body_content, flags=re.DOTALL | re.IGNORECASE)
            body_content = re.sub(r'<style[^>]*>.*?</style>', '', body_content, flags=re.DOTALL | re.IGNORECASE)
            body_content = re.sub(r'<[^>]+>', '', body_content)
            body_content = body_content.strip()

            if len(body_content) < 500:
                return True

        return False

    def scrape_url(
        self,
        url: str,
        rules: List[Dict[str, Any]],
        timeout: int = 30000,
    ) -> ScrapeResult:
        """
        Scrape a URL and extract data using provided rules.

        Args:
            url: URL to scrape
            rules: List of extraction rules [{name, selector_type, selector_value, attribute, is_list}]
            timeout: Timeout in milliseconds

        Returns:
            ScrapeResult with extracted data
        """
        # Fetch the page
        fetch_result = self.fetch_page(url, timeout=timeout)

        if fetch_result.get("error") and not fetch_result.get("html"):
            return ScrapeResult(
                success=False,
                url=url,
                method=fetch_result.get("method", ""),
                error=fetch_result.get("error"),
                response_time_ms=fetch_result.get("response_time_ms", 0),
            )

        html = fetch_result.get("html", "")

        # Check for poison pills
        poison_check = self.poison_detector.detect(html, url)
        if poison_check.is_poison:
            return ScrapeResult(
                success=False,
                url=url,
                method=fetch_result.get("method", ""),
                html=html,
                html_preview=html[:2000],
                error=poison_check.details.get("message", "Content issue detected"),
                poison_pill=poison_check.pill_type,
                response_time_ms=fetch_result.get("response_time_ms", 0),
            )

        # Extract data using rules
        extracted_data = {}
        extraction_errors = []

        for rule in rules:
            name = rule.get("name")
            selector_type = rule.get("selector_type", "css")
            selector_value = rule.get("selector_value")
            attribute = rule.get("attribute")
            is_list = rule.get("is_list", False)
            is_required = rule.get("is_required", False)

            if not name or not selector_value:
                continue

            try:
                if selector_type == "css":
                    extractor = self.css_extractor
                else:
                    extractor = self.xpath_extractor

                if is_list:
                    value = extractor.extract_all(html, selector_value, attribute)
                else:
                    value = extractor.extract_one(html, selector_value, attribute)

                if value:
                    extracted_data[name] = value
                elif is_required:
                    extraction_errors.append(f"Required field '{name}' not found")

            except Exception as e:
                extraction_errors.append(f"Error extracting '{name}': {str(e)}")

        # Determine success
        success = len(extracted_data) > 0 and len(extraction_errors) == 0

        return ScrapeResult(
            success=success,
            url=url,
            method=fetch_result.get("method", ""),
            data=extracted_data,
            html=html,
            html_preview=html[:2000],
            error="; ".join(extraction_errors) if extraction_errors else None,
            response_time_ms=fetch_result.get("response_time_ms", 0),
        )

    def test_selector(
        self,
        html: str,
        selector_type: str,
        selector_value: str,
        attribute: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Test a selector on HTML content.

        Returns:
            Dict with matches and count
        """
        if selector_type == "css":
            extractor = self.css_extractor
        else:
            extractor = self.xpath_extractor

        try:
            matches = extractor.extract_all(html, selector_value, attribute)
            return {
                "success": True,
                "matches": matches,
                "count": len(matches),
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "matches": [],
                "count": 0,
            }
