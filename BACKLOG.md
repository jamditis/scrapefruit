# Backlog

Future features and improvements for Scrapefruit.

## Planned features

### Video scraping and transcription

**Priority:** Medium
**Complexity:** High

Add support for YouTube and other video platforms with automatic transcription:

- **yt-dlp integration**: Download video/audio from YouTube, Vimeo, Twitter, and 1000+ sites
- **Local Whisper transcription**: Use OpenAI Whisper locally for speech-to-text
- **2x speed processing**: Process audio at 2x speed to reduce transcription time/cost
- **Timestamp normalization**: Adjust timestamps back to 1x speed for accurate output
- **Output formats**: SRT, VTT, plain text, JSON with word-level timestamps

**Implementation notes:**
```python
# Proposed fetcher: VideoFetcher
# 1. Use yt-dlp to extract audio
# 2. Speed up audio 2x with ffmpeg
# 3. Run Whisper transcription
# 4. Normalize timestamps (divide by 2)
# 5. Return transcript with metadata
```

**Dependencies:**
- `yt-dlp` - video/audio extraction
- `openai-whisper` or `faster-whisper` - transcription
- `ffmpeg` - audio processing

---

## Ideas (not yet planned)

- Proxy rotation support
- Residential proxy integration
- CAPTCHA solving service integration
- Scheduled/recurring scrape jobs
- Webhook notifications on job completion
- PDF extraction support
- Image OCR for infographics
