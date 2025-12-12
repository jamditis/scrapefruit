"""Poison pill types and result structures."""

from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, Any, Optional


class PoisonPillType(str, Enum):
    """Types of poison pills (content issues) that can be detected."""

    CONTENT_TOO_SHORT = "content_too_short"
    PAYWALL_DETECTED = "paywall_detected"
    ANTI_BOT = "anti_bot"
    CAPTCHA = "captcha"
    RATE_LIMITED = "rate_limited"
    DEAD_LINK = "dead_link"
    REDIRECT_LOOP = "redirect_loop"
    MALFORMED_HTML = "malformed_html"
    LOGIN_REQUIRED = "login_required"
    GEOGRAPHIC_BLOCK = "geographic_block"


@dataclass
class PoisonPillResult:
    """Result of poison pill detection."""

    is_poison: bool
    pill_type: Optional[str] = None
    severity: str = "low"  # low, medium, high, critical
    details: Dict[str, Any] = field(default_factory=dict)
    recommended_action: str = ""
    retry_possible: bool = False

    @classmethod
    def clean(cls) -> "PoisonPillResult":
        """Return a clean (no poison) result."""
        return cls(is_poison=False)

    @classmethod
    def detected(
        cls,
        pill_type: PoisonPillType,
        severity: str = "medium",
        message: str = "",
        retry_possible: bool = False,
    ) -> "PoisonPillResult":
        """Create a detected poison pill result."""
        return cls(
            is_poison=True,
            pill_type=pill_type.value,
            severity=severity,
            details={"message": message},
            recommended_action=cls._get_recommended_action(pill_type),
            retry_possible=retry_possible,
        )

    @staticmethod
    def _get_recommended_action(pill_type: PoisonPillType) -> str:
        """Get recommended action for a poison pill type."""
        actions = {
            PoisonPillType.CONTENT_TOO_SHORT: "Try with Playwright for JavaScript rendering",
            PoisonPillType.PAYWALL_DETECTED: "Skip or use authenticated session",
            PoisonPillType.ANTI_BOT: "Use Playwright with stealth mode",
            PoisonPillType.CAPTCHA: "Manual intervention required",
            PoisonPillType.RATE_LIMITED: "Wait and retry with longer delays",
            PoisonPillType.DEAD_LINK: "Mark as failed - URL no longer exists",
            PoisonPillType.REDIRECT_LOOP: "Check URL validity",
            PoisonPillType.MALFORMED_HTML: "Try alternative extraction",
            PoisonPillType.LOGIN_REQUIRED: "Provide authentication credentials",
            PoisonPillType.GEOGRAPHIC_BLOCK: "Use VPN or proxy",
        }
        return actions.get(pill_type, "Review manually")
