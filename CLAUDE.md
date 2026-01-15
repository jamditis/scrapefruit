# Scrapefruit - Web scraping desktop application

## Project overview

Scrapefruit is a Python desktop application for web scraping with a visual interface. It combines a pywebview GUI with a Flask backend, using Playwright for browser automation with stealth capabilities to bypass anti-bot detection.

## Tech stack

- **GUI**: pywebview (desktop window wrapper)
- **Backend**: Flask + Flask-SocketIO (real-time updates)
- **Scraping**: Multi-method cascade with fallback
  - HTTP (requests) - fast, lightweight
  - Playwright with playwright-stealth - JS rendering
  - Puppeteer (pyppeteer) - alternative browser fingerprint
  - Agent-browser (optional) - AI-optimized browsing
- **Database**: SQLite via SQLAlchemy
- **Export**: Google Sheets (gspread)

## Directory structure

```
scrapefruit/
├── api/
│   └── routes/
│       ├── export.py       # Export to Google Sheets
│       └── settings.py     # App settings endpoints
├── core/
│   ├── scraping/
│   │   ├── engine.py       # Cascade scraping orchestrator
│   │   ├── fetchers/
│   │   │   ├── __init__.py           # Fetcher exports
│   │   │   ├── http_fetcher.py       # Basic HTTP requests
│   │   │   ├── playwright_fetcher.py # Playwright with stealth
│   │   │   ├── puppeteer_fetcher.py  # Pyppeteer alternative
│   │   │   └── agent_browser_fetcher.py # Agent-browser CLI wrapper
│   │   └── extractors/
│   │       ├── css_extractor.py    # CSS selector extraction
│   │       └── xpath_extractor.py  # XPath extraction
│   ├── poison_pills/
│   │   ├── detector.py     # Paywall/anti-bot detection
│   │   └── types.py        # Detection pattern types
│   ├── jobs/
│   │   ├── orchestrator.py # Job lifecycle management
│   │   └── worker.py       # Background job worker
│   └── output/
│       └── formatters/
│           └── sheets_formatter.py  # Google Sheets output
├── database/
│   └── repositories/
│       ├── job_repository.py
│       ├── rule_repository.py
│       ├── result_repository.py
│       └── settings_repository.py
├── models/
│   ├── job.py              # Scraping job model
│   ├── url.py              # URL model
│   ├── rule.py             # Extraction rules
│   ├── result.py           # Scraping results
│   ├── template.py         # Reusable templates
│   └── settings.py         # App settings
├── static/
│   └── js/
│       ├── state.js        # Frontend state management
│       └── components/
│           ├── rules-editor.js      # Rule editing UI
│           └── cascade-settings.js  # Cascade config UI
├── utils/
│   └── logger.py           # Logging utilities
├── config.py               # Global configuration
├── main.py                 # Application entry point
├── requirements.txt        # Python dependencies
├── pyproject.toml          # Project metadata
└── venv/                   # Virtual environment
```

## Environment setup

### 1. Activate virtual environment

```bash
cd scrapefruit

# Windows
venv\Scripts\activate

# Mac/Linux
source venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
playwright install  # Install browser binaries
```

### 3. Configure environment

Create a `.env` file (copy from `.env.example`):

```bash
# Flask configuration
FLASK_DEBUG=true
SECRET_KEY=your-secret-key-change-in-prod

# Google Sheets export (optional)
GOOGLE_CREDENTIALS_PATH=path/to/credentials.json
```

### 4. Run the application

```bash
python main.py
```

The app runs on `http://127.0.0.1:5150`

## Configuration

Key settings in `config.py`:

| Setting | Default | Description |
|---------|---------|-------------|
| `FLASK_PORT` | 5150 | Server port |
| `DEFAULT_TIMEOUT` | 30000ms | Request timeout |
| `DEFAULT_RETRY_COUNT` | 3 | Retry attempts |
| `DEFAULT_DELAY_MIN` | 1000ms | Min delay between requests |
| `DEFAULT_DELAY_MAX` | 3000ms | Max delay between requests |

