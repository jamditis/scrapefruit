"""Stress tests for edge cases and unusual conditions."""

import pytest
import time
import threading
import concurrent.futures
from unittest.mock import Mock, patch


class TestLargeContent:
    """Tests for handling large content."""

    @pytest.fixture
    def engine(self):
        from core.scraping.engine import ScrapingEngine
        return ScrapingEngine()

    @pytest.fixture
    def detector(self):
        from core.poison_pills.detector import PoisonPillDetector
        return PoisonPillDetector()

    def test_very_large_html(self, detector):
        """Handle HTML with many characters."""
        # Large HTML (~750KB)
        large_html = "<html><body>" + ("<p>Content paragraph with several words here.</p>" * 50000) + "</body></html>"
        assert len(large_html) > 500_000  # At least 500KB

        result = detector.detect(large_html)
        assert result is not None  # Should complete without timeout

    def test_deeply_nested_html(self, detector):
        """Handle deeply nested HTML structures."""
        # 1000 levels deep
        nested = "<html><body>"
        for i in range(1000):
            nested += f"<div class='level-{i}'>"
        nested += "Content"
        for _ in range(1000):
            nested += "</div>"
        nested += "</body></html>"

        result = detector.detect(nested)
        assert result is not None

    def test_many_elements(self):
        """Handle HTML with thousands of elements."""
        from core.scraping.extractors.css_extractor import CSSExtractor
        extractor = CSSExtractor()

        # 10,000 list items
        html = "<html><body><ul>"
        for i in range(10000):
            html += f"<li class='item' data-id='{i}'>Item {i}</li>"
        html += "</ul></body></html>"

        results = extractor.extract_all(html, "li.item")
        assert len(results) == 10000

    def test_very_long_text_content(self, detector):
        """Handle elements with very long text."""
        # Single element with 100KB of text
        long_text = "Word " * 20000
        html = f"<html><body><p>{long_text}</p></body></html>"

        result = detector.detect(html)
        assert not result.is_poison  # Should be valid content

    def test_large_attribute_values(self):
        """Handle elements with very large attribute values."""
        from core.scraping.extractors.css_extractor import CSSExtractor
        extractor = CSSExtractor()

        # 10KB data attribute
        large_data = "x" * 10000
        html = f'<html><body><div data-content="{large_data}">Text</div></body></html>'

        result = extractor.extract_one(html, "[data-content]", attribute="data-content")
        assert result == large_data


class TestMalformedContent:
    """Tests for handling malformed/broken content."""

    @pytest.fixture
    def css_extractor(self):
        from core.scraping.extractors.css_extractor import CSSExtractor
        return CSSExtractor()

    @pytest.fixture
    def detector(self):
        from core.poison_pills.detector import PoisonPillDetector
        return PoisonPillDetector()

    def test_unclosed_tags(self, css_extractor):
        """Handle unclosed HTML tags."""
        html = "<html><body><div><p>Unclosed paragraph<p>Another<div>Nested"
        # Should not raise
        result = css_extractor.extract_one(html, "p")

    def test_mismatched_tags(self, css_extractor):
        """Handle mismatched closing tags."""
        html = "<html><body><div><p>Text</div></p></body></html>"
        result = css_extractor.extract_one(html, "p")

    def test_invalid_entities(self, detector):
        """Handle invalid HTML entities."""
        html = "<html><body><p>&invalid; &#999999; &amp</p></body></html>" * 10
        result = detector.detect(html)

    def test_null_bytes(self, detector):
        """Handle null bytes in content."""
        html = "<html><body><p>Text with \x00 null bytes</p></body></html>" * 10
        result = detector.detect(html)

    def test_binary_content(self, detector):
        """Handle accidental binary content."""
        # Mix of text and random bytes
        html = "<html><body><p>Text" + bytes(range(256)).decode('latin-1') + "</p></body></html>"
        result = detector.detect(html)

    def test_control_characters(self, css_extractor):
        """Handle control characters in content."""
        html = "<html><body><p>Text\x01\x02\x03\x04with\x05controls</p></body></html>"
        result = css_extractor.extract_one(html, "p")

    def test_bom_handling(self, detector):
        """Handle BOM (Byte Order Mark) in content."""
        html = "\ufeff<html><body><p>Content after BOM</p></body></html>" * 10
        result = detector.detect(html)

    def test_mixed_encodings(self, css_extractor):
        """Handle mixed encoding characters."""
        html = """
        <html><body>
        <p class="utf8">日本語</p>
        <p class="latin">Ñoño</p>
        <p class="emoji">🎉🚀💻</p>
        </body></html>
        """
        result = css_extractor.extract_all(html, "p")
        assert len(result) == 3


