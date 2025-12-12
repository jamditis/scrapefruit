"""XPath-based extraction."""

from typing import Optional, List
from lxml import html


class XPathExtractor:
    """Extract data from HTML using XPath expressions."""

    def extract_one(
        self,
        html_content: str,
        xpath: str,
        attribute: Optional[str] = None,
    ) -> Optional[str]:
        """
        Extract the first matching element.

        Args:
            html_content: HTML string to parse
            xpath: XPath expression
            attribute: Element attribute to extract (None = text content)

        Returns:
            Extracted value or None
        """
        try:
            tree = html.fromstring(html_content)
            elements = tree.xpath(xpath)

            if not elements:
                return None

            element = elements[0]
            return self._extract_value(element, attribute)

        except Exception:
            return None

    def extract_all(
        self,
        html_content: str,
        xpath: str,
        attribute: Optional[str] = None,
    ) -> List[str]:
        """
        Extract all matching elements.

        Args:
            html_content: HTML string to parse
            xpath: XPath expression
            attribute: Element attribute to extract (None = text content)

        Returns:
            List of extracted values
        """
        try:
            tree = html.fromstring(html_content)
            elements = tree.xpath(xpath)

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
        # If element is already a string (from text() or @attr xpath)
        if isinstance(element, str):
            return element.strip() if element.strip() else None

        if attribute:
            value = element.get(attribute)
        else:
            # Get text content
            value = element.text_content() if hasattr(element, "text_content") else str(element)

        if value:
            return value.strip()
        return None

    def exists(self, html_content: str, xpath: str) -> bool:
        """Check if XPath matches any elements."""
        try:
            tree = html.fromstring(html_content)
            elements = tree.xpath(xpath)
            return len(elements) > 0
        except Exception:
            return False

    def count(self, html_content: str, xpath: str) -> int:
        """Count matching elements."""
        try:
            tree = html.fromstring(html_content)
            elements = tree.xpath(xpath)
            return len(elements)
        except Exception:
            return 0
