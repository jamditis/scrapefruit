"""Poison pill detector for identifying content issues."""

import re
from typing import Optional

from core.poison_pills.types import PoisonPillType, PoisonPillResult
import config


class PoisonPillDetector:
    """
    Detects various content issues (poison pills) that indicate
    scraping problems or blocked content.
    """

    # Minimum content thresholds
    MIN_CONTENT_LENGTH = 500
    MIN_WORD_COUNT = 50

    def detect(self, html: str, url: str = "") -> PoisonPillResult:
        """
        Check HTML content for poison pills.

        Args:
            html: HTML content to check
            url: Optional URL for context

        Returns:
            PoisonPillResult indicating if issues were found
        """
        if not html:
            return PoisonPillResult.detected(
                PoisonPillType.CONTENT_TOO_SHORT,
                severity="high",
                message="Empty response",
            )

        # Check content length
        result = self._check_content_length(html)
        if result.is_poison:
            return result

        # Check for paywall
        result = self._check_paywall(html)
        if result.is_poison:
            return result

        # Check for rate limiting (before anti-bot, since anti-bot patterns include "rate limit")
        result = self._check_rate_limited(html)
        if result.is_poison:
            return result

        # Check for anti-bot
        result = self._check_anti_bot(html)
        if result.is_poison:
            return result

        # Check for CAPTCHA
        result = self._check_captcha(html)
        if result.is_poison:
            return result

        # Check for login required
        result = self._check_login_required(html)
        if result.is_poison:
            return result

        # Check for dead link indicators
        result = self._check_dead_link(html, url)
        if result.is_poison:
            return result

        return PoisonPillResult.clean()

    def _check_content_length(self, html: str) -> PoisonPillResult:
        """Check if content is too short."""
        # Strip HTML tags for word count
        text = re.sub(r'<[^>]+>', ' ', html)
        text = re.sub(r'\s+', ' ', text).strip()
        word_count = len(text.split())

        if len(html) < self.MIN_CONTENT_LENGTH:
            return PoisonPillResult.detected(
                PoisonPillType.CONTENT_TOO_SHORT,
                severity="medium",
                message=f"Content length {len(html)} below minimum {self.MIN_CONTENT_LENGTH}",
                retry_possible=True,
            )

        if word_count < self.MIN_WORD_COUNT:
            return PoisonPillResult.detected(
                PoisonPillType.CONTENT_TOO_SHORT,
                severity="medium",
                message=f"Word count {word_count} below minimum {self.MIN_WORD_COUNT}",
                retry_possible=True,
            )

        return PoisonPillResult.clean()

    def _check_paywall(self, html: str) -> PoisonPillResult:
        """Check for paywall indicators."""
        html_lower = html.lower()

        for pattern in config.PAYWALL_PATTERNS:
            if re.search(pattern, html_lower):
                return PoisonPillResult.detected(
                    PoisonPillType.PAYWALL_DETECTED,
                    severity="high",
                    message="Paywall detected - subscription required",
                )

        # Check for specific paywall elements
        paywall_selectors = [
            'class="paywall"',
            'class="subscriber-only"',
            'data-paywall',
            'id="paywall"',
        ]

        for selector in paywall_selectors:
            if selector in html_lower:
                return PoisonPillResult.detected(
                    PoisonPillType.PAYWALL_DETECTED,
                    severity="high",
                    message="Paywall element detected",
                )

        return PoisonPillResult.clean()

    def _check_rate_limited(self, html: str) -> PoisonPillResult:
        """Check for rate limiting indicators."""
        html_lower = html.lower()

        rate_limit_patterns = [
            r"rate\s*limit",
            r"too\s+many\s+requests",
            r"request\s+limit\s+exceeded",
            r"slow\s+down",
            r"try\s+again\s+(later|in\s+\d+)",
            r"temporarily\s+blocked",
            r"quota\s+exceeded",
            r"api\s+limit",
            r"throttl(ed|ing)",
        ]

        for pattern in rate_limit_patterns:
            if re.search(pattern, html_lower):
                return PoisonPillResult.detected(
                    PoisonPillType.RATE_LIMITED,
                    severity="high",
                    message="Rate limiting detected - server is throttling requests",
                    retry_possible=True,
                )

        # Check for 429 status in meta tags or response indicators
        if 'status="429"' in html_lower or "429 too many" in html_lower:
            return PoisonPillResult.detected(
                PoisonPillType.RATE_LIMITED,
                severity="high",
                message="HTTP 429 Too Many Requests",
                retry_possible=True,
            )

        return PoisonPillResult.clean()

    def _check_anti_bot(self, html: str) -> PoisonPillResult:
        """Check for anti-bot protection."""
        html_lower = html.lower()

        # Filter out rate limit pattern - that's handled by _check_rate_limited
        anti_bot_patterns = [p for p in config.ANTI_BOT_PATTERNS if "rate" not in p]

        for pattern in anti_bot_patterns:
            if re.search(pattern, html_lower):
                return PoisonPillResult.detected(
                    PoisonPillType.ANTI_BOT,
                    severity="high",
                    message="Anti-bot protection detected",
                    retry_possible=True,
                )

        # Check for Cloudflare challenge
        if "cf-browser-verification" in html_lower or "cf_chl_opt" in html_lower:
            return PoisonPillResult.detected(
                PoisonPillType.ANTI_BOT,
                severity="critical",
                message="Cloudflare challenge page",
                retry_possible=True,
            )

        return PoisonPillResult.clean()

    def _check_captcha(self, html: str) -> PoisonPillResult:
        """Check for CAPTCHA challenges."""
        html_lower = html.lower()

        captcha_indicators = [
            "g-recaptcha",
            "h-captcha",
            "recaptcha",
            "captcha-container",
            "cf-turnstile",
        ]

        for indicator in captcha_indicators:
            if indicator in html_lower:
                return PoisonPillResult.detected(
                    PoisonPillType.CAPTCHA,
                    severity="critical",
                    message="CAPTCHA challenge detected",
                )

        return PoisonPillResult.clean()

    def _check_login_required(self, html: str) -> PoisonPillResult:
        """Check if login is required."""
        html_lower = html.lower()

        login_patterns = [
            r"please\s+(log|sign)\s*in",
            r"(log|sign)\s*in\s+to\s+(view|read|continue)",
            r"create\s+an?\s+account\s+to",
            r"members?\s+only\s+content",
        ]

        for pattern in login_patterns:
            if re.search(pattern, html_lower):
                return PoisonPillResult.detected(
                    PoisonPillType.LOGIN_REQUIRED,
                    severity="high",
                    message="Login required to access content",
                )

        return PoisonPillResult.clean()

    def _check_dead_link(self, html: str, url: str) -> PoisonPillResult:
        """Check for dead link indicators."""
        html_lower = html.lower()

        dead_indicators = [
            "page not found",
            "404 error",
            "404 - not found",
            "this page doesn't exist",
            "this page does not exist",
            "the page you requested",
            "article not found",
            "content not found",
            "sorry, we couldn't find",
        ]

        for indicator in dead_indicators:
            if indicator in html_lower:
                return PoisonPillResult.detected(
                    PoisonPillType.DEAD_LINK,
                    severity="high",
                    message="Content appears to be removed or not found",
                )

        # Check title for 404
        title_match = re.search(r'<title[^>]*>([^<]+)</title>', html, re.IGNORECASE)
        if title_match:
            title = title_match.group(1).lower()
            if "404" in title or "not found" in title:
                return PoisonPillResult.detected(
                    PoisonPillType.DEAD_LINK,
                    severity="high",
                    message="Page returns 404 error",
                )

        return PoisonPillResult.clean()
