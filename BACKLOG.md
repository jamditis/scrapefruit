# Backlog

Future features and improvements for Scrapefruit.

## Implemented features

### Video scraping and transcription ✅

**Status:** Implemented in `core/scraping/fetchers/video_fetcher.py`

YouTube and 1000+ video platforms with automatic transcription:

- **yt-dlp integration**: Download video/audio from YouTube, Vimeo, Twitter, TikTok, etc.
- **Local Whisper transcription**: Uses faster-whisper for efficient speech-to-text
- **2x speed processing**: Processes audio at 2x speed to halve transcription time
- **Timestamp normalization**: Automatically adjusts timestamps back to 1x speed
- **Output formats**: Plain text, SRT, VTT, JSON with word-level timestamps

**Usage:**
```python
from core.scraping.fetchers.video_fetcher import VideoFetcher

fetcher = VideoFetcher(whisper_model="base", use_2x_speed=True)
result = fetcher.fetch("https://youtube.com/watch?v=...")
print(result.transcript)
print(result.to_srt())  # SRT subtitles
```

**Dependencies:** `yt-dlp`, `faster-whisper`, `ffmpeg` (optional, for 2x speed)

### Local LLM integration ✅

**Status:** Implemented in `core/llm/service.py`

Free local LLM support via Ollama with cloud fallbacks:

- **Ollama support**: Free, local inference with models like Gemma 3:4B, Phi-3 Mini
- **Cloud fallbacks**: OpenAI and Anthropic as backups when local isn't available
- **Text processing**: Summarization, entity extraction, classification, Q&A
- **Browser automation**: Enhanced browser_use_fetcher with Ollama support

**Usage:**
```python
from core.llm import get_llm_service

llm = get_llm_service()
result = llm.summarize("Long text here...")
entities = llm.extract_entities("Text with names and dates...")
```

**Setup:** Install Ollama, run `ollama pull gemma3:4b`, then it auto-detects.

---

## Ideas (not yet planned)

### Legion worker for heavy scraping operations

**Problem:** Playwright and agent-browser are slow/unreliable on Raspberry Pi (ARM64, limited RAM). Cloudflare Tunnel has ~100 second timeout which Playwright exceeds.

**Solution:** Hybrid architecture where Pi handles lightweight operations (HTTP fetching, job management, UI) and dispatches heavy Playwright operations to Legion PC.

**Design:**
- Pi serves web UI and handles quick HTTP-only scraping
- For JS-heavy sites, Pi queues job and wakes Legion via WoL
- Legion worker polls for jobs, runs Playwright, returns results
- Similar pattern to existing CJS2026 render pipeline

**Benefits:**
- Playwright runs fast on Legion (RTX 4080, 32GB RAM)
- No Cloudflare timeout issues (async job queue)
- Pi stays lightweight and responsive
- Legion auto-sleeps when idle (60s timeout like render worker)

**Implementation notes:**
- Reuse `.claude-coordination/` pattern or create dedicated job queue
- Consider SQLite job queue on Pi (like render dispatcher)
- Legion worker similar to `legion-worker.mjs` pattern

---

- Proxy rotation support
- Residential proxy integration
- CAPTCHA solving service integration
- Scheduled/recurring scrape jobs
- Webhook notifications on job completion
- PDF extraction support
- Image OCR for infographics
