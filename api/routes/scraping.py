"""Scraping action endpoints for preview and testing."""

from flask import Blueprint, request, jsonify

scraping_bp = Blueprint("scraping", __name__)

# Lazy-load engine to prevent import errors from breaking the blueprint
_engine = None

def get_engine():
    global _engine
    if _engine is None:
        from core.scraping.engine import ScrapingEngine
        _engine = ScrapingEngine()
    return _engine


@scraping_bp.route("/preview", methods=["POST"])
def preview_scrape():
    """Preview scrape a single URL with provided rules."""
    data = request.get_json()
    url = data.get("url")
    rules = data.get("rules", [])

    if not url:
        return jsonify({"error": "URL is required"}), 400

    try:
        result = get_engine().scrape_url(url, rules)
        return jsonify({
            "success": True,
            "url": url,
            "method": result.get("method"),
            "data": result.get("data"),
            "html_preview": result.get("html_preview", "")[:5000],
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "url": url,
        }), 500


@scraping_bp.route("/test-selector", methods=["POST"])
def test_selector():
    """Test a CSS/XPath selector on a URL."""
    data = request.get_json()
    url = data.get("url")
    selector_type = data.get("selector_type", "css")
    selector_value = data.get("selector_value")
    attribute = data.get("attribute")

    if not url or not selector_value:
        return jsonify({"error": "URL and selector_value are required"}), 400

    try:
        from core.scraping.extractors.css_extractor import CSSExtractor
        from core.scraping.extractors.xpath_extractor import XPathExtractor

        # Fetch the page
        html_result = get_engine().fetch_page(url)
        html = html_result.get("html", "")

        # Test extraction
        if selector_type == "css":
            extractor = CSSExtractor()
        else:
            extractor = XPathExtractor()

        matches = extractor.extract_all(html, selector_value, attribute)

        return jsonify({
            "success": True,
            "matches": matches[:20],
            "count": len(matches),
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
        }), 500


@scraping_bp.route("/fetch-html", methods=["POST"])
def fetch_html():
    """Fetch raw HTML from a URL."""
    data = request.get_json()
    url = data.get("url")
    use_playwright = data.get("use_playwright", False)

    if not url:
        return jsonify({"error": "URL is required"}), 400

    try:
        # Fix: use force_method parameter (not force_playwright)
        force_method = "playwright" if use_playwright else None
        result = get_engine().fetch_page(url, force_method=force_method)
        return jsonify({
            "success": True,
            "html": result.get("html", ""),
            "method": result.get("method"),
            "status_code": result.get("status_code"),
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
        }), 500


