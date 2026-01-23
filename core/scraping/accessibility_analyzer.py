"""Accessibility-based analyzer using agent_browser's accessibility tree.

This analyzer complements HTMLAnalyzer by using the browser's accessibility API
to identify interactive elements and their semantic roles, which can suggest
better extraction rules for dynamic content.

Optionally integrates SingleFile CLI to flatten pages for more stable extraction.

Features:
- Accessibility tree parsing with element refs (@e1, @e2, etc.)
- Combined analysis with HTMLAnalyzer for comprehensive rule suggestions
- SingleFile integration for stable, flattened HTML
- LLM-powered intent filtering for non-technical users
"""

import asyncio
import json
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, asdict, field
from typing import Any, Dict, List, Optional, Tuple

from core.scraping.fetchers.agent_browser_fetcher import AgentBrowserFetcher, AgentBrowserResult
from core.scraping.analyzer import HTMLAnalyzer, RuleSuggestion
import config


def _get_singlefile_path() -> Optional[str]:
    """Get path to SingleFile CLI if available."""
    return shutil.which("single-file") or shutil.which("singlefile")


def _get_chromium_path() -> Optional[str]:
    """Get path to Chromium executable for SingleFile."""
    return getattr(config, "CHROMIUM_EXECUTABLE_PATH", None)


@dataclass
class AccessibilitySample:
    """Sample data from accessibility-based fetch."""

    url: str
    html: str
    accessibility_tree: str
    element_refs: Dict[str, Dict[str, Any]]
    status_code: int
    response_time_ms: int
    error: Optional[str] = None
    flattened_html: Optional[str] = None  # SingleFile-flattened HTML

    def to_dict(self) -> Dict[str, Any]:
        return {
            "url": self.url,
            "html_length": len(self.html),
            "flattened_html_length": len(self.flattened_html) if self.flattened_html else 0,
            "accessibility_tree_length": len(self.accessibility_tree) if self.accessibility_tree else 0,
            "element_refs_count": len(self.element_refs),
            "status_code": self.status_code,
            "response_time_ms": self.response_time_ms,
            "error": self.error,
            "has_flattened": self.flattened_html is not None,
        }


@dataclass
class AccessibilityRuleSuggestion:
    """
    Enhanced rule suggestion with accessibility metadata.

    Includes the element's semantic role and accessibility info,
    which helps AI agents understand what each field represents.
    """

    name: str
    selector_type: str  # "css", "xpath", or "aria"
    selector_value: str
    attribute: Optional[str] = None
    is_list: bool = False
    confidence: float = 0.0
    preview: str = ""
    found_in_samples: int = 1
    category: str = "general"
    # Accessibility-specific fields
    aria_role: Optional[str] = None
    aria_name: Optional[str] = None
    ref_id: Optional[str] = None  # e.g., "@e1"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# Preset content categories for quick selection
