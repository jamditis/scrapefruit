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
        result = get_engine().fetch_page(url, force_playwright=use_playwright)
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
    Uses SingleFile CLI if available, falls back to Playwright/HTTP.
    Returns the HTML content directly for the analyzer.
    """
    import subprocess
    import shutil
    import traceback

    data = request.get_json()
    urls = data.get("urls", [])

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

            # Try SingleFile first if available
            if singlefile_path:
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

            # Fall back to scraping engine
            if not html:
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
        "error_count": len(errors)
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