@scraping_bp.route("/fetch-samples", methods=["POST"])
def fetch_samples():
    """
    Fetch HTML from URLs for sample analysis.

    Options:
        quick_mode: If true, use HTTP-only fetching (faster, bypasses Cloudflare timeout)
                    Default is true to avoid timeouts through Cloudflare Tunnel.
        use_playwright: If true, use full cascade with Playwright (slower but handles JS).
                        Only use for sites that require JavaScript rendering.
    """
    import subprocess
    import shutil
    import traceback

    data = request.get_json()
    urls = data.get("urls", [])
    # Default to quick mode to avoid Cloudflare timeout
    quick_mode = data.get("quick_mode", True)
    use_playwright = data.get("use_playwright", False)

    if not urls:
        return jsonify({"error": "No URLs provided"}), 400

    if len(urls) > 10:
        return jsonify({"error": "Maximum 10 URLs allowed"}), 400

    samples = []
    errors = []

    # Check if singlefile is available
    singlefile_path = shutil.which("single-file") or shutil.which("singlefile")

    for url in urls:
        try:
            html = None

            # Quick mode: HTTP-only fetching (fast, avoids Cloudflare timeout)
            if quick_mode and not use_playwright:
                engine = get_engine()
                result = engine.fetch_page(url, force_method="http", timeout=30000)
                html = result.get("html", "")
                if result.get("error"):
                    errors.append({"url": url, "error": result.get("error"), "fallback": True})
                    # Continue to try other methods if HTTP fails
                    html = None

            # Try SingleFile if quick_mode didn't get content (or wasn't used)
            if not html and singlefile_path and not quick_mode:
                try:
                    result = subprocess.run(
                        [singlefile_path, url, "--dump-content"],
                        capture_output=True,
                        text=True,
                        timeout=60
                    )
                    if result.returncode == 0 and result.stdout.strip():
                        html = result.stdout
                except (subprocess.TimeoutExpired, Exception) as e:
                    print(f"SingleFile failed for {url}: {e}")

            # Fall back to full scraping engine (with Playwright)
            if not html and (use_playwright or not quick_mode):
                engine = get_engine()
                result = engine.fetch_page(url)
                html = result.get("html", "")

            if html and len(html) > 100:  # Minimum viable HTML
                samples.append({
                    "url": url,
                    "html": html,
                    "size": len(html)
                })
            else:
                errors.append({"url": url, "error": "Empty or minimal HTML returned"})

        except Exception as e:
            traceback.print_exc()
            errors.append({"url": url, "error": str(e)})

    return jsonify({
        "success": True,
        "samples": samples,
        "errors": errors,
        "fetched_count": len(samples),
        "error_count": len(errors),
        "mode": "quick_http" if quick_mode and not use_playwright else "full_playwright",
        "note": "Using quick HTTP mode. Pass use_playwright=true for JS-heavy sites." if quick_mode else None
    })


@scraping_bp.route("/analyze-html", methods=["POST"])
def analyze_html():
    """Analyze uploaded HTML samples and suggest extraction rules."""
    import traceback

    try:
        from core.scraping.analyzer import HTMLAnalyzer
    except ImportError as e:
        print(f"Import error in analyze_html: {e}")
        traceback.print_exc()
        return jsonify({"success": False, "error": f"Import error: {e}"}), 500

    html_samples = []

    # Accept multipart/form-data with HTML files
    if request.files:
        files = request.files.getlist("samples")
        for f in files:
            try:
                content = f.read().decode("utf-8")
                if content.strip():
                    html_samples.append(content)
            except Exception:
                # Try latin-1 as fallback
                try:
                    f.seek(0)
                    content = f.read().decode("latin-1")
                    if content.strip():
                        html_samples.append(content)
                except Exception:
                    pass

    # Also accept JSON body with html_samples array
    if not html_samples and request.is_json:
        data = request.get_json()
        html_samples = data.get("html_samples", [])

    if not html_samples:
        return jsonify({
            "error": "No HTML samples provided. Upload files or send html_samples array.",
        }), 400

    if len(html_samples) > 10:
        return jsonify({
            "error": "Maximum 10 samples allowed.",
        }), 400

    try:
        analyzer = HTMLAnalyzer()
        suggestions = analyzer.analyze_multiple(html_samples)

        return jsonify({
            "success": True,
            "suggestions": [s.to_dict() for s in suggestions],
            "sample_count": len(html_samples),
        })
    except Exception as e:
        print(f"Analysis error: {e}")
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": str(e),
        }), 500


