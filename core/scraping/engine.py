"""Scraping engine with configurable cascade fallback strategy."""

import re
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field

from core.scraping.fetchers.http_fetcher import HTTPFetcher
from core.scraping.fetchers.playwright_fetcher import PlaywrightFetcher
from core.scraping.fetchers.agent_browser_fetcher import AgentBrowserFetcher
from core.scraping.fetchers.browser_use_fetcher import BrowserUseFetcher
from core.scraping.extractors.css_extractor import CSSExtractor

# Optional: pyppeteer may not be installed
try:
    from core.scraping.fetchers.puppeteer_fetcher import PuppeteerFetcher
    HAS_PUPPETEER = True
except ImportError:
    PuppeteerFetcher = None
    HAS_PUPPETEER = False
from core.scraping.extractors.xpath_extractor import XPathExtractor
from core.scraping.extractors.vision_extractor import get_vision_extractor
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
    cascade_attempts: List[Dict[str, Any]] = field(default_factory=list)
    screenshot: Optional[bytes] = None
    vision_extracted: bool = False  # True if data came from OCR

    def __post_init__(self):
        if self.data is None:
            self.data = {}


# Default cascade configuration
DEFAULT_CASCADE_CONFIG = {
    "enabled": True,
    "order": getattr(config, "DEFAULT_CASCADE_ORDER", ["http", "playwright", "puppeteer", "agent_browser"]),
    "max_attempts": 4,
    "fallback_on": {
        "status_codes": getattr(config, "FALLBACK_STATUS_CODES", [403, 429, 503]),
        "error_patterns": getattr(config, "FALLBACK_ERROR_PATTERNS", ["blocked", "captcha", "cloudflare", "challenge", "denied"]),
        "poison_pills": getattr(config, "FALLBACK_POISON_PILLS", ["anti_bot", "rate_limited"]),
        "empty_content": True,
        "javascript_required": True,
        "min_content_length": 500,
    },
}


