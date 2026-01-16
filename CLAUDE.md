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
  - Agent-browser (optional) - AI-optimized browsing with accessibility tree
  - Browser-use (optional) - LLM-controlled browser automation
  - Video fetcher (optional) - yt-dlp + Whisper transcription
- **Extraction**: BeautifulSoup, lxml, Tesseract OCR (optional)
- **LLM**: Local-first via Ollama, cloud fallback (OpenAI, Anthropic)
- **Database**: SQLite via SQLAlchemy
- **Export**: Google Sheets (gspread)
- **Testing**: pytest with 195+ tests

## Directory structure

```
scrapefruit/
├── api/
│   └── routes/
│       ├── export.py       # Export to Google Sheets
│       ├── scraping.py     # Scraping endpoints
│       └── settings.py     # App settings endpoints
├── core/
│   ├── scraping/
│   │   ├── engine.py       # Cascade scraping orchestrator
│   │   ├── fetchers/
│   │   │   ├── __init__.py             # Fetcher exports
│   │   │   ├── http_fetcher.py         # Basic HTTP requests
│   │   │   ├── playwright_fetcher.py   # Playwright with stealth
│   │   │   ├── puppeteer_fetcher.py    # Pyppeteer alternative
│   │   │   ├── agent_browser_fetcher.py # Agent-browser CLI wrapper
│   │   │   ├── browser_use_fetcher.py  # Browser-use AI integration
│   │   │   └── video_fetcher.py        # yt-dlp + Whisper transcription
│   │   └── extractors/
│   │       ├── __init__.py         # Extractor exports
│   │       ├── css_extractor.py    # CSS selector extraction
│   │       ├── xpath_extractor.py  # XPath extraction
│   │       └── vision_extractor.py # Screenshot + OCR extraction
│   ├── poison_pills/
│   │   ├── detector.py     # Paywall/anti-bot detection
│   │   └── types.py        # Detection pattern types
│   ├── llm/
│   │   ├── __init__.py     # LLM module exports
│   │   └── service.py      # Local-first LLM service (Ollama + cloud fallback)
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
│       ├── types.js        # JSDoc type definitions and validators
│       ├── state.js        # Frontend state management with subscriptions
│       └── components/
│           ├── rules-editor.js      # Rule editing UI
│           └── cascade-settings.js  # Cascade config UI
├── tests/
│   ├── conftest.py         # Shared pytest fixtures
│   ├── unit/
│   │   ├── test_poison_pills.py  # Poison pill detection tests
│   │   ├── test_extractors.py    # CSS/XPath/Vision extractor tests
│   │   └── test_fetchers.py      # Fetcher module tests
│   ├── integration/
│   │   └── test_engine.py        # Scraping engine integration tests
│   └── stress/
│       └── test_edge_cases.py    # Edge case and stress tests
├── utils/
│   └── logger.py           # Logging utilities
├── config.py               # Global configuration
├── main.py                 # Application entry point
├── pytest.ini              # Test configuration
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

# Browser-use AI (optional)
OPENAI_API_KEY=sk-...  # or ANTHROPIC_API_KEY
```

### 4. Run the application

```bash
python main.py
```

The app runs on `http://127.0.0.1:5150`

### 5. Run tests

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific categories
pytest tests/unit/
pytest tests/integration/
pytest tests/stress/

# Skip slow/integration tests
pytest -m "not slow and not integration"
```

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
| `DEFAULT_CASCADE_ORDER` | http, playwright, puppeteer, agent_browser, browser_use | Fetcher order |
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
4. **Agent-browser** - AI-optimized browsing with accessibility tree (requires npm install)
5. **Browser-use** - LLM-controlled browser automation (requires API key)

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

**Rate limiting patterns:**
- "too many requests"
- "rate limit exceeded"
- "quota exceeded"
- "throttled"

**Anti-bot patterns:**
- Cloudflare challenges
- CAPTCHA elements (reCAPTCHA, hCaptcha, Turnstile)
- "access denied"
- "verify you are human"

**Dead link patterns:**
- 404 indicators
- "page not found"
- "article not found"

**Login required patterns:**
- "sign in to view"
- "log in to continue"
- "create an account"

### Data extraction

- **CSS selectors**: Extract content using CSS selectors
- **XPath**: Extract content using XPath expressions
- **Vision/OCR**: Screenshot + Tesseract for when DOM extraction fails

The engine implements a two-phase extraction strategy:
1. First attempts DOM-based extraction (CSS/XPath)
2. If DOM extraction fails and vision is enabled, falls back to screenshot + OCR

### User agent rotation

Built-in user agent rotation with modern browser strings for Chrome, Firefox, Safari, and Edge.

### Video transcription

The VideoFetcher extracts and transcribes video/audio from 1000+ platforms:

```python
from core.scraping.fetchers.video_fetcher import VideoFetcher

