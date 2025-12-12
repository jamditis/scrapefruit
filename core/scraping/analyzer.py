"""HTML Analyzer - Detect patterns and suggest extraction rules."""

from dataclasses import dataclass, asdict
from typing import List, Optional, Dict, Any
import re
from collections import Counter

import lxml.html
from lxml.cssselect import CSSSelector


@dataclass
class RuleSuggestion:
    """A suggested extraction rule."""
    name: str
    selector_type: str  # "css" or "xpath"
    selector_value: str
    attribute: Optional[str] = None
    is_list: bool = False
    confidence: float = 0.0
    preview: str = ""
    found_in_samples: int = 1
    category: str = "general"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class HTMLAnalyzer:
    """Analyze HTML to suggest extraction rules."""

    # Semantic element checks: (field_name, selector, attribute, category, base_confidence)
    SEMANTIC_CHECKS = [
        # Titles
        ("title", "h1", None, "title", 0.95),
        ("subtitle", "h2", None, "title", 0.7),
        ("page_title", "title", None, "meta", 0.9),

        # Content
        ("content", "article", None, "content", 0.85),
        ("content", "main", None, "content", 0.8),
        ("content", "[itemprop='articleBody']", None, "content", 0.95),

        # Author/Date
        ("author", "[itemprop='author']", None, "attribution", 0.95),
        ("author", "[rel='author']", None, "attribution", 0.9),
        ("date", "time", "datetime", "attribution", 0.9),
        ("date", "[itemprop='datePublished']", "content", "attribution", 0.95),
        ("date", "[itemprop='datePublished']", None, "attribution", 0.9),

        # Media
        ("image", "[itemprop='image']", "src", "media", 0.9),
        ("image", "img.main-image", "src", "media", 0.85),
        ("image", "img.featured", "src", "media", 0.85),
        ("video", "video source", "src", "media", 0.9),

        # E-commerce
        ("price", "[itemprop='price']", "content", "ecommerce", 0.95),
        ("price", "[itemprop='price']", None, "ecommerce", 0.9),
        ("sku", "[itemprop='sku']", None, "ecommerce", 0.9),
        ("brand", "[itemprop='brand']", None, "ecommerce", 0.9),
        ("rating", "[itemprop='ratingValue']", "content", "ecommerce", 0.9),

        # Description
        ("description", "[itemprop='description']", None, "content", 0.9),
    ]

    # Common class patterns to search for
    CLASS_PATTERNS = [
        # (regex pattern for class, field name, category, confidence)
        (r"price|cost|amount", "price", "ecommerce", 0.8),
        (r"title|headline|heading", "title", "title", 0.75),
        (r"desc|description|summary|excerpt", "description", "content", 0.75),
        (r"author|byline|writer", "author", "attribution", 0.8),
        (r"date|time|published|posted", "date", "attribution", 0.75),
        (r"image|photo|thumbnail|img", "image", "media", 0.7),
        (r"content|body|text|article", "content", "content", 0.7),
        (r"rating|stars|score", "rating", "ecommerce", 0.75),
        (r"category|tag|label", "category", "meta", 0.7),
        (r"link|url|href", "link", "navigation", 0.65),
    ]

    def __init__(self):
        pass

    def analyze(self, html: str) -> List[RuleSuggestion]:
        """Analyze a single HTML document and return suggested rules."""
        try:
            tree = lxml.html.fromstring(html)
        except Exception:
            return []

        suggestions = []

        # 1. Check semantic elements
        suggestions.extend(self._check_semantic_elements(tree))

        # 2. Check meta tags
        suggestions.extend(self._check_meta_tags(tree))

        # 3. Scan for common class patterns
        suggestions.extend(self._scan_class_patterns(tree))

        # 4. Detect repeated structures (lists)
        suggestions.extend(self._detect_repeated_structures(tree))

        # 5. Check data attributes
        suggestions.extend(self._check_data_attributes(tree))

        # Deduplicate and rank
        return self._deduplicate_suggestions(suggestions)

    def analyze_multiple(self, html_samples: List[str]) -> List[RuleSuggestion]:
        """Analyze multiple HTML samples and return rules that work across all."""
        if not html_samples:
            return []

        if len(html_samples) == 1:
            return self.analyze(html_samples[0])

        # Analyze each sample
        all_suggestions: List[List[RuleSuggestion]] = []
        for html in html_samples:
            all_suggestions.append(self.analyze(html))

        # Find suggestions that appear in multiple samples
        # Key by (name, selector_value)
        suggestion_counts: Dict[tuple, List[RuleSuggestion]] = {}

        for sample_suggestions in all_suggestions:
            for s in sample_suggestions:
                key = (s.name, s.selector_value)
                if key not in suggestion_counts:
                    suggestion_counts[key] = []
                suggestion_counts[key].append(s)

        # Build final list with cross-sample stats
        final_suggestions = []
        num_samples = len(html_samples)

        for key, instances in suggestion_counts.items():
            # Use first instance as base
            base = instances[0]

            # Calculate how many samples this selector worked in
            found_in = len(instances)

            # Boost confidence based on consistency across samples
            consistency_boost = found_in / num_samples
            adjusted_confidence = min(0.99, base.confidence * (0.5 + 0.5 * consistency_boost))

            # Only include if found in at least half the samples
            if found_in >= num_samples / 2:
                final_suggestions.append(RuleSuggestion(
                    name=base.name,
                    selector_type=base.selector_type,
                    selector_value=base.selector_value,
                    attribute=base.attribute,
                    is_list=base.is_list,
                    confidence=round(adjusted_confidence, 2),
                    preview=base.preview,
                    found_in_samples=found_in,
                    category=base.category,
                ))

        # Sort by confidence
        final_suggestions.sort(key=lambda x: (-x.confidence, x.name))
        return final_suggestions

    def _check_semantic_elements(self, tree) -> List[RuleSuggestion]:
        """Check for semantic HTML elements."""
        suggestions = []

        for name, selector, attr, category, confidence in self.SEMANTIC_CHECKS:
            try:
                elements = tree.cssselect(selector)
                if elements:
                    value = self._extract_value(elements[0], attr)
                    if value and len(value.strip()) > 0:
                        suggestions.append(RuleSuggestion(
                            name=name,
                            selector_type="css",
                            selector_value=selector,
                            attribute=attr,
                            is_list=False,
                            confidence=confidence,
                            preview=value[:100].strip(),
                            category=category,
                        ))
            except Exception:
                continue

        return suggestions

    def _check_meta_tags(self, tree) -> List[RuleSuggestion]:
        """Check Open Graph and standard meta tags."""
        suggestions = []

        # Open Graph tags
        for meta in tree.cssselect("meta[property^='og:']"):
            prop = meta.get("property", "").replace("og:", "")
            content = meta.get("content", "")
            if content:
                suggestions.append(RuleSuggestion(
                    name=f"og_{prop}",
                    selector_type="css",
                    selector_value=f"meta[property='og:{prop}']",
                    attribute="content",
                    is_list=False,
                    confidence=0.95,
                    preview=content[:100],
                    category="meta",
                ))

        # Twitter cards
        for meta in tree.cssselect("meta[name^='twitter:']"):
            name = meta.get("name", "").replace("twitter:", "")
            content = meta.get("content", "")
            if content:
                suggestions.append(RuleSuggestion(
                    name=f"twitter_{name}",
                    selector_type="css",
                    selector_value=f"meta[name='twitter:{name}']",
                    attribute="content",
                    is_list=False,
                    confidence=0.9,
                    preview=content[:100],
                    category="meta",
                ))

        # Standard meta description
        desc_meta = tree.cssselect("meta[name='description']")
        if desc_meta:
            content = desc_meta[0].get("content", "")
            if content:
                suggestions.append(RuleSuggestion(
                    name="meta_description",
                    selector_type="css",
                    selector_value="meta[name='description']",
                    attribute="content",
                    is_list=False,
                    confidence=0.95,
                    preview=content[:100],
                    category="meta",
                ))

        return suggestions

    def _scan_class_patterns(self, tree) -> List[RuleSuggestion]:
        """Scan for elements with common class name patterns."""
        suggestions = []

        # Get all elements with class attributes
        elements_with_classes = tree.cssselect("[class]")

        # Track what we've already suggested to avoid duplicates
        seen_selectors = set()

        for el in elements_with_classes:
            classes = el.get("class", "").split()

            for cls in classes:
                cls_lower = cls.lower()

                for pattern, field_name, category, confidence in self.CLASS_PATTERNS:
                    if re.search(pattern, cls_lower):
                        selector = f".{cls}"

                        if selector in seen_selectors:
                            continue
                        seen_selectors.add(selector)

                        # Extract value for preview
                        value = self._extract_value(el, None)
                        if value and len(value.strip()) > 2:
                            # Determine if this should extract an attribute
                            attr = None
                            if el.tag == "img":
                                attr = "src"
                                value = el.get("src", "")
                            elif el.tag == "a":
                                attr = "href"
                                value = el.get("href", "")

                            suggestions.append(RuleSuggestion(
                                name=field_name,
                                selector_type="css",
                                selector_value=selector,
                                attribute=attr,
                                is_list=False,
                                confidence=confidence,
                                preview=value[:100].strip(),
                                category=category,
                            ))

        return suggestions

    def _detect_repeated_structures(self, tree) -> List[RuleSuggestion]:
        """Detect repeated elements that might be list items."""
        suggestions = []

        # Count elements by their class combinations
        class_counts: Counter = Counter()
        class_elements: Dict[str, list] = {}

        for el in tree.cssselect("[class]"):
            classes = el.get("class", "")
            if classes:
                # Use first class as key
                first_class = classes.split()[0]
                key = f".{first_class}"
                class_counts[key] += 1
                if key not in class_elements:
                    class_elements[key] = []
                class_elements[key].append(el)

        # Find classes that repeat 3+ times (likely list items)
        for selector, count in class_counts.items():
            if count >= 3:
                elements = class_elements.get(selector, [])
                if elements:
                    # Get preview from first element
                    preview = self._extract_value(elements[0], None)
                    if preview and len(preview.strip()) > 2:
                        suggestions.append(RuleSuggestion(
                            name=f"list_items",
                            selector_type="css",
                            selector_value=selector,
                            attribute=None,
                            is_list=True,
                            confidence=0.7,
                            preview=f"{count} items found",
                            category="list",
                        ))

        return suggestions

    def _check_data_attributes(self, tree) -> List[RuleSuggestion]:
        """Check for data-* attributes that might contain useful info."""
        suggestions = []
        seen = set()

        # Common data attributes to look for
        data_attrs = [
            "data-price", "data-id", "data-sku", "data-product-id",
            "data-title", "data-name", "data-url", "data-image",
        ]

        for attr in data_attrs:
            selector = f"[{attr}]"
            elements = tree.cssselect(selector)

            if elements and selector not in seen:
                seen.add(selector)
                value = elements[0].get(attr, "")
                if value:
                    # Derive field name from attribute
                    field_name = attr.replace("data-", "").replace("-", "_")

                    suggestions.append(RuleSuggestion(
                        name=field_name,
                        selector_type="css",
                        selector_value=selector,
                        attribute=attr,
                        is_list=False,
                        confidence=0.85,
                        preview=value[:100],
                        category="data",
                    ))

        return suggestions

    def _extract_value(self, element, attribute: Optional[str]) -> str:
        """Extract text content or attribute from an element."""
        if attribute:
            return element.get(attribute, "")
        else:
            return element.text_content() or ""

    def _deduplicate_suggestions(self, suggestions: List[RuleSuggestion]) -> List[RuleSuggestion]:
        """Remove duplicate suggestions, keeping highest confidence."""
        # Group by name
        by_name: Dict[str, List[RuleSuggestion]] = {}
        for s in suggestions:
            if s.name not in by_name:
                by_name[s.name] = []
            by_name[s.name].append(s)

        # Keep top 2 suggestions per field name (different selectors)
        final = []
        for name, group in by_name.items():
            # Sort by confidence
            group.sort(key=lambda x: -x.confidence)
            # Take top 2 unique selectors
            seen_selectors = set()
            for s in group:
                if s.selector_value not in seen_selectors:
                    seen_selectors.add(s.selector_value)
                    final.append(s)
                    if len(seen_selectors) >= 2:
                        break

        # Sort final list by confidence
        final.sort(key=lambda x: (-x.confidence, x.name))
        return final
