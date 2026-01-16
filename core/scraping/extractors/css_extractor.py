"""CSS selector-based extraction."""

from typing import Optional, List, Any
from lxml import html
from lxml.cssselect import CSSSelector

from core.scraping.extractors.base import BaseExtractor


class CSSExtractor(BaseExtractor):
    """Extract data from HTML using CSS selectors."""

    METHOD_NAME = "css"

    def extract_one(
        self,
        html_content: str,
        selector: str,
        attribute: Optional[str] = None,
    ) -> Optional[str]:
        """
        Extract the first matching element.

        Args:
            html_content: HTML string to parse
            selector: CSS selector
            attribute: Element attribute to extract (None = text content)

        Returns:
            Extracted value or None
        """
        try:
            tree = html.fromstring(html_content)
            css_selector = CSSSelector(selector)
            elements = css_selector(tree)

            if not elements:
                return None

            element = elements[0]
            return self._extract_value(element, attribute)

        except Exception as e:
            return None

    def extract_all(
        self,
        html_content: str,
        selector: str,
        attribute: Optional[str] = None,
    ) -> List[str]:
        """
        Extract all matching elements.

        Args:
            html_content: HTML string to parse
            selector: CSS selector
            attribute: Element attribute to extract (None = text content)

        Returns:
            List of extracted values
        """
        try:
            tree = html.fromstring(html_content)
            css_selector = CSSSelector(selector)
            elements = css_selector(tree)

            results = []
            for element in elements:
                value = self._extract_value(element, attribute)
                if value:
                    results.append(value)

            return results

        except Exception:
            return []

    def _extract_value(self, element, attribute: Optional[str]) -> Optional[str]:
        """Extract value from an element."""
        if attribute:
            value = element.get(attribute)
        else:
            # Get text content
            value = element.text_content()

        if value:
            return value.strip()
        return None

    def exists(self, html_content: str, selector: str) -> bool:
        """Check if selector matches any elements."""
        try:
            tree = html.fromstring(html_content)
            css_selector = CSSSelector(selector)
            elements = css_selector(tree)
            return len(elements) > 0
        except Exception:
            return False

    def count(self, html_content: str, selector: str) -> int:
        """Count matching elements."""
        try:
            tree = html.fromstring(html_content)
            css_selector = CSSSelector(selector)
            elements = css_selector(tree)
            return len(elements)
        except Exception:
            return 0


class MetaExtractor:
    """Extract meta tag content."""

    def extract(self, html_content: str, name: str) -> Optional[str]:
        """
        Extract meta tag content by name or property.

        Args:
            html_content: HTML string
            name: Meta name or property value

        Returns:
            Content value or None
        """
        css = CSSExtractor()

        # Try meta name
        value = css.extract_one(html_content, f'meta[name="{name}"]', "content")
        if value:
            return value

        # Try meta property (Open Graph)
        value = css.extract_one(html_content, f'meta[property="{name}"]', "content")
        if value:
            return value

        # Try itemprop
        value = css.extract_one(html_content, f'[itemprop="{name}"]', "content")
        if value:
            return value

        return None

    def extract_all_meta(self, html_content: str) -> dict:
        """Extract all meta tags as a dictionary."""
        try:
            tree = html.fromstring(html_content)
            meta_tags = tree.cssselect("meta")

            result = {}
            for meta in meta_tags:
                name = meta.get("name") or meta.get("property")
                content = meta.get("content")
                if name and content:
                    result[name] = content

            return result
        except Exception:
            return {}