fetcher = VideoFetcher(whisper_model="base", use_2x_speed=True)
result = fetcher.fetch("https://youtube.com/watch?v=...")
print(result.transcript)      # Plain text
print(result.to_srt())        # SRT subtitles
print(result.metadata.title)  # Video metadata
```

**Dependencies:** `yt-dlp`, `faster-whisper`, `ffmpeg` (optional, for 2x speed)

**Config options:**
| Setting | Default | Description |
|---------|---------|-------------|
| `WHISPER_MODEL` | base | Whisper model size (tiny, base, small, medium, large-v3) |
| `WHISPER_DEVICE` | cpu | Device for inference (cpu, cuda, auto) |
| `VIDEO_USE_2X_SPEED` | true | Process audio at 2x speed for faster transcription |

### Local LLM integration

The LLM service provides text processing with local-first inference:

```python
from core.llm import get_llm_service

llm = get_llm_service()
result = llm.summarize("Long text...")
entities = llm.extract_entities("Text with names and dates...")
answer = llm.answer_question(context, question)
```

**Provider priority:**
1. Ollama (local, free) - auto-detected if running
2. OpenAI (cloud) - requires OPENAI_API_KEY
3. Anthropic (cloud) - requires ANTHROPIC_API_KEY

**Setup Ollama:**
```bash
# Install from ollama.ai
ollama pull gemma3:4b  # 1.7GB, good for low-memory systems
# Or for even smaller:
ollama pull qwen2.5:1.5b  # 1GB
```

**Config options:**
| Setting | Default | Description |
|---------|---------|-------------|
| `OLLAMA_BASE_URL` | http://localhost:11434 | Ollama server URL |
| `OLLAMA_MODEL` | gemma3:4b | Default model for local inference |

### Export options

- SQLite database (local)
- Google Sheets (requires credentials)

## Data directories

| Directory | Purpose |
|-----------|---------|
| `data/` | SQLite database (`scrapefruit.db`) |
| `logs/` | Application logs |
| `exports/` | Exported data files |

## Architecture patterns

### Dependency injection

The app uses a DI container (`core/container.py`) for managing service dependencies:

```python
from core.container import get_container

container = get_container()
job_repo = container.resolve("job_repository")
orchestrator = container.resolve("job_orchestrator")
```

Services are registered once at startup and resolved throughout the app, enabling easier testing and loose coupling.

### Circuit breaker (LLM service)

The LLM service uses a circuit breaker pattern to handle provider failures gracefully:

- **Closed state**: Normal operation, requests pass through
- **Open state**: After 3 failures, requests fail fast for 60 seconds
- **Half-open state**: After timeout, allows one test request

This prevents cascading failures when Ollama or cloud APIs are unavailable.

### Route decorators

API routes use decorators to reduce boilerplate. The `@require_job` decorator in `api/routes/jobs.py`:

```python
@jobs_bp.route("/<job_id>", methods=["GET"])
@require_job
def get_job(job_id: str):
    # g.job is automatically loaded, 404 returned if not found
    return jsonify({"job": g.job.to_dict()})
```

### Frontend type system

The frontend uses JSDoc for type safety without TypeScript compilation:

- `static/js/types.js` - Type definitions, validators, and type guards
- `static/js/state.js` - Centralized state with fine-grained subscriptions

```javascript
// Subscribe to specific state changes
State.on('jobs', (jobs) => renderJobList(jobs));
State.on('selectedJobId', (id) => highlightJob(id));

