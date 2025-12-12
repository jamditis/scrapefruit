"""Extraction modules for parsing HTML content."""

from core.scraping.extractors.css_extractor import CSSExtractor
from core.scraping.extractors.xpath_extractor import XPathExtractor

__all__ = ["CSSExtractor", "XPathExtractor"]