CONTENT_PRESETS = {
    "articles": {
        "description": "Article content: titles, authors, dates, body text, summaries",
        "keywords": [
            "title", "heading", "headline", "author", "byline", "writer",
            "date", "published", "posted", "updated", "time",
            "article", "content", "body", "text", "paragraph", "story",
            "summary", "excerpt", "lead", "intro", "abstract",
            "category", "tag", "section", "topic",
        ],
        "roles": ["heading", "article", "paragraph", "link", "time"],
        "categories": ["content", "navigation"],
        "priority": 1,
    },
    "media": {
        "description": "All media: images, videos, audio, galleries, embeds",
        "keywords": [
            "image", "img", "photo", "picture", "thumbnail", "gallery", "carousel",
            "video", "youtube", "vimeo", "embed", "player", "stream",
            "audio", "podcast", "mp3", "sound", "music", "track",
            "media", "src", "alt", "poster", "source", "iframe",
            "figure", "figcaption", "caption",
        ],
        "roles": ["img", "figure", "video", "audio"],
        "categories": ["media"],
        "priority": 1,
    },
    "data": {
        "description": "Structured data: tables, lists, stats, numbers, metrics",
        "keywords": [
            "table", "row", "cell", "column", "header", "data", "grid",
            "list", "item", "entry", "record",
            "stat", "statistic", "number", "count", "total", "sum",
            "metric", "value", "percent", "percentage", "ratio",
            "chart", "graph", "figure",
            "price", "cost", "amount", "quantity", "score", "rating",
        ],
        "roles": ["table", "row", "cell", "gridcell", "list", "listitem", "option"],
        "categories": ["table", "list", "content"],
        "priority": 1,
    },
    "products": {
        "description": "Product info: names, prices, descriptions, images, reviews",
        "keywords": [
            "product", "item", "name", "title",
            "price", "cost", "sale", "discount", "deal",
            "description", "details", "specs", "specification", "features",
            "image", "photo", "gallery",
            "rating", "review", "stars", "score",
            "buy", "cart", "add", "purchase", "order",
            "stock", "availability", "quantity", "sku",
        ],
        "roles": ["img", "button", "heading", "listitem"],
        "categories": ["content", "media", "form"],
        "priority": 2,
    },
    "contact": {
        "description": "Contact info: emails, phones, addresses, social links",
        "keywords": [
            "email", "mail", "phone", "tel", "telephone", "call", "fax",
            "address", "location", "map", "directions",
            "contact", "reach", "connect",
            "social", "twitter", "linkedin", "facebook", "instagram", "youtube",
            "website", "url", "link",
        ],
        "roles": ["link", "textbox"],
        "categories": ["navigation", "form"],
        "priority": 2,
    },
    "navigation": {
        "description": "Site navigation: menus, links, buttons, breadcrumbs",
        "keywords": [
            "menu", "nav", "navigation", "navbar", "sidebar",
            "link", "href", "url",
            "button", "btn", "click", "action",
            "home", "about", "contact", "search", "login", "signup",
            "breadcrumb", "trail", "path",
            "next", "prev", "previous", "pagination", "page",
        ],
        "roles": ["link", "button", "navigation", "menu", "menuitem", "tab"],
        "categories": ["navigation"],
        "priority": 3,
    },
    "forms": {
        "description": "Form elements: inputs, dropdowns, buttons, labels",
        "keywords": [
            "input", "field", "text", "textarea",
            "form", "submit", "send", "save",
            "button", "btn", "click",
            "label", "placeholder", "hint",
            "select", "dropdown", "option", "choice",
            "checkbox", "radio", "toggle", "switch",
            "email", "password", "username", "name",
            "search", "query", "filter",
        ],
        "roles": ["textbox", "searchbox", "checkbox", "radio", "button", "combobox", "slider", "switch"],
        "categories": ["form"],
        "priority": 3,
    },
    "lists": {
        "description": "List content: bullet points, numbered lists, item collections",
        "keywords": [
            "list", "item", "entry", "element",
            "bullet", "point", "number", "ordered", "unordered",
            "collection", "group", "set",
            "results", "matches", "items",
        ],
        "roles": ["list", "listitem", "option"],
        "categories": ["list"],
        "priority": 2,
    },
    "all_content": {
        "description": "Main page content: articles, media, data, and key information",
        "keywords": [
            # Article keywords
            "title", "heading", "author", "date", "article", "content", "body", "text",
            # Media keywords
            "image", "video", "audio", "media", "photo", "embed",
            # Data keywords
            "table", "list", "data", "stat", "number", "price",
            # General content
            "main", "primary", "key", "important", "featured", "highlight",
        ],
        "roles": ["heading", "article", "paragraph", "img", "figure", "table", "list", "listitem"],
        "categories": ["content", "media", "table", "list"],
        "priority": 1,
    },
}

# Phrase aliases map common phrases to the correct preset
# These are checked before simple word matching to handle multi-word phrases
PHRASE_ALIASES = {
    # Social media → contact (not media)
    "social media": "contact",
    "social links": "contact",
    "social profiles": "contact",
    # Everything/all → all_content
    "everything": "all_content",
    "all content": "all_content",
    "main content": "all_content",
    "page content": "all_content",
    # Article variations
    "blog post": "articles",
    "news article": "articles",
    "blog content": "articles",
    # Product variations
    "e-commerce": "products",
    "ecommerce": "products",
    "shop items": "products",
    "store items": "products",
    # Data variations
    "spreadsheet": "data",
    "structured data": "data",
    "tabular data": "data",
    # Contact variations
    "contact info": "contact",
    "contact details": "contact",
    "email address": "contact",
    "phone number": "contact",
}


@dataclass
class FilteredRulesResult:
    """Result from intent-based rule filtering."""

    rules: List[AccessibilityRuleSuggestion]
    intent: str
    preset_used: Optional[str] = None
    llm_used: bool = False
    llm_provider: Optional[str] = None
    total_rules_before: int = 0
    total_rules_after: int = 0
    filter_time_ms: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rules": [r.to_dict() for r in self.rules],
            "intent": self.intent,
            "preset_used": self.preset_used,
            "llm_used": self.llm_used,
            "llm_provider": self.llm_provider,
            "total_rules_before": self.total_rules_before,
            "total_rules_after": self.total_rules_after,
            "filter_time_ms": self.filter_time_ms,
        }


