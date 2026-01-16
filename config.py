"""Global configuration for Scrapefruit."""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Paths
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
LOGS_DIR = BASE_DIR / "logs"
EXPORTS_DIR = BASE_DIR / "exports"

# Ensure directories exist
DATA_DIR.mkdir(exist_ok=True)
LOGS_DIR.mkdir(exist_ok=True)
EXPORTS_DIR.mkdir(exist_ok=True)

# Database
DATABASE_PATH = DATA_DIR / "scrapefruit.db"
DATABASE_URL = f"sqlite:///{DATABASE_PATH}"

# Flask
FLASK_HOST = "127.0.0.1"
FLASK_PORT = 5150  # Avoid common ports
FLASK_DEBUG = os.getenv("FLASK_DEBUG", "false").lower() == "true"
SECRET_KEY = os.getenv("SECRET_KEY", "scrapefruit-dev-key-change-in-prod")

# Scraping defaults
DEFAULT_TIMEOUT = 30000  # ms
DEFAULT_RETRY_COUNT = 3
DEFAULT_DELAY_MIN = 1000  # ms
DEFAULT_DELAY_MAX = 3000  # ms

# Per-URL timeout to prevent stuck jobs (seconds)
# If a single URL takes longer than this, it's marked as failed and skipped
DEFAULT_URL_TIMEOUT = 120  # 2 minutes per URL

# User agents for rotation
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
]

# Poison pill patterns
PAYWALL_PATTERNS = [
    r"subscribe\s+to\s+(read|continue|access)",
    r"premium\s+content",
    r"members?\s+only",
    r"sign\s+in\s+to\s+read",
    r"this\s+article\s+is\s+for\s+subscribers",
]

ANTI_BOT_PATTERNS = [
    r"cloudflare",
    r"captcha",
    r"verify\s+you\s+are\s+human",
    r"access\s+denied",
    r"rate\s+limit",
]

# Cascade scraping configuration
# agent_browser requires: npm install -g agent-browser && agent-browser install
# See: https://github.com/vercel-labs/agent-browser
DEFAULT_CASCADE_ORDER = ["http", "playwright", "puppeteer", "agent_browser"]
CASCADE_ENABLED = True

# Fallback triggers - conditions that cause cascade to try next method
FALLBACK_STATUS_CODES = [403, 429, 503]
FALLBACK_ERROR_PATTERNS = ["blocked", "captcha", "cloudflare", "challenge", "denied", "rate limit"]
FALLBACK_POISON_PILLS = ["anti_bot", "rate_limited"]

# Agent-browser configuration
AGENT_BROWSER_PATH = os.getenv("AGENT_BROWSER_PATH", "agent-browser")
AGENT_BROWSER_TIMEOUT = 60000  # Allow more time for CLI tool

# Window settings
WINDOW_TITLE = "Scrapefruit"
WINDOW_WIDTH = 1400
WINDOW_HEIGHT = 900
WINDOW_MIN_WIDTH = 1000
WINDOW_MIN_HEIGHT = 700

# Authentication (for web deployment)
AUTH_ENABLED = os.getenv("AUTH_ENABLED", "false").lower() == "true"
AUTH_USERNAME = os.getenv("AUTH_USERNAME", "")
AUTH_PASSWORD = os.getenv("AUTH_PASSWORD", "")

# LLM configuration (for AI-driven browser automation and text processing)
# Ollama is the recommended free/local option
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma3:4b")  # Small model for low-memory systems
# Cloud fallbacks (require API keys)
# OPENAI_API_KEY - set in .env for OpenAI fallback
# ANTHROPIC_API_KEY - set in .env for Anthropic fallback

# Video transcription configuration
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "base")  # tiny, base, small, medium, large-v3
WHISPER_DEVICE = os.getenv("WHISPER_DEVICE", "cpu")  # cpu, cuda, auto
WHISPER_COMPUTE_TYPE = os.getenv("WHISPER_COMPUTE_TYPE", "int8")  # int8, float16, float32
VIDEO_USE_2X_SPEED = os.getenv("VIDEO_USE_2X_SPEED", "true").lower() == "true"  # Faster transcription