class ScrapingEngine:
    """
    Main scraping engine implementing configurable cascade strategy.

    Cascade order (configurable):
    1. HTTP (fastest, lightweight) - FREE
    2. Playwright (JS rendering, stealth) - FREE
    3. Puppeteer (alternative fingerprint) - FREE
    4. Agent-browser (accessibility tree, semantic locators) - PREMIUM
    5. Browser-use (AI-driven, LLM-controlled) - PREMIUM

    Falls back to next method on:
    - Blocked status codes (403, 429, 503)
    - Anti-bot detection patterns
    - Empty or JS-heavy content
    - Poison pill detection

    Vision fallback:
    - If DOM extraction fails, captures screenshot and uses OCR

    Premium methods (agent_browser, browser_use) use more resources
    and may require API keys or donation to use.
    """

    # Available fetcher types
    FETCHER_TYPES = ["http", "playwright", "puppeteer", "agent_browser", "browser_use"]

    # Premium fetchers (may require donation or API key)
    PREMIUM_FETCHERS = ["agent_browser", "browser_use"]

    def __init__(self):
        # Fetcher registry - lazy loaded
        self._fetchers: Dict[str, Any] = {}

        # Extractors
        self.css_extractor = CSSExtractor()
        self.xpath_extractor = XPathExtractor()
        self.poison_detector = PoisonPillDetector()

    def _get_fetcher(self, method: str):
        """
        Get or create a fetcher by method name. Lazy-loaded for efficiency.

        Args:
            method: Fetcher type ('http', 'playwright', 'puppeteer', 'agent_browser')

        Returns:
            Fetcher instance or None if unavailable
        """
        if method in self._fetchers:
            return self._fetchers[method]

        fetcher = None

        if method == "http":
            fetcher = HTTPFetcher()
        elif method == "playwright":
            fetcher = PlaywrightFetcher()
        elif method == "puppeteer":
            if not HAS_PUPPETEER:
                return None
            try:
                fetcher = PuppeteerFetcher()
            except Exception:
                # Pyppeteer initialization failed
                return None
        elif method == "agent_browser":
            fetcher = AgentBrowserFetcher()
            # Check if CLI is available
            if not fetcher.is_available():
                return None
        elif method == "browser_use":
            fetcher = BrowserUseFetcher()
            # Check if browser-use is installed and has API key
            if not fetcher.is_available():
                return None

        if fetcher:
            self._fetchers[method] = fetcher

        return fetcher

    def fetch_page(
        self,
        url: str,
        cascade_config: Optional[Dict[str, Any]] = None,
        timeout: int = 30000,
        force_method: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Fetch a page using cascade strategy with configurable fallback.

        Args:
            url: URL to fetch
            cascade_config: Override cascade settings (order, fallback conditions)
            timeout: Timeout in milliseconds
            force_method: Skip cascade and use specific method

        Returns:
            Dict with html, method, status_code, error, attempts
        """
        # Handle force_method (backwards compatibility with force_playwright)
        if force_method:
            fetcher = self._get_fetcher(force_method)
            if not fetcher:
                return {
                    "html": "",
                    "method": force_method,
                    "status_code": 0,
                    "error": f"Fetcher '{force_method}' not available",
                    "response_time_ms": 0,
                    "attempts": [],
                }

            result = self._fetch_with_method(fetcher, force_method, url, timeout)
            return {
                "html": result.get("html", ""),
                "method": force_method,
                "status_code": result.get("status_code", 0),
                "error": result.get("error"),
                "response_time_ms": result.get("response_time_ms", 0),
                "attempts": [result],
            }

        # Merge cascade config with defaults
        cfg = {**DEFAULT_CASCADE_CONFIG}
        if cascade_config:
            cfg.update(cascade_config)
            # Handle fallback_on - ensure it's a dict, not a list
            if "fallback_on" in cascade_config:
                fallback_cfg = cascade_config["fallback_on"]
                if isinstance(fallback_cfg, dict):
                    cfg["fallback_on"] = {**DEFAULT_CASCADE_CONFIG["fallback_on"], **fallback_cfg}
                else:
                    # Invalid format - use defaults
                    cfg["fallback_on"] = DEFAULT_CASCADE_CONFIG["fallback_on"]

        # If cascade disabled, use first available method only
        if not cfg.get("enabled", True):
            order = cfg.get("order", ["http"])
            for method in order:
                fetcher = self._get_fetcher(method)
                if fetcher:
                    result = self._fetch_with_method(fetcher, method, url, timeout)
                    return {
                        "html": result.get("html", ""),
                        "method": method,
                        "status_code": result.get("status_code", 0),
                        "error": result.get("error"),
                        "response_time_ms": result.get("response_time_ms", 0),
                        "attempts": [result],
                    }

        # Run cascade
        order = cfg.get("order", DEFAULT_CASCADE_CONFIG["order"])
        max_attempts = min(cfg.get("max_attempts", 4), len(order))
        fallback_on = cfg.get("fallback_on", DEFAULT_CASCADE_CONFIG["fallback_on"])

        attempts = []
        total_time = 0

        for i, method in enumerate(order[:max_attempts]):
            fetcher = self._get_fetcher(method)
            if not fetcher:
                continue

            # Adjust timeout per method (HTTP gets less time since it's faster)
            method_timeout = timeout // 2 if method == "http" else timeout

            result = self._fetch_with_method(fetcher, method, url, method_timeout)
            result["attempt_index"] = i + 1
            attempts.append(result)
            total_time += result.get("response_time_ms", 0)

            if result.get("success", False):
                # Check if we should still fallback despite success
                should_fallback, reason = self._should_fallback(
                    result.get("html", ""),
                    fallback_on,
                )

                if should_fallback and i < max_attempts - 1:
                    result["fallback_reason"] = reason
                    continue

                # Success - return result
                return {
                    "html": result.get("html", ""),
                    "method": method,
                    "status_code": result.get("status_code", 0),
                    "error": None,
                    "response_time_ms": total_time,
                    "attempts": attempts,
                }

            # Failed - check if we should try next method
            if not self._should_try_next(result, fallback_on):
                break

        # All methods failed - return last attempt info
        last = attempts[-1] if attempts else {}
        return {
            "html": last.get("html", ""),
            "method": last.get("method", "none"),
            "status_code": last.get("status_code", 0),
            "error": last.get("error", "All cascade methods failed"),
            "response_time_ms": total_time,
            "attempts": attempts,
        }

    def _fetch_with_method(
        self,
        fetcher,
        method: str,
        url: str,
        timeout: int,
        take_screenshot: bool = False,
    ) -> Dict[str, Any]:
        """
        Fetch URL using a specific fetcher.

        Args:
            fetcher: Fetcher instance
            method: Method name for logging
            url: URL to fetch
            timeout: Timeout in milliseconds
            take_screenshot: Whether to capture a screenshot (browser methods only)

        Returns:
            Dict with fetch result
        """
        try:
            # HTTP fetcher uses seconds, others use milliseconds
            # HTTP doesn't support screenshots
            if method == "http":
                result = fetcher.fetch(url, timeout=timeout // 1000)
            else:
                # Browser-based fetchers support screenshots
                result = fetcher.fetch(url, timeout=timeout, take_screenshot=take_screenshot)

            return {
                "method": method,
                "success": result.success,
                "html": result.html,
                "status_code": result.status_code,
                "error": result.error,
                "response_time_ms": result.response_time_ms,
                "screenshot": getattr(result, 'screenshot', None),
            }

        except Exception as e:
            return {
                "method": method,
                "success": False,
                "html": "",
                "status_code": 0,
                "error": str(e),
                "response_time_ms": 0,
                "screenshot": None,
            }

    def _should_fallback(
        self,
        html: str,
        fallback_on: Dict[str, Any],
    ) -> Tuple[bool, Optional[str]]:
        """
        Determine if we should try the next fetcher despite success.

        Args:
            html: Fetched HTML content
            fallback_on: Fallback condition configuration

        Returns:
            Tuple of (should_fallback, reason)
        """
        # Check JavaScript requirement
        if fallback_on.get("javascript_required", True):
            if self._needs_javascript(html):
                return True, "javascript_required"

        # Check content length
        if fallback_on.get("empty_content", True):
            min_length = fallback_on.get("min_content_length", 500)
            if len(html) < min_length:
                return True, "content_too_short"

        # Check for poison pills that might resolve with different method
        retry_pills = fallback_on.get("poison_pills", [])
        if retry_pills and html:
            poison_check = self.poison_detector.detect(html, "")
            if poison_check.is_poison and poison_check.pill_type in retry_pills:
                return True, f"poison_pill:{poison_check.pill_type}"

        return False, None

    def _should_try_next(
        self,
        result: Dict[str, Any],
        fallback_on: Dict[str, Any],
    ) -> bool:
        """
        Determine if failure warrants trying the next method.

        Args:
            result: Fetch result dict
            fallback_on: Fallback condition configuration

        Returns:
            True if should try next method
        """
        # Check status code triggers
        trigger_codes = fallback_on.get("status_codes", [403, 429, 503])
        if result.get("status_code") in trigger_codes:
            return True

        # Check error patterns
        error_patterns = fallback_on.get("error_patterns", [])
        error = result.get("error", "")
        if error:
            error_lower = error.lower()
            for pattern in error_patterns:
                if pattern.lower() in error_lower:
                    return True

        # Default: try next on any failure
        return True

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
        cascade_config: Optional[Dict[str, Any]] = None,
        enable_vision_fallback: bool = True,
    ) -> ScrapeResult:
        """
        Scrape a URL and extract data using provided rules.

        Uses a two-phase extraction strategy:
        1. First attempts DOM-based extraction (CSS/XPath selectors)
        2. If DOM extraction fails and vision is available, falls back to
           screenshot + OCR for text extraction

        Args:
            url: URL to scrape
            rules: List of extraction rules [{name, selector_type, selector_value, attribute, is_list}]
            timeout: Timeout in milliseconds
            cascade_config: Optional cascade configuration override
            enable_vision_fallback: Try OCR on screenshot if DOM extraction fails

        Returns:
            ScrapeResult with extracted data
        """
        # Fetch the page using cascade
        fetch_result = self.fetch_page(url, cascade_config=cascade_config, timeout=timeout)

        if fetch_result.get("error") and not fetch_result.get("html"):
            return ScrapeResult(
                success=False,
                url=url,
                method=fetch_result.get("method", ""),
                error=fetch_result.get("error"),
                response_time_ms=fetch_result.get("response_time_ms", 0),
                cascade_attempts=fetch_result.get("attempts", []),
            )

        html = fetch_result.get("html", "")

        # Check for poison pills
        poison_check = self.poison_detector.detect(html, url)
        if poison_check.is_poison:
            # Check if this poison pill should have triggered cascade retry
            retry_pills = DEFAULT_CASCADE_CONFIG["fallback_on"].get("poison_pills", [])
            if poison_check.pill_type not in retry_pills:
                return ScrapeResult(
                    success=False,
                    url=url,
                    method=fetch_result.get("method", ""),
                    html=html,
                    html_preview=html[:2000],
                    error=poison_check.details.get("message", "Content issue detected"),
                    poison_pill=poison_check.pill_type,
                    response_time_ms=fetch_result.get("response_time_ms", 0),
                    cascade_attempts=fetch_result.get("attempts", []),
                )

        # Phase 1: Extract data using DOM rules
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

        # Determine success from DOM extraction
        dom_success = len(extracted_data) > 0 and len(extraction_errors) == 0
        screenshot = None
        vision_extracted = False

        # Phase 2: Vision fallback if DOM extraction failed
        if not dom_success and enable_vision_fallback and rules:
            vision_result = self._try_vision_extraction(url, timeout, cascade_config)
            if vision_result:
                screenshot = vision_result.get("screenshot")
                vision_data = vision_result.get("data", {})

                if vision_data:
                    # Merge vision data with any partial DOM data
                    for key, value in vision_data.items():
                        if key not in extracted_data:
                            extracted_data[key] = value

                    vision_extracted = True

                    # Clear extraction errors if vision found data
                    if extracted_data:
                        extraction_errors = []

        # Determine final success
        success = len(extracted_data) > 0 and len(extraction_errors) == 0

        # Build error message
        if extraction_errors:
            error_msg = "; ".join(extraction_errors)
        elif len(extracted_data) == 0 and rules:
            error_msg = f"No data extracted (0/{len(rules)} selectors matched)"
            if enable_vision_fallback:
                error_msg += " - vision fallback also failed"
        else:
            error_msg = None

        return ScrapeResult(
            success=success,
            url=url,
            method=fetch_result.get("method", ""),
            data=extracted_data,
            html=html,
            html_preview=html[:2000],
            error=error_msg,
            response_time_ms=fetch_result.get("response_time_ms", 0),
            cascade_attempts=fetch_result.get("attempts", []),
            screenshot=screenshot,
            vision_extracted=vision_extracted,
        )

    def _try_vision_extraction(
        self,
        url: str,
        timeout: int,
        cascade_config: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Attempt to extract data using screenshot + OCR.

        Takes a screenshot using a browser-based fetcher, then uses
        Tesseract OCR to extract text and structure from the image.

        Args:
            url: URL to screenshot
            timeout: Timeout in milliseconds
            cascade_config: Cascade configuration

        Returns:
            Dict with 'screenshot' bytes and 'data' dict, or None if failed
        """
        vision_extractor = get_vision_extractor()
        if not vision_extractor:
            return None  # Tesseract not available

        # Try to get a screenshot using browser-based fetcher
        screenshot = None

        # Prefer Playwright for screenshots
        for method in ["playwright", "puppeteer"]:
            fetcher = self._get_fetcher(method)
            if fetcher:
                try:
                    result = self._fetch_with_method(
                        fetcher, method, url, timeout, take_screenshot=True
                    )
                    if result.get("screenshot"):
                        screenshot = result["screenshot"]
                        break
                except Exception:
                    continue

        if not screenshot:
            return None

        # Run OCR on screenshot
        try:
            vision_result = vision_extractor.extract_structured(screenshot)

            if not vision_result.success:
                return {"screenshot": screenshot, "data": {}}

            # Build extracted data from OCR results
            extracted_data = {}

            # Add raw text as fallback
            if vision_result.text:
                extracted_data["_ocr_text"] = vision_result.text

            # Add any structured data found
            if vision_result.structured_data:
                for key, value in vision_result.structured_data.items():
                    if not key.startswith("_"):
                        extracted_data[key] = value

            return {
                "screenshot": screenshot,
                "data": extracted_data,
                "confidence": vision_result.confidence,
            }

        except Exception as e:
            return {"screenshot": screenshot, "data": {}, "error": str(e)}

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

    def get_available_methods(self) -> List[str]:
        """
        Get list of available fetcher methods.

        Returns:
            List of method names that are currently available
        """
        available = []
        for method in self.FETCHER_TYPES:
            fetcher = self._get_fetcher(method)
            if fetcher:
                available.append(method)
        return available