class AccessibilityAnalyzer:
    """
    Analyzer that uses browser accessibility API for rule suggestion.

    Complements HTMLAnalyzer by:
    1. Fetching pages with accessibility trees via agent_browser
    2. Identifying interactive elements by semantic role
    3. Mapping accessibility refs to CSS selectors
    4. Suggesting rules based on element semantics
    """

    # Role categories for rule suggestions
    ROLE_CATEGORIES = {
        # Navigation
        "link": "navigation",
        "navigation": "navigation",
        "menu": "navigation",
        "menuitem": "navigation",
        "tab": "navigation",
        # Forms
        "textbox": "form",
        "searchbox": "form",
        "combobox": "form",
        "checkbox": "form",
        "radio": "form",
        "button": "form",
        "switch": "form",
        "slider": "form",
        # Content
        "heading": "content",
        "paragraph": "content",
        "article": "content",
        "img": "media",
        "figure": "media",
        # Lists
        "list": "list",
        "listitem": "list",
        "option": "list",
        # Tables
        "table": "table",
        "row": "table",
        "cell": "table",
        "gridcell": "table",
    }

    def __init__(self):
        self._fetcher: Optional[AgentBrowserFetcher] = None
        self._html_analyzer = HTMLAnalyzer()
        self._singlefile_path = _get_singlefile_path()
        self._chromium_path = _get_chromium_path()

    def is_singlefile_available(self) -> bool:
        """Check if SingleFile CLI is available."""
        return self._singlefile_path is not None

    def flatten_with_singlefile(
        self,
        url: str,
        timeout: int = 60000,
    ) -> Optional[str]:
        """
        Flatten a URL to self-contained HTML using SingleFile CLI.

        SingleFile creates a complete snapshot with:
        - All CSS inlined
        - Images embedded as data URIs
        - JavaScript executed and removed
        - DOM as-rendered (post-JS)

        Args:
            url: URL to flatten
            timeout: Timeout in milliseconds

        Returns:
            Flattened HTML string, or None if failed
        """
        if not self._singlefile_path:
            return None

        try:
            cmd = [
                self._singlefile_path,
                url,
                "--dump-content",
                "--browser-headless",
                f"--browser-load-max-time={timeout}",
                "--browser-wait-until=networkIdle",
            ]

            # Use system Chromium on ARM64
            if self._chromium_path:
                cmd.extend([f"--browser-executable-path={self._chromium_path}"])

            # Add no-sandbox for running as non-root
            cmd.extend([
                "--browser-arg=--no-sandbox",
                "--browser-arg=--disable-setuid-sandbox",
                "--browser-arg=--disable-gpu",
            ])

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout // 1000 + 30,  # Add buffer
            )

            if result.returncode == 0 and result.stdout.strip():
                return result.stdout

            return None

        except subprocess.TimeoutExpired:
            return None
        except Exception:
            return None

    async def _get_fetcher(self) -> AgentBrowserFetcher:
        """Get or create agent_browser fetcher."""
        if self._fetcher is None:
            self._fetcher = AgentBrowserFetcher()
        return self._fetcher

    async def fetch_sample_async(
        self,
        url: str,
        timeout: int = 45000,
    ) -> AccessibilitySample:
        """
        Fetch a single URL with accessibility tree.

        Args:
            url: URL to fetch
            timeout: Timeout in milliseconds

        Returns:
            AccessibilitySample with HTML and accessibility data
        """
        fetcher = await self._get_fetcher()

        result = await fetcher.fetch_async(
            url=url,
            timeout=timeout,
            capture_accessibility=True,
            take_screenshot=False,
        )

        return AccessibilitySample(
            url=url,
            html=result.html,
            accessibility_tree=result.accessibility_tree or "",
            element_refs=result.element_refs or {},
            status_code=result.status_code,
            response_time_ms=result.response_time_ms,
            error=result.error,
        )

    async def fetch_samples_async(
        self,
        urls: List[str],
        timeout: int = 45000,
        max_samples: int = 10,
        use_singlefile: bool = False,
    ) -> Tuple[List[AccessibilitySample], List[Dict[str, str]]]:
        """
        Fetch multiple URLs with accessibility trees.

        Args:
            urls: URLs to fetch (max 10)
            timeout: Timeout per URL in milliseconds
            max_samples: Maximum samples to fetch
            use_singlefile: Also flatten with SingleFile for stable extraction

        Returns:
            Tuple of (successful_samples, errors)
        """
        urls = urls[:max_samples]
        samples = []
        errors = []

        for url in urls:
            try:
                sample = await self.fetch_sample_async(url, timeout)
                if sample.error:
                    errors.append({"url": url, "error": sample.error})
                elif len(sample.html) < 100:
                    errors.append({"url": url, "error": "Empty or minimal HTML"})
                else:
                    # Optionally flatten with SingleFile
                    if use_singlefile and self.is_singlefile_available():
                        flattened = self.flatten_with_singlefile(url, timeout)
                        if flattened:
                            sample.flattened_html = flattened

                    samples.append(sample)
            except Exception as e:
                errors.append({"url": url, "error": str(e)})

        return samples, errors

    def fetch_samples(
        self,
        urls: List[str],
        timeout: int = 45000,
        max_samples: int = 10,
        use_singlefile: bool = False,
    ) -> Tuple[List[AccessibilitySample], List[Dict[str, str]]]:
        """Synchronous wrapper for fetch_samples_async."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(
                self.fetch_samples_async(urls, timeout, max_samples, use_singlefile)
            )
        finally:
            pass  # Don't close loop to avoid EPIPE

    def analyze_accessibility(
        self,
        samples: List[AccessibilitySample],
    ) -> List[AccessibilityRuleSuggestion]:
        """
        Analyze accessibility trees from samples and suggest rules.

        Args:
            samples: List of AccessibilitySample objects

        Returns:
            List of rule suggestions based on accessibility analysis
        """
        if not samples:
            return []

        # Collect all element refs across samples
        all_refs: Dict[str, List[Dict[str, Any]]] = {}  # role -> list of ref info

        for sample in samples:
            for ref_id, info in sample.element_refs.items():
                role = info.get("role", "").lower()
                if role:
                    if role not in all_refs:
                        all_refs[role] = []
                    all_refs[role].append({
                        **info,
                        "ref_id": ref_id,
                        "url": sample.url,
                    })

        suggestions = []
        num_samples = len(samples)

        # Generate suggestions for common roles
        for role, instances in all_refs.items():
            # Count unique URLs this role appears in
            urls_with_role = set(i["url"] for i in instances)
            found_in = len(urls_with_role)

            # Only suggest if found in at least half the samples
            if found_in < num_samples / 2:
                continue

            category = self.ROLE_CATEGORIES.get(role, "general")

            # Group by name to find consistent patterns
            by_name: Dict[str, List[Dict]] = {}
            for inst in instances:
                name = inst.get("name", "")
                if name:
                    if name not in by_name:
                        by_name[name] = []
                    by_name[name].append(inst)

            # Suggest rules for named elements that appear consistently
            for name, name_instances in by_name.items():
                name_urls = set(i["url"] for i in name_instances)
                name_found_in = len(name_urls)

                if name_found_in >= num_samples / 2:
                    # Generate CSS selector based on role and name
                    css_selector = self._role_to_css_selector(role, name)

                    # Calculate confidence
                    consistency = name_found_in / num_samples
                    base_confidence = 0.8 if role in self.ROLE_CATEGORIES else 0.6
                    confidence = min(0.95, base_confidence * (0.5 + 0.5 * consistency))

                    # Derive field name
                    field_name = self._derive_field_name(role, name, category)

                    suggestions.append(AccessibilityRuleSuggestion(
                        name=field_name,
                        selector_type="css",
                        selector_value=css_selector,
                        attribute=self._get_attribute_for_role(role),
                        is_list=role in ("list", "listitem", "option", "row"),
                        confidence=round(confidence, 2),
                        preview=name[:100],
                        found_in_samples=name_found_in,
                        category=category,
                        aria_role=role,
                        aria_name=name,
                        ref_id=name_instances[0].get("ref_id"),
                    ))

            # Also suggest a generic rule for the role (without specific name)
            if len(instances) >= 3:  # At least 3 instances
                generic_selector = self._role_to_css_selector(role, None)
                field_name = f"{role}_items" if role not in ("link", "button") else f"all_{role}s"

                suggestions.append(AccessibilityRuleSuggestion(
                    name=field_name,
                    selector_type="css",
                    selector_value=generic_selector,
                    attribute=self._get_attribute_for_role(role),
                    is_list=True,
                    confidence=0.7,
                    preview=f"{len(instances)} {role} elements found",
                    found_in_samples=found_in,
                    category=category,
                    aria_role=role,
                ))

        # Sort by confidence
        suggestions.sort(key=lambda x: (-x.confidence, x.name))

        return suggestions

    def analyze_combined(
        self,
        samples: List[AccessibilitySample],
        prefer_flattened: bool = True,
    ) -> List[AccessibilityRuleSuggestion]:
        """
        Combine HTML analysis with accessibility analysis for best results.

        Args:
            samples: List of AccessibilitySample objects
            prefer_flattened: Use SingleFile-flattened HTML when available

        Returns:
            Combined rule suggestions from both analysis methods
        """
        # Run accessibility analysis
        accessibility_suggestions = self.analyze_accessibility(samples)

        # Run HTML analysis - prefer flattened HTML if available
        html_samples = []
        for s in samples:
            if prefer_flattened and s.flattened_html:
                html_samples.append(s.flattened_html)
            elif s.html:
                html_samples.append(s.html)

        html_suggestions = self._html_analyzer.analyze_multiple(html_samples)

        # Convert HTML suggestions to AccessibilityRuleSuggestion
        combined = list(accessibility_suggestions)

        for hs in html_suggestions:
            # Check if we already have this selector
            existing = any(
                s.selector_value == hs.selector_value
                for s in combined
            )
            if not existing:
                combined.append(AccessibilityRuleSuggestion(
                    name=hs.name,
                    selector_type=hs.selector_type,
                    selector_value=hs.selector_value,
                    attribute=hs.attribute,
                    is_list=hs.is_list,
                    confidence=hs.confidence,
                    preview=hs.preview,
                    found_in_samples=hs.found_in_samples,
                    category=hs.category,
                ))

        # Sort by confidence
        combined.sort(key=lambda x: (-x.confidence, x.name))

        return combined

    def _role_to_css_selector(self, role: str, name: Optional[str]) -> str:
        """Convert ARIA role and name to CSS selector."""
        # Map roles to common HTML elements/attributes
        role_selectors = {
            "link": "a",
            "button": "button, [role='button'], input[type='submit']",
            "textbox": "input[type='text'], input:not([type]), textarea",
            "searchbox": "input[type='search'], [role='searchbox']",
            "checkbox": "input[type='checkbox']",
            "radio": "input[type='radio']",
            "combobox": "select, [role='combobox']",
            "heading": "h1, h2, h3, h4, h5, h6",
            "img": "img",
            "navigation": "nav, [role='navigation']",
            "article": "article",
            "list": "ul, ol, [role='list']",
            "listitem": "li, [role='listitem']",
            "table": "table",
            "row": "tr",
            "cell": "td, th",
        }

        base_selector = role_selectors.get(role, f"[role='{role}']")

        if name:
            # Add attribute selector for accessible name
            # This is approximate - real accessible name computation is complex
            escaped_name = name.replace('"', '\\"')
            if role == "link":
                return f"a:contains('{escaped_name}')"  # jQuery-style, may need adjustment
            elif role == "button":
                return f"button:contains('{escaped_name}'), [aria-label='{escaped_name}']"
            elif role == "img":
                return f"img[alt='{escaped_name}']"
            else:
                return f"[aria-label='{escaped_name}'], :contains('{escaped_name}')"

        return base_selector

    def _get_attribute_for_role(self, role: str) -> Optional[str]:
        """Get the attribute to extract for a given role."""
        attribute_map = {
            "link": "href",
            "img": "src",
            "textbox": "value",
            "checkbox": "checked",
            "radio": "checked",
        }
        return attribute_map.get(role)

    def _derive_field_name(self, role: str, name: str, category: str) -> str:
        """Derive a field name from role and accessible name."""
        # Clean the name for use as a field identifier
        clean_name = re.sub(r'[^a-zA-Z0-9\s]', '', name.lower())
        clean_name = re.sub(r'\s+', '_', clean_name.strip())

        if len(clean_name) > 30:
            clean_name = clean_name[:30]

        if not clean_name:
            return f"{role}_{category}"

        # Prefix with role for clarity
        if role in ("link", "button"):
            return f"{role}_{clean_name}"
        elif role in ("textbox", "searchbox"):
            return f"input_{clean_name}"
        else:
            return clean_name

    async def close_async(self):
        """Close the fetcher."""
        if self._fetcher:
            await self._fetcher.close_async()
            self._fetcher = None

    def close(self):
        """Synchronous close."""
        if self._fetcher:
            self._fetcher.close()
            self._fetcher = None

    # ─────────────────────────────────────────────────────────────────────────
    # Rule filtering methods (tiered: preset → keyword → category → LLM)
    # ─────────────────────────────────────────────────────────────────────────

    def get_available_presets(self) -> Dict[str, str]:
        """
        Get available content presets for quick filtering.

        Returns:
            Dict mapping preset name to description
        """
        return {name: info["description"] for name, info in CONTENT_PRESETS.items()}

    def filter_by_preset(
        self,
        rules: List[AccessibilityRuleSuggestion],
        preset_name: str,
    ) -> FilteredRulesResult:
        """
        Filter rules using a predefined content preset.

        Args:
            rules: List of rule suggestions to filter
            preset_name: Name of preset (articles, products, contact, etc.)

        Returns:
            FilteredRulesResult with filtered rules
        """
        import time
        start = time.time()

        preset = CONTENT_PRESETS.get(preset_name.lower())
        if not preset:
            # Unknown preset, return all rules
            return FilteredRulesResult(
                rules=rules,
                intent=preset_name,
                preset_used=None,
                total_rules_before=len(rules),
                total_rules_after=len(rules),
                filter_time_ms=int((time.time() - start) * 1000),
            )

        keywords = preset["keywords"]
        roles = preset.get("roles", [])
        categories = preset.get("categories", [])

        filtered = []
        for rule in rules:
            score = 0

            # Check keywords in rule name, selector, and preview
            rule_text = f"{rule.name} {rule.selector_value} {rule.preview}".lower()
            for kw in keywords:
                if kw in rule_text:
                    score += 2

            # Check ARIA role match
            if rule.aria_role and rule.aria_role.lower() in roles:
                score += 3

            # Check category match
            if rule.category and rule.category.lower() in categories:
                score += 2

            if score > 0:
                # Store score for sorting
                filtered.append((score, rule))

        # Sort by score (descending), then by confidence
        filtered.sort(key=lambda x: (-x[0], -x[1].confidence))
        filtered_rules = [r for _, r in filtered]

        return FilteredRulesResult(
            rules=filtered_rules,
            intent=preset["description"],
            preset_used=preset_name,
            total_rules_before=len(rules),
            total_rules_after=len(filtered_rules),
            filter_time_ms=int((time.time() - start) * 1000),
        )

    def filter_by_keywords(
        self,
        rules: List[AccessibilityRuleSuggestion],
        keywords: List[str],
        match_all: bool = False,
    ) -> FilteredRulesResult:
        """
        Filter rules by keyword matching.

        Args:
            rules: List of rule suggestions to filter
            keywords: Keywords to search for (case-insensitive)
            match_all: If True, require all keywords to match; if False, any keyword

        Returns:
            FilteredRulesResult with filtered rules
        """
        import time
        start = time.time()

        keywords = [kw.lower().strip() for kw in keywords if kw.strip()]
        if not keywords:
            return FilteredRulesResult(
                rules=rules,
                intent=", ".join(keywords),
                total_rules_before=len(rules),
                total_rules_after=len(rules),
                filter_time_ms=int((time.time() - start) * 1000),
            )

        filtered = []
        for rule in rules:
            rule_text = f"{rule.name} {rule.selector_value} {rule.preview} {rule.aria_role or ''} {rule.aria_name or ''}".lower()

            if match_all:
                if all(kw in rule_text for kw in keywords):
                    # Score = number of keyword matches * 2
                    score = sum(rule_text.count(kw) for kw in keywords)
                    filtered.append((score, rule))
            else:
                matches = sum(1 for kw in keywords if kw in rule_text)
                if matches > 0:
                    # Score based on how many keywords matched
                    score = matches * 2 + sum(rule_text.count(kw) for kw in keywords)
                    filtered.append((score, rule))

        # Sort by score (descending), then by confidence
        filtered.sort(key=lambda x: (-x[0], -x[1].confidence))
        filtered_rules = [r for _, r in filtered]

        return FilteredRulesResult(
            rules=filtered_rules,
            intent=", ".join(keywords),
            total_rules_before=len(rules),
            total_rules_after=len(filtered_rules),
            filter_time_ms=int((time.time() - start) * 1000),
        )

    def filter_by_category(
        self,
        rules: List[AccessibilityRuleSuggestion],
        categories: List[str],
    ) -> FilteredRulesResult:
        """
        Filter rules by content category.

        Args:
            rules: List of rule suggestions to filter
            categories: Categories to include (navigation, content, form, media, list, table, general)

        Returns:
            FilteredRulesResult with filtered rules
        """
        import time
        start = time.time()

        categories = [c.lower().strip() for c in categories if c.strip()]
        if not categories:
            return FilteredRulesResult(
                rules=rules,
                intent=", ".join(categories),
                total_rules_before=len(rules),
                total_rules_after=len(rules),
                filter_time_ms=int((time.time() - start) * 1000),
            )

        filtered = [r for r in rules if r.category and r.category.lower() in categories]

        # Sort by confidence
        filtered.sort(key=lambda x: -x.confidence)

        return FilteredRulesResult(
            rules=filtered,
            intent=f"categories: {', '.join(categories)}",
            total_rules_before=len(rules),
            total_rules_after=len(filtered),
            filter_time_ms=int((time.time() - start) * 1000),
        )

    def filter_by_role(
        self,
        rules: List[AccessibilityRuleSuggestion],
        roles: List[str],
    ) -> FilteredRulesResult:
        """
        Filter rules by ARIA role.

        Args:
            rules: List of rule suggestions to filter
            roles: ARIA roles to include (link, button, heading, img, etc.)

        Returns:
            FilteredRulesResult with filtered rules
        """
        import time
        start = time.time()

        roles = [r.lower().strip() for r in roles if r.strip()]
        if not roles:
            return FilteredRulesResult(
                rules=rules,
                intent=", ".join(roles),
                total_rules_before=len(rules),
                total_rules_after=len(rules),
                filter_time_ms=int((time.time() - start) * 1000),
            )

        filtered = [r for r in rules if r.aria_role and r.aria_role.lower() in roles]

        # Sort by confidence
        filtered.sort(key=lambda x: -x.confidence)

        return FilteredRulesResult(
            rules=filtered,
            intent=f"roles: {', '.join(roles)}",
            total_rules_before=len(rules),
            total_rules_after=len(roles),
            filter_time_ms=int((time.time() - start) * 1000),
        )

    def smart_filter(
        self,
        rules: List[AccessibilityRuleSuggestion],
        intent: str,
        use_llm: bool = False,
        max_rules: int = 20,
    ) -> FilteredRulesResult:
        """
        Smart filtering using tiered approach: preset → keyword → LLM (optional).

        This method automatically determines the best filtering strategy:
        1. First checks if intent matches a preset name
        2. Then tries keyword extraction and matching
        3. Only uses LLM if use_llm=True and simpler methods found few results

        Args:
            rules: List of rule suggestions to filter
            intent: Natural language description of what user wants
            use_llm: Whether to use LLM as fallback for complex queries
            max_rules: Maximum number of rules to return

        Returns:
            FilteredRulesResult with filtered and ranked rules
        """
        import time
        start = time.time()

        if not rules:
            return FilteredRulesResult(
                rules=[],
                intent=intent,
                total_rules_before=0,
                total_rules_after=0,
                filter_time_ms=0,
            )

        intent_lower = intent.lower().strip()

        # Step 1a: Check for phrase aliases first (handles "social media" → contact)
        for phrase, preset_name in PHRASE_ALIASES.items():
            if phrase in intent_lower:
                result = self.filter_by_preset(rules, preset_name)
                if result.rules:
                    result.rules = result.rules[:max_rules]
                    result.filter_time_ms = int((time.time() - start) * 1000)
                    return result

        # Step 1b: Check if intent matches a preset name exactly
        for preset_name in CONTENT_PRESETS:
            # Require word boundaries to avoid "media" matching in "social media"
            pattern = rf'\b{re.escape(preset_name)}\b'
            if re.search(pattern, intent_lower) or intent_lower == preset_name:
                result = self.filter_by_preset(rules, preset_name)
                if result.rules:
                    result.rules = result.rules[:max_rules]
                    result.filter_time_ms = int((time.time() - start) * 1000)
                    return result

        # Step 2: Extract keywords from intent and filter
        # Remove common stop words and split into keywords
        stop_words = {
            "i", "want", "to", "the", "a", "an", "and", "or", "for", "of", "in",
            "on", "with", "from", "get", "extract", "scrape", "find", "show",
            "me", "all", "any", "some", "like", "such", "as", "that", "which",
            "are", "is", "be", "was", "were", "been", "being", "have", "has",
            "had", "do", "does", "did", "will", "would", "could", "should",
        }
        words = re.findall(r'\b[a-z]+\b', intent_lower)
        keywords = [w for w in words if w not in stop_words and len(w) > 2]

        if keywords:
            result = self.filter_by_keywords(rules, keywords)
            if len(result.rules) >= 3:
                result.rules = result.rules[:max_rules]
                result.filter_time_ms = int((time.time() - start) * 1000)
                return result

        # Step 3: Try matching against preset keywords
        # Score presets and prefer high-priority ones (lower number = higher priority)
        preset_matches = []
        for preset_name, preset_info in CONTENT_PRESETS.items():
            preset_keywords = preset_info["keywords"]
            priority = preset_info.get("priority", 5)

            # Score based on keyword matches
            score = sum(1 for kw in keywords if kw in preset_keywords)
            # Also check if preset keywords appear in intent
            score += sum(1 for pkw in preset_keywords if pkw in intent_lower)

            if score >= 2:
                preset_matches.append((score, priority, preset_name))

        # Sort by score (descending), then by priority (ascending)
        if preset_matches:
            preset_matches.sort(key=lambda x: (-x[0], x[1]))
            best_score, _, best_preset = preset_matches[0]
            result = self.filter_by_preset(rules, best_preset)
            if result.rules:
                result.rules = result.rules[:max_rules]
                result.filter_time_ms = int((time.time() - start) * 1000)
                return result

        # Step 4: Use LLM if enabled and simpler methods didn't work well
        if use_llm:
            llm_result = self._filter_with_llm(rules, intent, max_rules)
            if llm_result and llm_result.rules:
                llm_result.filter_time_ms = int((time.time() - start) * 1000)
                return llm_result

        # Fallback: return top rules by confidence
        sorted_rules = sorted(rules, key=lambda x: -x.confidence)[:max_rules]
        return FilteredRulesResult(
            rules=sorted_rules,
            intent=intent,
            total_rules_before=len(rules),
            total_rules_after=len(sorted_rules),
            filter_time_ms=int((time.time() - start) * 1000),
        )

    def _filter_with_llm(
        self,
        rules: List[AccessibilityRuleSuggestion],
        intent: str,
        max_rules: int = 20,
    ) -> Optional[FilteredRulesResult]:
        """
        Use LLM to filter and rank rules based on intent.

        Only called when simpler filtering methods don't produce good results.

        Args:
            rules: List of rule suggestions to filter
            intent: Natural language description of what user wants
            max_rules: Maximum number of rules to return

        Returns:
            FilteredRulesResult or None if LLM unavailable/fails
        """
        try:
            from core.llm.service import get_llm_service
        except ImportError:
            return None

        llm = get_llm_service()
        if not llm.is_available():
            return None

        # Create a compact representation of rules for LLM
        rules_summary = []
        for i, rule in enumerate(rules[:50]):  # Limit to 50 rules for context
            rules_summary.append({
                "id": i,
                "name": rule.name,
                "category": rule.category,
                "role": rule.aria_role,
                "preview": rule.preview[:80] if rule.preview else "",
            })

        system_prompt = """You are a web scraping assistant that helps users find relevant extraction rules.