// Type validation
const validation = Types.validateJob(jobData);
if (!validation.valid) console.warn(validation.errors);
```

## Development notes

### Adding new extractors

1. Create new extractor in `core/scraping/extractors/`
2. Inherit from base extractor class
3. Implement `extract_one()` and `extract_all()` methods
4. Register in `extractors/__init__.py`
5. Add tests in `tests/unit/test_extractors.py`

### Adding new fetchers

1. Create new fetcher in `core/scraping/fetchers/`
2. Create a dataclass for the result (e.g., `MyFetcherResult`)
3. Implement `fetch()` method returning the result dataclass
4. Add `is_available()` method for optional dependencies
5. Register in `fetchers/__init__.py`
6. Add to `FETCHER_TYPES` in `engine.py`
7. Add tests in `tests/unit/test_fetchers.py`

### Adding new poison pill patterns

1. Add pattern to `config.py` (e.g., `PAYWALL_PATTERNS`, `ANTI_BOT_PATTERNS`)
2. Update `detector.py` if new detection logic is needed
3. Add test cases in `tests/unit/test_poison_pills.py`

### Testing conventions

- Tests use fixtures from `tests/conftest.py`
- HTML fixtures must have 500+ chars and 50+ words to pass content length checks
- Use `pad_html()` helper for inline HTML that needs padding
- Mark slow tests with `@pytest.mark.slow`
- Mark tests requiring external resources with `@pytest.mark.integration`
- Mark vision tests with `@pytest.mark.vision`

## Troubleshooting

### Playwright errors

```bash
# Reinstall browsers
playwright install chromium

# Check playwright is in PATH
playwright --version
```

### Pyppeteer errors

Pyppeteer's bundled Chromium download may fail due to outdated URLs. The engine gracefully handles missing pyppeteer:

```bash
# If pyppeteer Chromium download fails, use Playwright's
python -m playwright install chromium

# pyppeteer is optional - the engine skips it if unavailable
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

### Browser-use not available

Browser-use requires the package and an API key:

```bash
pip install browser-use

# Set API key in .env
OPENAI_API_KEY=sk-...
# or
ANTHROPIC_API_KEY=sk-ant-...
```

The engine gracefully skips browser-use if not configured.

### Vision/OCR not available

Vision extraction requires Tesseract OCR:

```bash
# Windows (via chocolatey)
choco install tesseract

# Mac
brew install tesseract

# Linux
sudo apt install tesseract-ocr

# Python package
pip install pytesseract pillow
```

The engine skips vision fallback if Tesseract is not installed.

### Google Sheets export fails

- Verify `GOOGLE_CREDENTIALS_PATH` points to valid service account JSON
- Ensure service account has edit access to target spreadsheet

### Anti-bot blocking

- Increase delays in config
- Try different user agents
- Enable cascade mode to automatically try alternative fetchers
- Consider using residential proxies

### Test failures

If tests fail with "content_too_short":
- Ensure test HTML has 500+ characters AND 50+ words
- Use fixtures from `conftest.py` or the `pad_html()` helper
- The poison pill detector checks content length before other patterns

### Video fetcher not available

Install dependencies for video transcription:

```bash
pip install yt-dlp faster-whisper

# Install ffmpeg (optional, for 2x speed optimization)
# Windows (via chocolatey)
choco install ffmpeg

# Mac
brew install ffmpeg

# Linux
sudo apt install ffmpeg
```

The engine gracefully skips video fetcher if dependencies are missing.

### Ollama not available

For local LLM inference:

```bash
# Install Ollama from https://ollama.ai

# Pull a small model (recommended for low-memory systems)
ollama pull gemma3:4b  # 1.7GB
# Or even smaller:
ollama pull qwen2.5:1.5b  # 1GB

# Start Ollama server
ollama serve
```

The LLM service auto-detects Ollama and falls back to cloud APIs if unavailable.


---

## Multi-machine workflow

This repo is developed across multiple machines (MacBook, work Windows PC, home Windows PC). GitHub is the source of truth.

**Before switching machines:**
```bash
git add . && git commit -m "WIP" && git push
```

**After switching machines:**
```bash
git pull
```
