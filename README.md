![# Scrapefruit homepage screenshot](https://i.imgur.com/GLMUd7C.png)

# Scrapefruit

[![GitHub stars](https://img.shields.io/github/stars/jamditis/scrapefruit?style=flat-square)](https://github.com/jamditis/scrapefruit/stargazers)
[![GitHub forks](https://img.shields.io/github/forks/jamditis/scrapefruit?style=flat-square)](https://github.com/jamditis/scrapefruit/network/members)
[![GitHub issues](https://img.shields.io/github/issues/jamditis/scrapefruit?style=flat-square)](https://github.com/jamditis/scrapefruit/issues)
[![GitHub last commit](https://img.shields.io/github/last-commit/jamditis/scrapefruit?style=flat-square)](https://github.com/jamditis/scrapefruit/commits)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue?style=flat-square&logo=python&logoColor=white)](https://www.python.org/downloads/)
[![Tests](https://img.shields.io/badge/tests-170%20passed-brightgreen?style=flat-square)](https://github.com/jamditis/scrapefruit)
[![License: PolyForm Noncommercial](https://img.shields.io/badge/license-PolyForm%20Noncommercial-yellow?style=flat-square)](https://polyformproject.org/licenses/noncommercial/1.0.0/)

A Python web application for web scraping with a visual interface. Combines a pywebview GUI with a Flask backend, using Playwright for browser automation with stealth capabilities to bypass anti-bot detection.

## Features

- **Visual interface**: Desktop GUI powered by pywebview
- **Cascade scraping**: Multi-method fallback system (HTTP → Playwright → Puppeteer → Agent-browser → Browser-use)
- **Anti-bot bypass**: Playwright-stealth integration for handling Cloudflare, CAPTCHAs, and rate limiting
- **Smart detection**: Automatic poison pill detection (paywalls, rate limiting, anti-bot patterns, dead links)
- **Data extraction**: CSS selectors, XPath expressions, and vision-based OCR fallback
- **Export options**: SQLite database and Google Sheets integration
- **AI-driven scraping**: Optional browser-use integration for LLM-controlled browser automation
- **Video transcription**: Extract and transcribe videos from YouTube, Twitter/X, TikTok, and 1000+ platforms
- **Local LLM integration**: Free local inference via Ollama for summarization, entity extraction, and classification

## Tech stack

- **GUI**: pywebview
- **Backend**: Flask + Flask-SocketIO
- **Scraping**: Playwright, requests, pyppeteer, browser-use (optional)
- **Extraction**: BeautifulSoup, lxml, Tesseract OCR (optional)
- **Database**: SQLite via SQLAlchemy
- **Export**: Google Sheets (gspread)
- **Video**: yt-dlp + faster-whisper for transcription
- **LLM**: Ollama (local) with OpenAI/Anthropic fallback

## Quick start

### 1. Clone and setup

```bash
git clone https://github.com/jamditis/scrapefruit.git
cd scrapefruit

# Create virtual environment
python -m venv venv

# Activate (Linux/Mac)
source venv/bin/activate

# Activate (Windows)
venv\Scripts\activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
playwright install  # Install browser binaries
```

### 3. Configure environment

```bash
cp .env.example .env
# Edit .env with your settings
```

### 4. Run

```bash
python main.py
```

The app runs on `http://127.0.0.1:5150`

## Cascade scraping

The engine uses a configurable cascade strategy that automatically falls back between scraping methods:

| Method | Speed | JS Support | Use case |
|--------|-------|------------|----------|
| **HTTP** | Fastest | No | Static pages, APIs |
| **Playwright** | Medium | Yes | JavaScript-heavy sites, stealth mode |
| **Puppeteer** | Medium | Yes | Alternative browser fingerprint |
| **Agent-browser** | Slower | Yes | AI-optimized with accessibility tree |
| **Browser-use** | Slowest | Yes | LLM-controlled automation |
| **Video** | Varies | N/A | YouTube, Twitter/X, TikTok, 1000+ sites |

**Fallback triggers:**
- Blocked status codes (403, 429, 503)
- Anti-bot detection patterns (Cloudflare, CAPTCHA)
- Empty or minimal content (<500 chars)
- JavaScript-heavy SPA markers
- Poison pill detection

## Extraction methods

| Method | Description |
|--------|-------------|
| **CSS selectors** | Standard CSS selector syntax |
| **XPath** | Full XPath expression support |
| **Vision/OCR** | Screenshot + Tesseract for anti-scraping bypasses |

When DOM extraction fails, the engine can automatically capture a screenshot and use OCR to extract text content.

## Configuration

Key settings in `config.py`:

| Setting | Default | Description |
|---------|---------|-------------|
| `FLASK_PORT` | 5150 | Server port |
| `DEFAULT_TIMEOUT` | 30000ms | Request timeout |
| `DEFAULT_RETRY_COUNT` | 3 | Retry attempts |
| `CASCADE_ENABLED` | True | Enable cascade fallback |

## Testing

The project includes a comprehensive test suite:

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test categories
pytest tests/unit/           # Unit tests
pytest tests/integration/    # Integration tests
pytest tests/stress/         # Stress tests
```

**Test coverage:**
- 170+ tests across unit, integration, and stress testing
- Poison pill detection (paywall, rate limiting, anti-bot, CAPTCHA, dead links)
- Extractors (CSS, XPath, Vision/OCR)
- Fetchers (HTTP, Playwright, Puppeteer, Agent-browser, Browser-use)
- Edge cases (large content, malformed HTML, concurrency, unicode)

## Requirements

- Python 3.11+
- Chromium (installed via Playwright)
- Tesseract OCR (optional, for vision extraction)

## Optional dependencies

| Package | Purpose | Install |
|---------|---------|---------|
| `pyppeteer` | Puppeteer browser automation | `pip install pyppeteer` |
| `browser-use` | AI-driven browser control | `pip install browser-use` |
| `pytesseract` | Vision/OCR extraction | `pip install pytesseract` + install Tesseract |
| `agent-browser` | Accessibility tree scraping | `npm install -g agent-browser` |
| `yt-dlp` | Video/audio extraction | `pip install yt-dlp` |
| `faster-whisper` | Audio transcription | `pip install faster-whisper` |
| `ollama` | Local LLM inference | [ollama.ai](https://ollama.ai) + `ollama pull qwen2.5:0.5b` |

## Video transcription

Extract and transcribe videos from 1000+ platforms:

```python
from core.scraping.fetchers.video_fetcher import VideoFetcher

fetcher = VideoFetcher(whisper_model="tiny", use_2x_speed=True)
result = fetcher.fetch("https://youtube.com/watch?v=...")

print(result.transcript)       # Plain text
print(result.to_srt())         # SRT subtitles
print(result.metadata.title)   # Video metadata
```

**Supported platforms:** YouTube, Vimeo, Twitter/X, TikTok, Facebook, Instagram, Twitch, Dailymotion, and 1000+ more via yt-dlp.

## Local LLM integration

Free local inference via Ollama (no API costs):

```python
from core.llm import get_llm_service

llm = get_llm_service()
result = llm.summarize("Long article text...")
entities = llm.extract_entities("Text with names and dates...")
```

**Setup:**
```bash
# Install Ollama from ollama.ai, then:
ollama pull qwen2.5:0.5b  # 400MB, good for low-memory systems
```

The service auto-detects Ollama and falls back to OpenAI/Anthropic if API keys are set.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