@scraping_bp.route("/analyze-accessibility", methods=["POST"])
def analyze_accessibility():
    """
    Fetch and analyze URLs using browser accessibility API.

    Uses agent_browser to fetch pages with accessibility trees,
    then analyzes both HTML structure and accessibility info
    to suggest extraction rules.

    Request JSON:
        {
            "urls": ["https://example.com/page1", ...],  // max 10
            "timeout": 45000,  // optional, per-URL timeout in ms
            "combined": true,  // optional, combine with HTML analysis
            "use_singlefile": false  // optional, flatten with SingleFile for stable rules
        }

    Returns:
        {
            "success": true,
            "samples": [...],  // sample metadata
            "suggestions": [...],  // rule suggestions
            "errors": [...]  // any fetch errors
        }
    """
    import traceback

    try:
        from core.scraping.accessibility_analyzer import AccessibilityAnalyzer
    except ImportError as e:
        print(f"Import error in analyze_accessibility: {e}")
        traceback.print_exc()
        return jsonify({"success": False, "error": f"Import error: {e}"}), 500

    data = request.get_json()
    urls = data.get("urls", [])
    timeout = data.get("timeout", 45000)
    combined = data.get("combined", True)  # Default to combined analysis
    use_singlefile = data.get("use_singlefile", False)  # Optional SingleFile flattening

    if not urls:
        return jsonify({"error": "No URLs provided"}), 400

    if len(urls) > 10:
        return jsonify({"error": "Maximum 10 URLs allowed"}), 400

    try:
        analyzer = AccessibilityAnalyzer()

        # Check if SingleFile is available when requested
        singlefile_available = analyzer.is_singlefile_available()
        if use_singlefile and not singlefile_available:
            return jsonify({
                "success": False,
                "error": "SingleFile CLI not available. Install with: npm install -g single-file-cli",
            }), 400

        # Fetch samples with accessibility trees (and optionally flatten)
        samples, errors = analyzer.fetch_samples(
            urls, timeout=timeout, use_singlefile=use_singlefile
        )

        if not samples:
            return jsonify({
                "success": False,
                "error": "Failed to fetch any samples",
                "errors": errors,
            }), 400

        # Analyze samples
        if combined:
            suggestions = analyzer.analyze_combined(samples, prefer_flattened=use_singlefile)
        else:
            suggestions = analyzer.analyze_accessibility(samples)

        # Close the fetcher
        analyzer.close()

        return jsonify({
            "success": True,
            "samples": [s.to_dict() for s in samples],
            "suggestions": [s.to_dict() for s in suggestions],
            "errors": errors,
            "sample_count": len(samples),
            "suggestion_count": len(suggestions),
            "singlefile_used": use_singlefile and singlefile_available,
        })

    except Exception as e:
        print(f"Accessibility analysis error: {e}")
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": str(e),
        }), 500