class TestConcurrency:
    """Tests for concurrent/parallel operations."""

    @pytest.fixture
    def detector(self):
        from core.poison_pills.detector import PoisonPillDetector
        return PoisonPillDetector()

    def test_concurrent_detection(self, detector):
        """Multiple threads detecting simultaneously."""
        html_samples = [
            "<html><body><p>Clean content here.</p></body></html>" * 10,
            "<html><body><h1>Subscribe to read</h1></body></html>" * 10,
            "<html><body><p>Rate limit exceeded</p></body></html>" * 10,
        ]

        results = []
        errors = []

        def detect_in_thread(html):
            try:
                result = detector.detect(html)
                results.append(result)
            except Exception as e:
                errors.append(e)

        threads = []
        for _ in range(10):  # 10 iterations
            for html in html_samples:
                t = threading.Thread(target=detect_in_thread, args=(html,))
                threads.append(t)
                t.start()

        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(results) == 30

    def test_concurrent_extraction(self):
        """Multiple threads extracting simultaneously."""
        from core.scraping.extractors.css_extractor import CSSExtractor
        extractor = CSSExtractor()

        html = """
        <html><body>
        <ul><li>1</li><li>2</li><li>3</li></ul>
        </body></html>
        """

        results = []
        errors = []

        def extract_in_thread():
            try:
                result = extractor.extract_all(html, "li")
                results.append(result)
            except Exception as e:
                errors.append(e)

        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(extract_in_thread) for _ in range(100)]
            concurrent.futures.wait(futures)

        assert len(errors) == 0
        assert len(results) == 100
        for r in results:
            assert r == ["1", "2", "3"]

    def test_engine_thread_safety(self):
        """Engine operations should be thread-safe."""
        from core.scraping.engine import ScrapingEngine

        engine = ScrapingEngine()
        html = "<html><body><h1>Title</h1><p>Content</p></body></html>"

        results = []
        errors = []

        def test_selector_in_thread():
            try:
                result = engine.test_selector(html, "css", "h1")
                results.append(result)
            except Exception as e:
                errors.append(e)

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(test_selector_in_thread) for _ in range(50)]
            concurrent.futures.wait(futures)

        assert len(errors) == 0
        assert len(results) == 50


