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

# Window settings
WINDOW_TITLE = "Scrapefruit"
WINDOW_WIDTH = 1400
WINDOW_HEIGHT = 900
WINDOW_MIN_WIDTH = 1000
WINDOW_MIN_HEIGHT = 700
