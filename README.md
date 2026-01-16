# Scrapefruit

[![GitHub stars](https://img.shields.io/github/stars/jamditis/scrapefruit?style=flat-square)](https://github.com/jamditis/scrapefruit/stargazers)
[![GitHub forks](https://img.shields.io/github/forks/jamditis/scrapefruit?style=flat-square)](https://github.com/jamditis/scrapefruit/network/members)
[![GitHub issues](https://img.shields.io/github/issues/jamditis/scrapefruit?style=flat-square)](https://github.com/jamditis/scrapefruit/issues)
[![GitHub last commit](https://img.shields.io/github/last-commit/jamditis/scrapefruit?style=flat-square)](https://github.com/jamditis/scrapefruit/commits)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue?style=flat-square&logo=python&logoColor=white)](https://www.python.org/downloads/)
[![Deploy](https://img.shields.io/github/actions/workflow/status/jamditis/scrapefruit/deploy.yml?branch=master&style=flat-square&label=deploy)](https://github.com/jamditis/scrapefruit/actions/workflows/deploy.yml)
[![License: PolyForm Noncommercial](https://img.shields.io/badge/license-PolyForm%20Noncommercial-yellow?style=flat-square)](https://polyformproject.org/licenses/noncommercial/1.0.0/)

A Python desktop application for web scraping with a visual interface. Combines a pywebview GUI with a Flask backend, using Playwright for browser automation with stealth capabilities to bypass anti-bot detection.

## Features

- **Visual Interface**: Desktop GUI powered by pywebview
- **Cascade Scraping**: Multi-method fallback system (HTTP, Playwright, Puppeteer, Agent-browser)
- **Anti-bot Bypass**: Playwright-stealth integration for handling Cloudflare, CAPTCHAs, and rate limiting
- **Smart Detection**: Automatic poison pill detection (paywalls, anti-bot patterns)
- **Data Extraction**: CSS selectors, XPath expressions, and Trafilatura for article extraction
- **Export Options**: SQLite database and Google Sheets integration

## Tech Stack

- **GUI**: pywebview
- **Backend**: Flask + Flask-SocketIO
- **Scraping**: Playwright, requests, pyppeteer
- **Database**: SQLite via SQLAlchemy
- **Export**: Google Sheets (gspread)

## Quick Start

### 1. Clone and Setup

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

### 2. Install Dependencies

```bash
pip install -r requirements.txt
playwright install  # Install browser binaries
```

### 3. Configure Environment

```bash
cp .env.example .env
# Edit .env with your settings
```

### 4. Run

```bash
python main.py
```

The app runs on `http://127.0.0.1:5150`

## Cascade Scraping

The engine uses a configurable cascade strategy that automatically falls back between scraping methods:

1. **HTTP** (fastest) - Basic requests library
2. **Playwright** - JS rendering with stealth mode
3. **Puppeteer** - Alternative browser fingerprint
4. **Agent-browser** - AI-optimized browsing (optional)

**Fallback triggers:**
- Blocked status codes (403, 429, 503)
- Anti-bot detection patterns
- Empty or minimal content
- JavaScript-heavy SPA markers

## Configuration

Key settings in `config.py`:

| Setting | Default | Description |
|---------|---------|-------------|
| `FLASK_PORT` | 5150 | Server port |
| `DEFAULT_TIMEOUT` | 30000ms | Request timeout |
| `DEFAULT_RETRY_COUNT` | 3 | Retry attempts |
| `CASCADE_ENABLED` | True | Enable cascade fallback |

## Requirements

- Python 3.11+
- Chromium (installed via Playwright)

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
