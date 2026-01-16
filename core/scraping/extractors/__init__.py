"""Extraction modules for parsing HTML content and images."""

from core.scraping.extractors.css_extractor import CSSExtractor
from core.scraping.extractors.xpath_extractor import XPathExtractor
from core.scraping.extractors.vision_extractor import (
    VisionExtractor,
    VisionExtractionResult,
    get_vision_extractor,
)

__all__ = [
    "CSSExtractor",
    "XPathExtractor",
    "VisionExtractor",
    "VisionExtractionResult",
    "get_vision_extractor",
]
