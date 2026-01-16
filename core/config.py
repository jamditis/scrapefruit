"""Structured configuration with validation and compiled patterns.

This module provides a type-safe, validated configuration system
that compiles regex patterns at startup for better performance.

Usage:
    from core.config import get_config, ScrapingConfig

    config = get_config()
    if config.scraping.timeout > 30000:
        print("Long timeout configured")

    # Use pre-compiled patterns
    for pattern in config.patterns.paywall:
        if pattern.search(html):
            print("Paywall detected")
"""

import os
import re
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Pattern, Optional, Tuple
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


@dataclass(frozen=True)
class PathConfig:
    """Path configuration (immutable)."""

    base_dir: Path
    data_dir: Path
    logs_dir: Path
    exports_dir: Path
    database_path: Path

    @property
    def database_url(self) -> str:
        """SQLAlchemy database URL."""
        return f"sqlite:///{self.database_path}"


@dataclass(frozen=True)
class FlaskConfig:
    """Flask server configuration."""

    host: str = "127.0.0.1"
    port: int = 5150
    debug: bool = False
    secret_key: str = "scrapefruit-dev-key-change-in-prod"


@dataclass(frozen=True)
class ScrapingConfig:
    """Scraping behavior configuration."""

    timeout_ms: int = 30000
    retry_count: int = 3
    delay_min_ms: int = 1000
    delay_max_ms: int = 3000
    user_agents: Tuple[str, ...] = ()

    def __post_init__(self):
        """Validate configuration values."""
        if self.timeout_ms <= 0:
            raise ValueError(f"timeout_ms must be positive, got {self.timeout_ms}")
        if self.retry_count < 0:
            raise ValueError(f"retry_count must be non-negative, got {self.retry_count}")
        if self.delay_min_ms < 0 or self.delay_max_ms < 0:
            raise ValueError("delay values must be non-negative")
        if self.delay_min_ms > self.delay_max_ms:
            raise ValueError("delay_min_ms cannot exceed delay_max_ms")
        if not self.user_agents:
            raise ValueError("At least one user agent is required")


@dataclass(frozen=True)
class CascadeConfig:
    """Cascade fallback configuration."""

    enabled: bool = True
    order: Tuple[str, ...] = ("http", "playwright", "puppeteer", "agent_browser")
    fallback_status_codes: Tuple[int, ...] = (403, 429, 503)
    fallback_error_patterns: Tuple[str, ...] = (
        "blocked", "captcha", "cloudflare", "challenge", "denied", "rate limit"
    )
    fallback_poison_pills: Tuple[str, ...] = ("anti_bot", "rate_limited")


@dataclass(frozen=True)
class WindowConfig:
    """Desktop window configuration."""

    title: str = "Scrapefruit"
    width: int = 1400
    height: int = 900
    min_width: int = 1000
    min_height: int = 700


@dataclass(frozen=True)
class LLMConfig:
    """LLM provider configuration."""

    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "gemma3:4b"
    ollama_timeout_seconds: int = 5

    @property
    def has_openai_key(self) -> bool:
        """Check if OpenAI API key is configured."""
        return bool(os.getenv("OPENAI_API_KEY"))

    @property
    def has_anthropic_key(self) -> bool:
        """Check if Anthropic API key is configured."""
        return bool(os.getenv("ANTHROPIC_API_KEY"))


@dataclass(frozen=True)
class VideoConfig:
    """Video transcription configuration."""

    whisper_model: str = "base"
    whisper_device: str = "cpu"
    whisper_compute_type: str = "int8"
    use_2x_speed: bool = True


@dataclass(frozen=True)
class AuthConfig:
    """Authentication configuration."""

    enabled: bool = False
    username: str = ""
    password: str = ""


class CompiledPatterns:
    """Pre-compiled regex patterns for performance.

    Patterns are compiled once at startup and reused throughout
    the application lifetime. This avoids repeated regex compilation
    on every detection check.
    """

    def __init__(
        self,
        paywall_patterns: List[str],
        anti_bot_patterns: List[str],
        fallback_error_patterns: List[str],
    ):
        # Compile patterns with case-insensitive flag
        self.paywall: List[Pattern] = [
            re.compile(p, re.IGNORECASE) for p in paywall_patterns
        ]
        self.anti_bot: List[Pattern] = [
            re.compile(p, re.IGNORECASE) for p in anti_bot_patterns
        ]
        self.fallback_error: List[Pattern] = [
            re.compile(re.escape(p), re.IGNORECASE) for p in fallback_error_patterns
        ]

        # Combined pattern for quick "any match" check
        self._any_poison_pill = re.compile(
            "|".join(paywall_patterns + anti_bot_patterns),
            re.IGNORECASE
        )

    def has_any_poison_pill(self, text: str) -> bool:
        """Quick check if text contains any poison pill pattern."""
        return bool(self._any_poison_pill.search(text))

    def find_paywall_match(self, text: str) -> Optional[str]:
        """Find first paywall pattern match."""
        for pattern in self.paywall:
            match = pattern.search(text)
            if match:
                return match.group(0)
        return None

    def find_anti_bot_match(self, text: str) -> Optional[str]:
        """Find first anti-bot pattern match."""
        for pattern in self.anti_bot:
            match = pattern.search(text)
            if match:
                return match.group(0)
        return None


