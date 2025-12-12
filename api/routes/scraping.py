"""Scraping action endpoints for preview and testing."""

from flask import Blueprint, request, jsonify

from core.scraping.engine import ScrapingEngine

scraping_bp = Blueprint("scraping", __name__)
engine = ScrapingEngine()


@scraping_bp.route("/preview", methods=["POST"])
def preview_scrape():
    """Preview scrape a single URL with provided rules."""
    data = request.get_json()
    url = data.get("url")
    rules = data.get("rules", [])

    if not url:
        return jsonify({"error": "URL is required"}), 400

    try:
        result = engine.scrape_url(url, rules)
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
        html_result = engine.fetch_page(url)
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
        result = engine.fetch_page(url, force_playwright=use_playwright)
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
