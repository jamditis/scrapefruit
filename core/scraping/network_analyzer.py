"""Network analyzer for capturing XHR/fetch requests and discovering API endpoints.

Many modern websites load data via XHR/fetch requests (JSON APIs, GraphQL, etc.)
that are often easier to scrape than parsing the rendered DOM. This module
intercepts network traffic during page load to discover these data sources.

Usage:
    from core.scraping.network_analyzer import NetworkAnalyzer

    analyzer = NetworkAnalyzer()

    # Capture network traffic from a URL
    result = analyzer.capture(url, wait_time=5000)

    # Get discovered API endpoints
    for endpoint in result.api_endpoints:
        print(f"{endpoint.method} {endpoint.url} -> {endpoint.content_type}")

    # Get JSON responses
    for response in result.json_responses:
        print(f"{response.url}: {len(response.data)} items")
"""

import asyncio
import json
import re
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Set
from urllib.parse import urlparse, parse_qs

import config


@dataclass
class CapturedRequest:
    """A captured network request."""

    url: str
    method: str
    headers: Dict[str, str] = field(default_factory=dict)
    post_data: Optional[str] = None
    resource_type: str = ""
    timestamp: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CapturedResponse:
    """A captured network response."""

    url: str
    status: int
    headers: Dict[str, str] = field(default_factory=dict)
    content_type: str = ""
    content_length: int = 0
    body: Optional[str] = None
    is_json: bool = False
    json_data: Optional[Any] = None
    timestamp: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        # Don't include full body in dict representation (can be large)
        if self.body and len(self.body) > 1000:
            d["body"] = self.body[:1000] + f"... ({len(self.body)} chars total)"
        return d


@dataclass
class APIEndpoint:
    """A discovered API endpoint."""

    url: str
    method: str
    content_type: str
    status: int
    response_size: int
    is_json: bool = False
    is_graphql: bool = False
    has_pagination: bool = False
    query_params: Dict[str, List[str]] = field(default_factory=dict)
    sample_data_keys: List[str] = field(default_factory=list)
    data_array_path: Optional[str] = None  # e.g., "data.items" or "results"
    data_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class NetworkCaptureResult:
    """Result from network capture."""

    url: str
    success: bool
    requests: List[CapturedRequest] = field(default_factory=list)
    responses: List[CapturedResponse] = field(default_factory=list)
    api_endpoints: List[APIEndpoint] = field(default_factory=list)
    json_responses: List[CapturedResponse] = field(default_factory=list)
    graphql_responses: List[CapturedResponse] = field(default_factory=list)
    error: Optional[str] = None
    capture_time_ms: int = 0
    total_requests: int = 0
    total_bytes: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "url": self.url,
            "success": self.success,
            "error": self.error,
            "capture_time_ms": self.capture_time_ms,
            "total_requests": self.total_requests,
            "total_bytes": self.total_bytes,
            "api_endpoints": [e.to_dict() for e in self.api_endpoints],
            "json_responses": [r.to_dict() for r in self.json_responses],
            "graphql_responses": [r.to_dict() for r in self.graphql_responses],
            # Don't include all requests/responses by default (can be large)
            "request_count": len(self.requests),
            "response_count": len(self.responses),
        }


# Patterns that indicate API endpoints
API_URL_PATTERNS = [
    r"/api/",
    r"/v\d+/",
    r"/graphql",
    r"/rest/",
    r"/data/",
    r"/json/",
    r"/ajax/",
    r"/_next/data/",  # Next.js
    r"/__api__/",
    r"/wp-json/",  # WordPress REST API
    r"/feed",
    r"\.json$",
]

# Content types that indicate JSON/API responses
JSON_CONTENT_TYPES = [
    "application/json",
    "text/json",
    "application/ld+json",
    "application/hal+json",
    "application/vnd.api+json",
]

# Resource types to capture
CAPTURE_RESOURCE_TYPES = {"xhr", "fetch", "document", "script"}

# Resource types to ignore
IGNORE_RESOURCE_TYPES = {"image", "stylesheet", "font", "media", "manifest", "other"}

# Pagination indicators in query params or response
PAGINATION_PARAMS = ["page", "offset", "limit", "cursor", "after", "before", "skip", "take", "per_page", "pageSize"]