@dataclass
class AppConfig:
    """
    Main application configuration.

    This is the top-level config object that contains all
    configuration sections and compiled patterns.
    """

    paths: PathConfig
    flask: FlaskConfig
    scraping: ScrapingConfig
    cascade: CascadeConfig
    window: WindowConfig
    llm: LLMConfig
    video: VideoConfig
    auth: AuthConfig
    patterns: CompiledPatterns

    @classmethod
    def from_environment(cls) -> "AppConfig":
        """
        Create configuration from environment variables and defaults.

        This is the main factory method for creating a validated
        configuration instance.
        """
        base_dir = Path(__file__).parent.parent
        data_dir = base_dir / "data"
        logs_dir = base_dir / "logs"
        exports_dir = base_dir / "exports"

        # Ensure directories exist
        data_dir.mkdir(exist_ok=True)
        logs_dir.mkdir(exist_ok=True)
        exports_dir.mkdir(exist_ok=True)

        # Default user agents
        user_agents = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
        )

        # Poison pill patterns
        paywall_patterns = [
            r"subscribe\s+to\s+(read|continue|access)",
            r"premium\s+content",
            r"members?\s+only",
            r"sign\s+in\s+to\s+read",
            r"this\s+article\s+is\s+for\s+subscribers",
        ]

        anti_bot_patterns = [
            r"cloudflare",
            r"captcha",
            r"verify\s+you\s+are\s+human",
            r"access\s+denied",
            r"rate\s+limit",
        ]

        cascade_config = CascadeConfig()

        return cls(
            paths=PathConfig(
                base_dir=base_dir,
                data_dir=data_dir,
                logs_dir=logs_dir,
                exports_dir=exports_dir,
                database_path=data_dir / "scrapefruit.db",
            ),
            flask=FlaskConfig(
                host="127.0.0.1",
                port=5150,
                debug=os.getenv("FLASK_DEBUG", "false").lower() == "true",
                secret_key=os.getenv("SECRET_KEY", "scrapefruit-dev-key-change-in-prod"),
            ),
            scraping=ScrapingConfig(
                timeout_ms=30000,
                retry_count=3,
                delay_min_ms=1000,
                delay_max_ms=3000,
                user_agents=user_agents,
            ),
            cascade=cascade_config,
            window=WindowConfig(),
            llm=LLMConfig(
                ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
                ollama_model=os.getenv("OLLAMA_MODEL", "gemma3:4b"),
                ollama_timeout_seconds=5,
            ),
            video=VideoConfig(
                whisper_model=os.getenv("WHISPER_MODEL", "base"),
                whisper_device=os.getenv("WHISPER_DEVICE", "cpu"),
                whisper_compute_type=os.getenv("WHISPER_COMPUTE_TYPE", "int8"),
                use_2x_speed=os.getenv("VIDEO_USE_2X_SPEED", "true").lower() == "true",
            ),
            auth=AuthConfig(
                enabled=os.getenv("AUTH_ENABLED", "false").lower() == "true",
                username=os.getenv("AUTH_USERNAME", ""),
                password=os.getenv("AUTH_PASSWORD", ""),
            ),
            patterns=CompiledPatterns(
                paywall_patterns=paywall_patterns,
                anti_bot_patterns=anti_bot_patterns,
                fallback_error_patterns=list(cascade_config.fallback_error_patterns),
            ),
        )


# Thread-safe singleton
_config: Optional[AppConfig] = None
_config_lock = threading.Lock()


def get_config() -> AppConfig:
    """
    Get the singleton configuration instance.

    Thread-safe with double-checked locking pattern.
    Configuration is created once on first access.

    Returns:
        The application configuration
    """
    global _config
    if _config is None:
        with _config_lock:
            if _config is None:
                _config = AppConfig.from_environment()
    return _config


def reset_config() -> None:
    """
    Reset the configuration singleton.

    Useful for testing with different configurations.
    """
    global _config
    with _config_lock:
        _config = None