Given a user's intent and a list of available rules, return the IDs of the most relevant rules.
Output ONLY a JSON array of rule IDs, nothing else. Example: [0, 3, 7, 12]"""

        prompt = f"""User intent: {intent}

Available rules:
{json.dumps(rules_summary, indent=2)}

Return the IDs of the {max_rules} most relevant rules for this intent as a JSON array:"""

        result = llm.complete(prompt, system_prompt)
        if not result.success:
            return None

        try:
            # Parse the JSON array of IDs
            content = result.content.strip()
            # Handle potential markdown code blocks
            if content.startswith("```"):
                content = content.split("\n", 1)[1].rsplit("```", 1)[0]
            selected_ids = json.loads(content)

            if not isinstance(selected_ids, list):
                return None

            # Get the selected rules
            filtered_rules = []
            for rule_id in selected_ids:
                if isinstance(rule_id, int) and 0 <= rule_id < len(rules):
                    filtered_rules.append(rules[rule_id])

            if not filtered_rules:
                return None

            return FilteredRulesResult(
                rules=filtered_rules[:max_rules],
                intent=intent,
                llm_used=True,
                llm_provider=result.provider,
                total_rules_before=len(rules),
                total_rules_after=len(filtered_rules),
            )

        except (json.JSONDecodeError, ValueError, TypeError):
            return None