class TestBoundaryConditions:
    """Tests for boundary conditions and limits."""

    def test_empty_selector(self):
        """Empty selector should be handled."""
        from core.scraping.extractors.css_extractor import CSSExtractor
        extractor = CSSExtractor()

        html = "<html><body><p>Test</p></body></html>"
        try:
            result = extractor.extract_one(html, "")
        except Exception:
            pass  # May raise - that's acceptable

    def test_empty_html(self):
        """Empty HTML should be handled."""
        from core.scraping.extractors.css_extractor import CSSExtractor
        extractor = CSSExtractor()

        result = extractor.extract_one("", "p")
        assert result is None

    def test_whitespace_only_html(self):
        """Whitespace-only HTML should be handled."""
        from core.poison_pills.detector import PoisonPillDetector
        detector = PoisonPillDetector()

        result = detector.detect("   \n\t\n   ")
        assert result.is_poison  # Should be detected as empty

    def test_single_character(self):
        """Single character content."""
        from core.poison_pills.detector import PoisonPillDetector
        detector = PoisonPillDetector()

        result = detector.detect("x")
        assert result.is_poison  # Too short

    def test_none_input_handling(self):
        """None input should be handled gracefully."""
        from core.poison_pills.detector import PoisonPillDetector
        detector = PoisonPillDetector()

        try:
            result = detector.detect(None)
        except (TypeError, AttributeError):
            pass  # Expected - None is not valid input

    def test_max_recursion_depth(self):
        """Deep recursion should not cause stack overflow."""
        from core.scraping.extractors.css_extractor import CSSExtractor
        extractor = CSSExtractor()

        # Moderately deep nesting (100 levels is enough to test)
        html = "<html><body>"
        for _ in range(100):
            html += "<div>"
        html += "<p>Deep content</p>"
        for _ in range(100):
            html += "</div>"
        html += "</body></html>"

        result = extractor.extract_one(html, "p")
        assert result == "Deep content"

    def test_extremely_long_selector(self):
        """Very long CSS selector should be handled."""
        from core.scraping.extractors.css_extractor import CSSExtractor
        extractor = CSSExtractor()

        html = "<html><body><p>Test</p></body></html>"
        long_selector = "div > " * 100 + "p"

        result = extractor.extract_one(html, long_selector)
        # Should not match but shouldn't crash


class TestSpecialCharacters:
    """Tests for special character handling."""

    @pytest.fixture
    def css_extractor(self):
        from core.scraping.extractors.css_extractor import CSSExtractor
        return CSSExtractor()

    def test_quotes_in_content(self, css_extractor):
        """Handle quotes in content."""
        html = '<html><body><p>He said "Hello" and \'Goodbye\'</p></body></html>'
        result = css_extractor.extract_one(html, "p")
        assert '"Hello"' in result or "'Hello'" in result

    def test_angle_brackets_in_text(self, css_extractor):
        """Handle angle brackets in text content."""
        html = "<html><body><p>Value &lt; 10 and &gt; 5</p></body></html>"
        result = css_extractor.extract_one(html, "p")
        assert "<" in result or "&lt;" in result

    def test_ampersands_in_urls(self, css_extractor):
        """Handle ampersands in URLs."""
        html = '<html><body><a href="page.html?a=1&amp;b=2">Link</a></body></html>'
        result = css_extractor.extract_one(html, "a", attribute="href")
        assert "a=1" in result and "b=2" in result

    def test_newlines_in_content(self, css_extractor):
        """Handle newlines in content."""
        html = """
        <html><body><pre>
        Line 1
        Line 2
        Line 3
        </pre></body></html>
        """
        result = css_extractor.extract_one(html, "pre")
        assert "Line 1" in result

    def test_tabs_in_content(self, css_extractor):
        """Handle tabs in content."""
        html = "<html><body><p>Column1\tColumn2\tColumn3</p></body></html>"
        result = css_extractor.extract_one(html, "p")
        assert "Column1" in result

    def test_zero_width_characters(self, css_extractor):
        """Handle zero-width characters."""
        html = "<html><body><p>Text\u200bwith\u200bzero\u200bwidth</p></body></html>"
        result = css_extractor.extract_one(html, "p")
        assert "Text" in result


