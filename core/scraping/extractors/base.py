"""Abstract base classes for extractors.

This module defines the interfaces that all extractors must implement,
enabling polymorphism, better type safety, and easier testing.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any


@dataclass
class ExtractionResult:
    """
    Result from an extraction operation.

    Provides a consistent structure for all extraction results,
    whether from CSS, XPath, or vision-based extraction.
    """

    success: bool
    value: Optional[str] = None
    values: List[str] = field(default_factory=list)
    error: Optional[str] = None
    selector_used: str = ""
    method: str = ""

    @property
    def is_single(self) -> bool:
        """Check if this is a single-value result."""
        return self.value is not None

    @property
    def is_multiple(self) -> bool:
        """Check if this is a multi-value result."""
        return len(self.values) > 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary for serialization."""
        return {
            "success": self.success,
            "value": self.value,
            "values": self.values,
            "error": self.error,
            "selector_used": self.selector_used,
            "method": self.method,
        }


class BaseExtractor(ABC):
    """
    Abstract base class for all extractors.

    Extractors are responsible for extracting specific data from HTML content
    using various methods (CSS selectors, XPath, OCR, etc.).

    All extractors must implement:
    - extract_one(): Extract single value
    - extract_all(): Extract all matching values
    """

    # Subclasses should override this with their method name
    METHOD_NAME: str = "base"

    @abstractmethod
    def extract_one(
        self,
        html_content: str,
        selector: str,
        attribute: Optional[str] = None,
    ) -> Optional[str]:
        """
        Extract the first matching value.

        Args:
            html_content: HTML string to parse
            selector: Selector expression (CSS, XPath, etc.)
            attribute: Element attribute to extract (None = text content)

        Returns:
            Extracted value or None if not found
        """
        pass

    @abstractmethod
    def extract_all(
        self,
        html_content: str,
        selector: str,
        attribute: Optional[str] = None,
    ) -> List[str]:
        """
        Extract all matching values.

        Args:
            html_content: HTML string to parse
            selector: Selector expression (CSS, XPath, etc.)
            attribute: Element attribute to extract (None = text content)

        Returns:
            List of extracted values (empty list if none found)
        """
        pass

    def exists(self, html_content: str, selector: str) -> bool:
        """
        Check if selector matches any elements.

        Args:
            html_content: HTML string to parse
            selector: Selector expression

        Returns:
            True if at least one element matches
        """
        return self.extract_one(html_content, selector) is not None

    def count(self, html_content: str, selector: str) -> int:
        """
        Count matching elements.

        Args:
            html_content: HTML string to parse
            selector: Selector expression

        Returns:
            Number of matching elements
        """
        return len(self.extract_all(html_content, selector))

    def extract_one_safe(
        self,
        html_content: str,
        selector: str,
        attribute: Optional[str] = None,
    ) -> ExtractionResult:
        """
        Extract single value with full result metadata.

        Unlike extract_one(), this method never raises exceptions
        and provides detailed information about the extraction attempt.

        Args:
            html_content: HTML string to parse
            selector: Selector expression
            attribute: Element attribute to extract

        Returns:
            ExtractionResult with value and metadata
        """
        try:
            value = self.extract_one(html_content, selector, attribute)
            return ExtractionResult(
                success=value is not None,
                value=value,
                selector_used=selector,
                method=self.METHOD_NAME,
            )
        except Exception as e:
            return ExtractionResult(
                success=False,
                error=str(e),
                selector_used=selector,
                method=self.METHOD_NAME,
            )

    def extract_all_safe(
        self,
        html_content: str,
        selector: str,
        attribute: Optional[str] = None,
    ) -> ExtractionResult:
        """
        Extract all values with full result metadata.

        Unlike extract_all(), this method never raises exceptions
        and provides detailed information about the extraction attempt.

        Args:
            html_content: HTML string to parse
            selector: Selector expression
            attribute: Element attribute to extract

        Returns:
            ExtractionResult with values and metadata
        """
        try:
            values = self.extract_all(html_content, selector, attribute)
            return ExtractionResult(
                success=len(values) > 0,
                values=values,
                selector_used=selector,
                method=self.METHOD_NAME,
            )
        except Exception as e:
            return ExtractionResult(
                success=False,
                error=str(e),
                selector_used=selector,
                method=self.METHOD_NAME,
            )