### Cascade settings

| Setting | Default | Description |
|---------|---------|-------------|
| `DEFAULT_CASCADE_ORDER` | http, playwright, puppeteer, agent_browser | Fetcher order |
| `CASCADE_ENABLED` | True | Enable cascade fallback |
| `FALLBACK_STATUS_CODES` | 403, 429, 503 | Status codes that trigger fallback |
| `FALLBACK_ERROR_PATTERNS` | blocked, captcha, cloudflare, challenge | Text patterns that trigger fallback |
| `AGENT_BROWSER_PATH` | agent-browser | Path to agent-browser CLI |
| `AGENT_BROWSER_TIMEOUT` | 60000ms | Agent-browser timeout |

## Features

### Cascade scraping

The engine uses a configurable cascade strategy that automatically falls back between scraping methods when one fails or content is blocked.

**Default cascade order:**
1. **HTTP** (fastest) - basic requests library
2. **Playwright** - JS rendering with stealth mode
3. **Puppeteer** - alternative browser fingerprint via pyppeteer
4. **Agent-browser** - AI-optimized browsing (requires separate installation)

**Fallback triggers:**
- Blocked status codes (403, 429, 503)
- Anti-bot detection patterns (cloudflare, captcha, challenge)
- Empty or minimal content (< 500 chars)
- JavaScript-heavy SPA markers
- Poison pill detection (paywall, rate limiting)

**Per-job configuration:** Each job can override cascade settings via the UI, including:
- Enable/disable cascade
- Select which methods to include
- Reorder methods via drag-and-drop
- Configure fallback triggers

### Poison pill detection

The app detects common scraping obstacles:

**Paywall patterns:**
- "subscribe to read"
- "premium content"
- "members only"

**Anti-bot patterns:**
- Cloudflare challenges
- CAPTCHA
- Rate limiting

### User agent rotation

Built-in user agent rotation with modern browser strings for Chrome, Firefox, Safari, and Edge.

### Data extraction

- **CSS selectors**: Extract content using CSS selectors
- **XPath**: Extract content using XPath expressions
- **Trafilatura**: Full article extraction with metadata

### Export options

- SQLite database (local)
- Google Sheets (requires credentials)

## Data directories

| Directory | Purpose |
|-----------|---------|
| `data/` | SQLite database (`scrapefruit.db`) |
| `logs/` | Application logs |
| `exports/` | Exported data files |

## Development notes

### Adding new extractors

1. Create new extractor in `core/scraping/extractors/`
2. Inherit from base extractor class
3. Implement `extract()` method
4. Register in `extractors/__init__.py`

### Adding new fetchers

1. Create new fetcher in `core/scraping/fetchers/`
2. Implement fetch strategy (requests, Playwright, etc.)
3. Register in `fetchers/__init__.py`

## Troubleshooting

### Playwright errors

```bash
# Reinstall browsers
playwright install chromium

# Check playwright is in PATH
playwright --version
```

### Pyppeteer errors

Pyppeteer's bundled Chromium download may fail due to outdated URLs. The engine is configured to use Playwright's Chromium installation as a fallback.

```bash
# If pyppeteer Chromium download fails, use Playwright's
python -m playwright install chromium

# The puppeteer_fetcher will look for Playwright's Chromium
```

### Agent-browser not available

Agent-browser is optional and requires separate installation:

```bash
# Install globally via npm
npm install -g agent-browser

# Install browser
agent-browser install

# Set custom path if needed
AGENT_BROWSER_PATH=/path/to/agent-browser
```

The engine gracefully skips agent-browser if not installed.

### Google Sheets export fails

- Verify `GOOGLE_CREDENTIALS_PATH` points to valid service account JSON
- Ensure service account has edit access to target spreadsheet

### Anti-bot blocking

- Increase delays in config
- Try different user agents
- Enable cascade mode to automatically try alternative fetchers
- Consider using residential proxies