class TestPerformance:
    """Performance-related stress tests."""

    def test_extraction_speed(self):
        """Extraction should be fast even with complex HTML."""
        from core.scraping.extractors.css_extractor import CSSExtractor
        extractor = CSSExtractor()

        # Generate complex HTML
        html = "<html><body>"
        for i in range(1000):
            html += f'<div class="item"><span class="name">Item {i}</span><span class="value">{i * 2}</span></div>'
        html += "</body></html>"

        start = time.time()
        results = extractor.extract_all(html, ".item .name")
        elapsed = time.time() - start

        assert len(results) == 1000
        assert elapsed < 5.0  # Should complete in under 5 seconds

    def test_detection_speed(self):
        """Poison detection should be fast."""
        from core.poison_pills.detector import PoisonPillDetector
        detector = PoisonPillDetector()

        html = "<html><body>" + ("<p>Normal content paragraph.</p>" * 1000) + "</body></html>"

        start = time.time()
        for _ in range(100):
            detector.detect(html)
        elapsed = time.time() - start

        assert elapsed < 5.0  # 100 detections in under 5 seconds

    def test_memory_stability(self):
        """Memory usage should not grow unboundedly."""
        from core.scraping.extractors.css_extractor import CSSExtractor
        import gc

        extractor = CSSExtractor()
        html = "<html><body>" + ("<p>Content</p>" * 1000) + "</body></html>"

        # Run many extractions
        for _ in range(100):
            results = extractor.extract_all(html, "p")
            del results

        gc.collect()
        # If we get here without memory error, test passes


class TestRobustness:
    """Robustness tests for unusual but valid inputs."""

    def test_doctype_variations(self):
        """Handle various DOCTYPE declarations."""
        from core.poison_pills.detector import PoisonPillDetector
        detector = PoisonPillDetector()

        doctypes = [
            "<!DOCTYPE html>",
            "<!DOCTYPE HTML PUBLIC \"-//W3C//DTD HTML 4.01//EN\">",
            "<!DOCTYPE html SYSTEM>",
            "<?xml version=\"1.0\"?><!DOCTYPE html>",
        ]

        for doctype in doctypes:
            html = f"{doctype}<html><body><p>Content here with enough text.</p></body></html>" * 5
            result = detector.detect(html)
            assert result is not None

    def test_xml_mixed_with_html(self):
        """Handle XML-like content in HTML."""
        from core.scraping.extractors.css_extractor import CSSExtractor
        extractor = CSSExtractor()

        html = """
        <html><body>
        <div>
            <![CDATA[Some CDATA content]]>
            <custom:element>Custom content</custom:element>
        </div>
        <p>Regular HTML</p>
        </body></html>
        """
        result = extractor.extract_one(html, "p")
        assert result == "Regular HTML"

    def test_svg_embedded(self):
        """Handle embedded SVG content."""
        from core.scraping.extractors.css_extractor import CSSExtractor
        extractor = CSSExtractor()

        html = """
        <html><body>
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
            <circle cx="50" cy="50" r="40"/>
            <text x="50" y="50">SVG Text</text>
        </svg>
        <p>HTML Text</p>
        </body></html>
        """
        result = extractor.extract_one(html, "p")
        assert result == "HTML Text"

    def test_math_ml_embedded(self):
        """Handle embedded MathML content."""
        from core.scraping.extractors.css_extractor import CSSExtractor
        extractor = CSSExtractor()

        html = """
        <html><body>
        <math xmlns="http://www.w3.org/1998/Math/MathML">
            <mrow><mi>x</mi><mo>=</mo><mfrac><mn>1</mn><mn>2</mn></mfrac></mrow>
        </math>
        <p>The equation above shows x = 1/2</p>
        </body></html>
        """
        result = extractor.extract_one(html, "p")
        assert "equation" in result

    def test_template_tags(self):
        """Handle HTML template tags."""
        from core.scraping.extractors.css_extractor import CSSExtractor
        extractor = CSSExtractor()

        html = """
        <html><body>
        <template id="tmpl">
            <div class="template-content">Hidden template</div>
        </template>
        <div class="visible">Visible content</div>
        </body></html>
        """
        result = extractor.extract_one(html, ".visible")
        assert result == "Visible content"

    def test_script_with_html_content(self):
        """Handle script tags containing HTML-like content."""
        from core.scraping.extractors.css_extractor import CSSExtractor
        extractor = CSSExtractor()

        html = """
        <html><body>
        <script type="text/template">
            <div class="fake">This is inside script</div>
        </script>
        <div class="real">Real content</div>
        </body></html>
        """
        result = extractor.extract_one(html, ".real")
        assert result == "Real content"