@scraping_bp.route("/generate-report", methods=["POST"])
def generate_report():
    """
    Generate a markdown report from scrape job results or analysis data.

    Supports three report types:
    - "job": Job completion report with success/failure stats and issues
    - "analysis": Analysis report with rule suggestions and sample info
    - "errors": Concise error summary for debugging

    Request JSON for job report:
        {
            "type": "job",
            "job": { "id": "...", "created_at": "...", ... },
            "urls": [ { "url": "...", "status": "...", ... }, ... ],
            "results": [ { "url": "...", "data": {...}, ... }, ... ],
            "include_data_preview": true,
            "max_preview_items": 5
        }

    Request JSON for analysis report:
        {
            "type": "analysis",
            "samples": [ { "url": "...", "success": true, ... }, ... ],
            "filtered_result": { "rules": [...], "intent": "...", ... },
            "all_rules_count": 76
        }

    Request JSON for error summary:
        {
            "type": "errors",
            "urls": [ { "url": "...", "status": "failed", "error_type": "...", ... }, ... ]
        }

    Returns:
        {
            "success": true,
            "report": "# Markdown report content...",
            "report_type": "job" | "analysis" | "errors"
        }
    """
    try:
        from core.output.report_generator import ReportGenerator
    except ImportError as e:
        return jsonify({"success": False, "error": f"Import error: {e}"}), 500

    data = request.get_json()
    report_type = data.get("type", "job")

    try:
        generator = ReportGenerator()

        if report_type == "job":
            job = data.get("job", {})
            urls = data.get("urls", [])
            results = data.get("results", [])
            include_preview = data.get("include_data_preview", True)
            max_items = data.get("max_preview_items", 5)

            if not urls:
                return jsonify({"error": "urls required for job report"}), 400

            report = generator.generate_job_report(
                job, urls, results,
                include_data_preview=include_preview,
                max_preview_items=max_items,
            )

        elif report_type == "analysis":
            samples = data.get("samples", [])
            filtered_result = data.get("filtered_result", {})
            all_rules_count = data.get("all_rules_count", 0)

            if not filtered_result:
                return jsonify({"error": "filtered_result required for analysis report"}), 400

            report = generator.generate_analysis_report(
                samples, filtered_result, all_rules_count
            )

        elif report_type == "errors":
            urls = data.get("urls", [])
            if not urls:
                return jsonify({"error": "urls required for error summary"}), 400

            report = generator.generate_error_summary(urls)

        else:
            return jsonify({"error": f"Unknown report type: {report_type}"}), 400

        return jsonify({
            "success": True,
            "report": report,
            "report_type": report_type,
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@scraping_bp.route("/filter-presets", methods=["GET"])
def get_filter_presets():
    """
    Get available content presets for rule filtering.

    Returns:
        {
            "success": true,
            "presets": {
                "articles": "Article content: titles, authors, dates, body text",
                "products": "Product info: names, prices, descriptions, images",
                ...
            }
        }
    """
    try:
        from core.scraping.accessibility_analyzer import CONTENT_PRESETS

        presets = {name: info["description"] for name, info in CONTENT_PRESETS.items()}
        return jsonify({
            "success": True,
            "presets": presets,
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@scraping_bp.route("/filter-rules", methods=["POST"])
def filter_rules():
    """
    Filter rule suggestions based on user intent or preset.

    Supports multiple filtering modes (in priority order):
    1. Preset: Use a predefined content category
    2. Keywords: Match specific keywords
    3. Categories: Filter by content categories
    4. Roles: Filter by ARIA roles
    5. Smart: Auto-detect best filtering strategy (with optional LLM)

    Request JSON:
        {
            "rules": [...],  // Array of rule suggestion objects
            "mode": "smart",  // preset, keywords, categories, roles, or smart
            "intent": "article titles and author names",  // For smart mode
            "preset": "articles",  // For preset mode
            "keywords": ["title", "author"],  // For keywords mode
            "categories": ["content"],  // For categories mode
            "roles": ["heading", "link"],  // For roles mode
            "match_all": false,  // For keywords mode
            "use_llm": false,  // For smart mode, enable LLM fallback
            "max_rules": 20  // Max rules to return
        }

    Returns:
        {
            "success": true,
            "filtered": {
                "rules": [...],
                "intent": "...",
                "preset_used": "articles" or null,
                "llm_used": false,
                "total_rules_before": 76,
                "total_rules_after": 12,
                "filter_time_ms": 5
            }
        }
    """
    import traceback

    try:
        from core.scraping.accessibility_analyzer import (
            AccessibilityAnalyzer,
            AccessibilityRuleSuggestion,
        )
    except ImportError as e:
        return jsonify({"success": False, "error": f"Import error: {e}"}), 500

    data = request.get_json()
    rules_data = data.get("rules", [])
    mode = data.get("mode", "smart")
    max_rules = data.get("max_rules", 20)

    if not rules_data:
        return jsonify({"error": "No rules provided"}), 400

    # Convert rule dicts back to AccessibilityRuleSuggestion objects
    rules = []
    for r in rules_data:
        try:
            rules.append(AccessibilityRuleSuggestion(
                name=r.get("name", ""),
                selector_type=r.get("selector_type", "css"),
                selector_value=r.get("selector_value", ""),
                attribute=r.get("attribute"),
                is_list=r.get("is_list", False),
                confidence=r.get("confidence", 0.0),
                preview=r.get("preview", ""),
                found_in_samples=r.get("found_in_samples", 1),
                category=r.get("category", "general"),
                aria_role=r.get("aria_role"),
                aria_name=r.get("aria_name"),
                ref_id=r.get("ref_id"),
            ))
        except Exception:
            continue

    if not rules:
        return jsonify({"error": "No valid rules could be parsed"}), 400

    try:
        analyzer = AccessibilityAnalyzer()

        if mode == "preset":
            preset_name = data.get("preset", "")
            if not preset_name:
                return jsonify({"error": "preset name required for preset mode"}), 400
            result = analyzer.filter_by_preset(rules, preset_name)

        elif mode == "keywords":
            keywords = data.get("keywords", [])
            if not keywords:
                return jsonify({"error": "keywords required for keywords mode"}), 400
            match_all = data.get("match_all", False)
            result = analyzer.filter_by_keywords(rules, keywords, match_all)

        elif mode == "categories":
            categories = data.get("categories", [])
            if not categories:
                return jsonify({"error": "categories required for categories mode"}), 400
            result = analyzer.filter_by_category(rules, categories)

        elif mode == "roles":
            roles = data.get("roles", [])
            if not roles:
                return jsonify({"error": "roles required for roles mode"}), 400
            result = analyzer.filter_by_role(rules, roles)

        else:  # smart mode (default)
            intent = data.get("intent", "")
            if not intent:
                return jsonify({"error": "intent required for smart mode"}), 400
            use_llm = data.get("use_llm", False)
            result = analyzer.smart_filter(rules, intent, use_llm=use_llm, max_rules=max_rules)

        # Apply max_rules limit
        result.rules = result.rules[:max_rules]
        result.total_rules_after = len(result.rules)

        return jsonify({
            "success": True,
            "filtered": result.to_dict(),
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@scraping_bp.route("/analyze-and-filter", methods=["POST"])
def analyze_and_filter():
    """
    Combined endpoint: fetch samples, analyze, and filter in one call.

    This is the recommended endpoint for non-technical users who want
    to describe what they want and get relevant extraction rules.

    Request JSON:
        {
            "urls": ["https://example.com/page1", ...],
            "intent": "I want article titles and author names",
            "preset": null,  // Optional: use preset instead of intent
            "timeout": 45000,
            "use_singlefile": false,
            "use_llm": false,  // Enable LLM for complex intents
            "max_rules": 15,
            "generate_report": false  // Include markdown report in response
        }

    Returns:
        {
            "success": true,
            "samples": [...],
            "filtered": {
                "rules": [...],
                "intent": "...",
                "preset_used": null,
                "llm_used": false,
                "total_rules_before": 76,
                "total_rules_after": 12
            },
            "errors": [],
            "report": "# Analysis report..."  // Only if generate_report=true
        }
    """
    import traceback

    try:
        from core.scraping.accessibility_analyzer import AccessibilityAnalyzer
    except ImportError as e:
        return jsonify({"success": False, "error": f"Import error: {e}"}), 500

    data = request.get_json()
    urls = data.get("urls", [])
    intent = data.get("intent", "")
    preset = data.get("preset")
    timeout = data.get("timeout", 45000)
    use_singlefile = data.get("use_singlefile", False)
    use_llm = data.get("use_llm", False)
    max_rules = data.get("max_rules", 15)
    generate_report = data.get("generate_report", False)

    if not urls:
        return jsonify({"error": "No URLs provided"}), 400

    if not intent and not preset:
        return jsonify({"error": "Either intent or preset is required"}), 400

    if len(urls) > 10:
        return jsonify({"error": "Maximum 10 URLs allowed"}), 400

    try:
        analyzer = AccessibilityAnalyzer()

        # Fetch and analyze samples
        samples, errors = analyzer.fetch_samples(
            urls, timeout=timeout, use_singlefile=use_singlefile
        )

        if not samples:
            analyzer.close()
            return jsonify({
                "success": False,
                "error": "Failed to fetch any samples",
                "errors": errors,
            }), 400

        # Analyze samples
        suggestions = analyzer.analyze_combined(samples, prefer_flattened=use_singlefile)

        # Filter rules based on intent or preset
        if preset:
            filtered_result = analyzer.filter_by_preset(suggestions, preset)
        else:
            filtered_result = analyzer.smart_filter(
                suggestions, intent, use_llm=use_llm, max_rules=max_rules
            )

        analyzer.close()

        # Build response
        response = {
            "success": True,
            "samples": [s.to_dict() for s in samples],
            "all_suggestions_count": len(suggestions),
            "filtered": filtered_result.to_dict(),
            "errors": errors,
        }

        # Generate markdown report if requested
        if generate_report:
            try:
                from core.output.report_generator import ReportGenerator
                generator = ReportGenerator()
                response["report"] = generator.generate_analysis_report(
                    [s.to_dict() for s in samples],
                    filtered_result.to_dict(),
                    all_rules_count=len(suggestions),
                )
            except Exception as report_error:
                response["report_error"] = str(report_error)

        return jsonify(response)

    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@scraping_bp.route("/fetch-accessibility", methods=["POST"])
def fetch_accessibility():
    """
    Fetch a single URL with accessibility tree (for preview/debugging).

    Request JSON:
        {
            "url": "https://example.com",
            "timeout": 30000,
            "interactive_only": true
        }

    Returns:
        {
            "success": true,
            "url": "...",
            "html_length": 12345,
            "accessibility_tree": "...",
            "element_refs": {...},
            "response_time_ms": 1234
        }
    """
    import traceback

    try:
        from core.scraping.accessibility_analyzer import AccessibilityAnalyzer
    except ImportError as e:
        return jsonify({"success": False, "error": f"Import error: {e}"}), 500

    data = request.get_json()
    url = data.get("url")
    timeout = data.get("timeout", 30000)
    interactive_only = data.get("interactive_only", True)

    if not url:
        return jsonify({"error": "URL is required"}), 400

    try:
        analyzer = AccessibilityAnalyzer()
        samples, errors = analyzer.fetch_samples([url], timeout=timeout)

        if not samples:
            error_msg = errors[0]["error"] if errors else "Unknown error"
            return jsonify({
                "success": False,
                "url": url,
                "error": error_msg,
            }), 400

        sample = samples[0]

        # Filter to interactive elements if requested
        tree = sample.accessibility_tree
        if interactive_only and tree:
            lines = tree.split("\n")
            interactive_lines = [l for l in lines if "@e" in l]
            tree = "\n".join(interactive_lines)

        analyzer.close()

        return jsonify({
            "success": True,
            "url": url,
            "html_length": len(sample.html),
            "accessibility_tree": tree,
            "element_refs": sample.element_refs,
            "element_count": len(sample.element_refs),
            "response_time_ms": sample.response_time_ms,
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({
            "success": False,
            "url": url,
            "error": str(e),
        }), 500


@scraping_bp.route("/capture-network", methods=["POST"])
def capture_network():
    """
    Capture network traffic from a URL to discover API endpoints.

    This intercepts XHR/fetch requests during page load to find JSON APIs,
    GraphQL endpoints, and other data sources that may be easier to scrape
    than parsing the rendered DOM.

    Request JSON:
        {
            "url": "https://example.com",
            "wait_time": 5000,  // Time to wait for network activity (ms)
            "wait_for_idle": true,  // Wait for network to be idle
            "include_bodies": true  // Include response bodies
        }

    Returns:
        {
            "success": true,
            "url": "...",
            "capture_time_ms": 5234,
            "total_requests": 42,
            "total_bytes": 123456,
            "api_endpoints": [
                {
                    "url": "https://api.example.com/v1/data",
                    "method": "GET",
                    "content_type": "application/json",
                    "is_json": true,
                    "has_pagination": true,
                    "data_array_path": "data.items",
                    "data_count": 50
                },
                ...
            ],
            "json_responses": [...],
            "graphql_responses": [...]
        }
    """
    import traceback

    try:
        from core.scraping.network_analyzer import NetworkAnalyzer
    except ImportError as e:
        return jsonify({"success": False, "error": f"Import error: {e}"}), 500

    data = request.get_json()
    url = data.get("url")
    wait_time = data.get("wait_time", 5000)
    wait_for_idle = data.get("wait_for_idle", True)
    include_bodies = data.get("include_bodies", True)

    if not url:
        return jsonify({"error": "URL is required"}), 400

    try:
        analyzer = NetworkAnalyzer()
        result = analyzer.capture(
            url,
            wait_time=wait_time,
            wait_for_idle=wait_for_idle,
            include_bodies=include_bodies,
        )
        analyzer.close()

        return jsonify(result.to_dict())

    except Exception as e:
        traceback.print_exc()
        return jsonify({
            "success": False,
            "url": url,
            "error": str(e),
        }), 500


@scraping_bp.route("/discover-apis", methods=["POST"])
def discover_apis():
    """
    Discover API endpoints from multiple URLs.

    Captures network traffic from multiple sample URLs and aggregates
    discovered API endpoints, ranking them by usefulness.

    Request JSON:
        {
            "urls": ["https://example.com/page1", "https://example.com/page2"],
            "wait_time": 5000,
            "max_urls": 5,
            "generate_report": false  // Include markdown report
        }

    Returns:
        {
            "success": true,
            "urls_analyzed": 2,
            "total_endpoints": 15,
            "unique_endpoints": 8,
            "endpoints": [
                {
                    "url": "https://api.example.com/v1/data",
                    "found_in_urls": 2,
                    "is_json": true,
                    "has_pagination": true,
                    "data_array_path": "results",
                    "avg_data_count": 25
                },
                ...
            ],
            "report": "# API Discovery Report..."  // Only if generate_report=true
        }
    """
    import traceback
    from collections import defaultdict

    try:
        from core.scraping.network_analyzer import NetworkAnalyzer
    except ImportError as e:
        return jsonify({"success": False, "error": f"Import error: {e}"}), 500

    data = request.get_json()
    urls = data.get("urls", [])
    wait_time = data.get("wait_time", 5000)
    max_urls = data.get("max_urls", 5)
    generate_report = data.get("generate_report", False)

    if not urls:
        return jsonify({"error": "URLs are required"}), 400

    urls = urls[:max_urls]

    try:
        analyzer = NetworkAnalyzer()
        all_endpoints = defaultdict(lambda: {
            "count": 0,
            "data_counts": [],
            "endpoint": None,
        })
        errors = []
        total_endpoints = 0

        for url in urls:
            try:
                result = analyzer.capture(url, wait_time=wait_time)
                if result.success:
                    for endpoint in result.api_endpoints:
                        # Use base URL without query params as key
                        base_url = endpoint.url.split("?")[0]
                        all_endpoints[base_url]["count"] += 1
                        all_endpoints[base_url]["data_counts"].append(endpoint.data_count)
                        if all_endpoints[base_url]["endpoint"] is None:
                            all_endpoints[base_url]["endpoint"] = endpoint
                        total_endpoints += 1
                else:
                    errors.append({"url": url, "error": result.error})
            except Exception as e:
                errors.append({"url": url, "error": str(e)})

        analyzer.close()

        # Build aggregated endpoint list
        aggregated = []
        for base_url, info in all_endpoints.items():
            endpoint = info["endpoint"]
            if endpoint:
                aggregated.append({
                    "url": base_url,
                    "full_url": endpoint.url,
                    "method": endpoint.method,
                    "content_type": endpoint.content_type,
                    "is_json": endpoint.is_json,
                    "is_graphql": endpoint.is_graphql,
                    "has_pagination": endpoint.has_pagination,
                    "data_array_path": endpoint.data_array_path,
                    "found_in_urls": info["count"],
                    "avg_data_count": sum(info["data_counts"]) / len(info["data_counts"]) if info["data_counts"] else 0,
                    "sample_data_keys": endpoint.sample_data_keys,
                })

        # Sort by frequency and data count
        aggregated.sort(key=lambda x: (x["found_in_urls"], x["avg_data_count"]), reverse=True)

        response = {
            "success": True,
            "urls_analyzed": len(urls),
            "total_endpoints": total_endpoints,
            "unique_endpoints": len(aggregated),
            "endpoints": aggregated,
            "errors": errors,
        }

        # Generate report if requested
        if generate_report:
            report = _generate_api_discovery_report(urls, aggregated, errors)
            response["report"] = report

        return jsonify(response)

    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


def _generate_api_discovery_report(
    urls: list,
    endpoints: list,
    errors: list,
) -> str:
    """Generate markdown report for API discovery."""
    from datetime import datetime

    lines = [
        "# API discovery report",
        "",
        f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"**URLs analyzed:** {len(urls)}",
        f"**Unique endpoints found:** {len(endpoints)}",
        "",
        "---",
        "",
        "## Discovered API endpoints",
        "",
    ]

    if not endpoints:
        lines.append("*No API endpoints discovered.*")
    else:
        # Top endpoints
        lines.append("### Top endpoints (by frequency and data volume)")
        lines.append("")
        lines.append("| Endpoint | Type | Found in | Avg items | Pagination |")
        lines.append("|----------|------|----------|-----------|------------|")

        for ep in endpoints[:15]:
            ep_type = "GraphQL" if ep["is_graphql"] else "JSON" if ep["is_json"] else "Other"
            pagination = "✓" if ep["has_pagination"] else "—"
            url_display = ep["url"]
            if len(url_display) > 50:
                url_display = url_display[:47] + "..."
            lines.append(
                f"| `{url_display}` | {ep_type} | {ep['found_in_urls']} URLs | {ep['avg_data_count']:.0f} | {pagination} |"
            )

        if len(endpoints) > 15:
            lines.append(f"\n*... and {len(endpoints) - 15} more endpoints*")

        # Detailed info for top 5
        lines.append("")
        lines.append("### Endpoint details")
        lines.append("")

        for i, ep in enumerate(endpoints[:5]):
            lines.append(f"#### {i + 1}. `{ep['url']}`")
            lines.append("")
            lines.append(f"- **Type:** {'GraphQL' if ep['is_graphql'] else 'JSON API' if ep['is_json'] else 'Other'}")
            lines.append(f"- **Content-Type:** `{ep['content_type']}`")
            lines.append(f"- **Data path:** `{ep['data_array_path'] or 'N/A'}`")
            lines.append(f"- **Avg items:** {ep['avg_data_count']:.0f}")
            lines.append(f"- **Has pagination:** {'Yes' if ep['has_pagination'] else 'No'}")

            if ep["sample_data_keys"]:
                keys = ", ".join(f"`{k}`" for k in ep["sample_data_keys"][:10])
                lines.append(f"- **Sample keys:** {keys}")

            lines.append("")

    # Errors section
    if errors:
        lines.append("## Errors")
        lines.append("")
        for err in errors:
            lines.append(f"- `{err['url']}`: {err['error']}")
        lines.append("")

    # Next steps
    lines.append("---")
    lines.append("")
    lines.append("## Next steps")
    lines.append("")
    lines.append("1. **Test endpoints directly** - Try calling the discovered APIs in your browser or with curl")
    lines.append("2. **Check authentication** - Some endpoints may require cookies or auth headers")
    lines.append("3. **Look for pagination** - If an endpoint has pagination, you may need to loop through pages")
    lines.append("4. **Use the data path** - The `data_array_path` tells you where the main data array is in the response")
    lines.append("")

    return "\n".join(lines)
