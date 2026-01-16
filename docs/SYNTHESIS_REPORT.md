# Scrapefruit Documentation Synthesis Report

**Generated:** 2026-01-16
**Documents Analyzed:** 4

---

## Executive Summary

Scrapefruit is a Python desktop application for web scraping that combines a visual GUI with sophisticated anti-detection capabilities. The project uses a multi-layered architecture with pywebview for the desktop interface, Flask for the backend, and a cascade of scraping methods to handle various levels of website protection.

---

## Key Findings

### 1. Project Identity and Purpose

All sources consistently describe Scrapefruit as a **web scraping desktop application** with anti-bot bypass capabilities.

> "Scrapefruit is a Python desktop application for web scraping with a visual interface. It combines a pywebview GUI with a Flask backend, using Playwright for browser automation with stealth capabilities to bypass anti-bot detection."
> — **CLAUDE.md** (line 5), **README.md** (line 11)

The application is hosted at `https://scrapefruit.amditis.tech` as indicated by the redirect page.
> — **docs/index.html** (line 7, 65, 69)

### 2. Technical Architecture

#### Core Technology Stack

| Layer | Technology | Source |
|-------|-----------|--------|
| GUI | pywebview (>=5.0) | CLAUDE.md, README.md, requirements.txt |
| Backend | Flask (>=3.0) + Flask-SocketIO (>=5.3) | All sources |
| Scraping | Playwright (>=1.40), requests (>=2.31), pyppeteer (>=2.0.0) | requirements.txt |
| Database | SQLite via SQLAlchemy (>=2.0) | All sources |
| Export | Google Sheets via gspread (>=6.0) | All sources |

#### Cascade Scraping System

The most significant technical feature is the **cascade scraping system** with four fetcher methods:

1. **HTTP** (requests) - "fast, lightweight" — **CLAUDE.md**
2. **Playwright** - "JS rendering with stealth mode" — **README.md**
3. **Puppeteer** (pyppeteer) - "alternative browser fingerprint" — **CLAUDE.md**
4. **Agent-browser** - "AI-optimized browsing (optional)" — **README.md**

> "The engine uses a configurable cascade strategy that automatically falls back between scraping methods when one fails or content is blocked."
> — **CLAUDE.md** (line 145)

### 3. Anti-Detection Features

#### Fallback Triggers
The system automatically escalates to more sophisticated methods when detecting:
- Blocked status codes: **403, 429, 503** — **CLAUDE.md** (line 137)
- Anti-bot patterns: **"blocked, captcha, cloudflare, challenge"** — **CLAUDE.md** (line 138)
- Content threshold: **< 500 characters** triggers fallback — **CLAUDE.md** (line 157)

#### Poison Pill Detection
The application identifies common scraping obstacles:

**Paywall patterns:**
> "subscribe to read", "premium content", "members only"
> — **CLAUDE.md** (lines 171-173)

**Anti-bot patterns:**
> "Cloudflare challenges, CAPTCHA, Rate limiting"
> — **CLAUDE.md** (lines 176-178)

### 4. Configuration Defaults

| Setting | Value | Source |
|---------|-------|--------|
| Server Port | 5150 | CLAUDE.md, README.md |
| Request Timeout | 30000ms | CLAUDE.md, README.md |
| Retry Count | 3 | CLAUDE.md, README.md |
| Request Delay (min) | 1000ms | CLAUDE.md only |
| Request Delay (max) | 3000ms | CLAUDE.md only |
| Agent-browser Timeout | 60000ms | CLAUDE.md only |

### 5. Data Extraction Methods

Three extraction approaches are documented:
- **CSS Selectors** - via cssselect library (>=1.2)
- **XPath Expressions** - via lxml library (>=5.0)
- **Trafilatura** - "Full article extraction with metadata" — **CLAUDE.md** (line 188)

### 6. System Requirements

> "Python 3.11+" and "Chromium (installed via Playwright)"
> — **README.md** (lines 98-99)

### 7. Licensing

The project uses the **PolyForm Noncommercial License**:
> "[![License: PolyForm Noncommercial](https://img.shields.io/badge/license-PolyForm%20Noncommercial-yellow?style=flat-square)]"
> — **README.md** (line 9)

---

## Contradictions Between Sources

### No Major Contradictions Found

The documentation is internally consistent. Both README.md and CLAUDE.md provide the same technical descriptions, with CLAUDE.md offering more comprehensive detail.

### Minor Differences (Not Contradictions)

1. **Level of Detail:** CLAUDE.md includes configuration options (DEFAULT_DELAY_MIN, DEFAULT_DELAY_MAX, AGENT_BROWSER_TIMEOUT) not mentioned in README.md. This is expected as CLAUDE.md serves as the comprehensive development reference.

2. **Pyppeteer Workaround:** Only CLAUDE.md documents the Playwright fallback for Pyppeteer's Chromium download issues:
   > "Pyppeteer's bundled Chromium download may fail due to outdated URLs. The engine is configured to use Playwright's Chromium installation as a fallback."
   > — **CLAUDE.md** (lines 231-232)

---

## Unanswered Questions

### Architecture & Design
1. **How does the job orchestration system work?** The `core/jobs/orchestrator.py` and `worker.py` are mentioned but not documented.
2. **What is the template system?** `models/template.py` is listed in the directory structure but its functionality is not explained.
3. **How does the WebSocket communication work?** Flask-SocketIO is listed but real-time update patterns are not documented.

### Operational Details
4. **What is the database schema?** No documentation exists for the SQLAlchemy models beyond file names.
5. **How does user agent rotation work?** It's mentioned as a feature but implementation details are absent.
6. **What extraction rules are supported?** The `rule.py` model and `rule_repository.py` are referenced but not documented.

### Deployment & Production
7. **What is the deploy.yml workflow doing?** A GitHub Actions deploy workflow badge is shown but not documented.
8. **How is the hosted version at scrapefruit.amditis.tech deployed?** No deployment documentation exists.
9. **When should waitress (production server) be used vs the development server?**

### External Dependencies
10. **What is agent-browser exactly?** Described as "AI-optimized browsing" but no link to documentation or repository is provided.
11. **What format should the Google credentials JSON be in?** Service account setup is not detailed.

### Security & Legal
12. **What are the legal implications of the anti-bot bypass features?** No usage policy or terms of service documentation exists.
13. **How should the SECRET_KEY be generated for production?** Security best practices are not documented.

### Error Handling
14. **What happens when all cascade methods fail?** Error handling and user feedback mechanisms are not documented.
15. **How are rate limits handled across multiple jobs?** Global rate limiting strategy is not specified.

---

## Document Summary

| Document | Lines | Purpose |
|----------|-------|---------|
| CLAUDE.md | 269 | Comprehensive developer reference |
| README.md | 104 | User-facing quickstart guide |
| requirements.txt | 32 | Dependency manifest |
| docs/index.html | 73 | Redirect page to hosted app |

---

*Report generated from analysis of project documentation in /home/user/scrapefruit/*
