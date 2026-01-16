"""Extraction modules for parsing HTML content and images."""

from core.scraping.extractors.base import BaseExtractor, ExtractionResult
from core.scraping.extractors.css_extractor import CSSExtractor
from core.scraping.extractors.xpath_extractor import XPathExtractor
from core.scraping.extractors.vision_extractor import (
    VisionExtractor,
    VisionExtractionResult,
    TextRegion,
    get_vision_extractor,
)

__all__ = [
    # Base classes
    "BaseExtractor",
    "ExtractionResult",
    # Concrete extractors
    "CSSExtractor",
    "XPathExtractor",
    "VisionExtractor",
    "VisionExtractionResult",
    "TextRegion",
    "get_vision_extractor",
]