class NetworkAnalyzer:
    """
    Analyzes network traffic to discover API endpoints and JSON data sources.

    Uses Playwright to intercept all network requests during page load,
    identifies XHR/fetch requests that return JSON, and extracts useful
    information about discovered API endpoints.
    """

    def __init__(self):
        self._browser = None
        self._playwright = None

    async def _ensure_browser(self):
        """Ensure browser is launched."""
        if self._browser is None:
            from playwright.async_api import async_playwright

            self._playwright = await async_playwright().start()

            launch_options = {
                "headless": True,
                "args": [
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                ],
            }

            # Use system Chromium on ARM64
            chromium_path = getattr(config, "CHROMIUM_EXECUTABLE_PATH", None)
            if chromium_path:
                launch_options["executable_path"] = chromium_path

            self._browser = await self._playwright.chromium.launch(**launch_options)

    async def capture_async(
        self,
        url: str,
        wait_time: int = 5000,
        wait_for_idle: bool = True,
        include_bodies: bool = True,
        max_body_size: int = 1024 * 1024,  # 1MB
    ) -> NetworkCaptureResult:
        """
        Capture network traffic from a URL.

        Args:
            url: URL to capture traffic from
            wait_time: Time to wait for network activity (ms)
            wait_for_idle: Wait for network to be idle before returning
            include_bodies: Include response bodies in results
            max_body_size: Maximum body size to capture (bytes)

        Returns:
            NetworkCaptureResult with captured requests and discovered endpoints
        """
        import time
        start_time = time.time()

        result = NetworkCaptureResult(url=url, success=False)
        requests: List[CapturedRequest] = []
        responses: List[CapturedResponse] = []
        response_bodies: Dict[str, str] = {}

        try:
            await self._ensure_browser()
            context = await self._browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = await context.new_page()

            # Set up request interception
            async def handle_request(request):
                resource_type = request.resource_type
                if resource_type in IGNORE_RESOURCE_TYPES:
                    return

                captured = CapturedRequest(
                    url=request.url,
                    method=request.method,
                    headers=dict(request.headers),
                    post_data=request.post_data,
                    resource_type=resource_type,
                    timestamp=datetime.now().isoformat(),
                )
                requests.append(captured)

            # Set up response interception
            async def handle_response(response):
                resource_type = response.request.resource_type
                if resource_type in IGNORE_RESOURCE_TYPES:
                    return

                content_type = response.headers.get("content-type", "")
                content_length = int(response.headers.get("content-length", 0))

                captured = CapturedResponse(
                    url=response.url,
                    status=response.status,
                    headers=dict(response.headers),
                    content_type=content_type,
                    content_length=content_length,
                    timestamp=datetime.now().isoformat(),
                )

                # Check if JSON response
                is_json = any(ct in content_type.lower() for ct in JSON_CONTENT_TYPES)
                captured.is_json = is_json

                # Capture body for JSON responses
                if include_bodies and is_json and content_length < max_body_size:
                    try:
                        body = await response.text()
                        captured.body = body
                        captured.content_length = len(body)

                        # Try to parse JSON
                        try:
                            captured.json_data = json.loads(body)
                        except json.JSONDecodeError:
                            pass
                    except Exception:
                        pass

                responses.append(captured)
                result.total_bytes += content_length

            page.on("request", handle_request)
            page.on("response", handle_response)

            # Navigate to page
            try:
                if wait_for_idle:
                    await page.goto(url, wait_until="networkidle", timeout=wait_time + 30000)
                else:
                    await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                    await page.wait_for_timeout(wait_time)
            except Exception as e:
                # Page might timeout but we still want the captured traffic
                if "timeout" not in str(e).lower():
                    raise

            # Additional wait for any delayed requests
            await page.wait_for_timeout(min(wait_time, 3000))

            await context.close()

            result.requests = requests
            result.responses = responses
            result.total_requests = len(requests)
            result.success = True

            # Analyze captured traffic
            self._analyze_responses(result)

        except Exception as e:
            result.error = str(e)

        result.capture_time_ms = int((time.time() - start_time) * 1000)
        return result

    def capture(
        self,
        url: str,
        wait_time: int = 5000,
        wait_for_idle: bool = True,
        include_bodies: bool = True,
    ) -> NetworkCaptureResult:
        """Synchronous wrapper for capture_async."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        asyncio.run,
                        self.capture_async(url, wait_time, wait_for_idle, include_bodies)
                    )
                    return future.result(timeout=wait_time / 1000 + 60)
            else:
                return loop.run_until_complete(
                    self.capture_async(url, wait_time, wait_for_idle, include_bodies)
                )
        except RuntimeError:
            return asyncio.run(
                self.capture_async(url, wait_time, wait_for_idle, include_bodies)
            )

    def _analyze_responses(self, result: NetworkCaptureResult):
        """Analyze captured responses to identify API endpoints."""
        seen_urls: Set[str] = set()

        for response in result.responses:
            # Skip non-successful responses
            if response.status < 200 or response.status >= 400:
                continue

            # Skip if already seen (dedupe by URL without query params for some cases)
            base_url = response.url.split("?")[0]
            if base_url in seen_urls and not response.is_json:
                continue

            # Check if this looks like an API endpoint
            is_api = self._is_api_endpoint(response)

            if response.is_json:
                result.json_responses.append(response)

                # Check for GraphQL
                if "/graphql" in response.url.lower() or self._is_graphql_response(response):
                    result.graphql_responses.append(response)

            if is_api or response.is_json:
                endpoint = self._create_endpoint(response)
                if endpoint:
                    result.api_endpoints.append(endpoint)
                    seen_urls.add(base_url)

        # Sort endpoints by relevance (larger responses, JSON, etc.)
        result.api_endpoints.sort(
            key=lambda e: (e.is_json, e.data_count, e.response_size),
            reverse=True
        )

    def _is_api_endpoint(self, response: CapturedResponse) -> bool:
        """Check if response looks like an API endpoint."""
        url_lower = response.url.lower()

        # Check URL patterns
        for pattern in API_URL_PATTERNS:
            if re.search(pattern, url_lower):
                return True

        # Check content type
        if response.is_json:
            return True

        return False

    def _is_graphql_response(self, response: CapturedResponse) -> bool:
        """Check if response is a GraphQL response."""
        if not response.json_data:
            return False

        # GraphQL responses typically have "data" and optionally "errors" keys
        if isinstance(response.json_data, dict):
            keys = set(response.json_data.keys())
            if "data" in keys or "errors" in keys:
                # Check if it has the GraphQL structure
                if keys <= {"data", "errors", "extensions"}:
                    return True

        return False

    def _create_endpoint(self, response: CapturedResponse) -> Optional[APIEndpoint]:
        """Create an APIEndpoint from a captured response."""
        parsed = urlparse(response.url)
        query_params = parse_qs(parsed.query)

        endpoint = APIEndpoint(
            url=response.url,
            method="GET",  # We don't track method in response, assume GET
            content_type=response.content_type,
            status=response.status,
            response_size=response.content_length,
            is_json=response.is_json,
            is_graphql=self._is_graphql_response(response),
            query_params=query_params,
        )

        # Check for pagination
        for param in PAGINATION_PARAMS:
            if param.lower() in [p.lower() for p in query_params.keys()]:
                endpoint.has_pagination = True
                break

        # Analyze JSON data structure
        if response.json_data:
            self._analyze_json_structure(endpoint, response.json_data)

        return endpoint

    def _analyze_json_structure(self, endpoint: APIEndpoint, data: Any, path: str = ""):
        """Analyze JSON data structure to find arrays and keys."""
        if isinstance(data, dict):
            # Get top-level keys
            if not path:
                endpoint.sample_data_keys = list(data.keys())[:20]

            # Look for arrays in common paths
            for key, value in data.items():
                current_path = f"{path}.{key}" if path else key

                if isinstance(value, list) and len(value) > 0:
                    # Found an array - this might be the main data
                    if not endpoint.data_array_path or len(value) > endpoint.data_count:
                        endpoint.data_array_path = current_path
                        endpoint.data_count = len(value)

                        # Check pagination in response
                        if any(p in data for p in ["total", "count", "totalCount", "total_count", "hasMore", "has_more", "next", "nextPage"]):
                            endpoint.has_pagination = True

                elif isinstance(value, dict):
                    # Recurse into nested objects (but not too deep)
                    if path.count(".") < 2:
                        self._analyze_json_structure(endpoint, value, current_path)

        elif isinstance(data, list):
            endpoint.data_array_path = path or "root"
            endpoint.data_count = len(data)

    async def close_async(self):
        """Close browser resources."""
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None

    def close(self):
        """Synchronous close."""
        if self._browser:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # Can't await in running loop, just mark as None
                    self._browser = None
                    self._playwright = None
                else:
                    loop.run_until_complete(self.close_async())
            except RuntimeError:
                asyncio.run(self.close_async())


def capture_network(url: str, wait_time: int = 5000) -> NetworkCaptureResult:
    """Convenience function to capture network traffic from a URL."""
    analyzer = NetworkAnalyzer()
    try:
        return analyzer.capture(url, wait_time)
    finally:
        analyzer.close()
