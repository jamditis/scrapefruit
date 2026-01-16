"""Video Fetcher - Extract and transcribe video/audio content.

This fetcher handles YouTube, Vimeo, Twitter, and 1000+ other video platforms
using yt-dlp for extraction and Whisper for transcription.

Features:
- Video/audio download via yt-dlp
- Optional 2x speed processing for faster transcription
- Local Whisper transcription (no API costs)
- Multiple output formats: plain text, SRT, VTT, JSON with timestamps

Dependencies:
    pip install yt-dlp faster-whisper

    # For 2x speed processing (optional but recommended):
    # Install ffmpeg: https://ffmpeg.org/download.html

Usage:
    from core.scraping.fetchers.video_fetcher import VideoFetcher

    fetcher = VideoFetcher()
    if fetcher.is_available():
        result = fetcher.fetch("https://youtube.com/watch?v=...")
        print(result.transcript)
"""

import os
import re
import json
import shutil
import subprocess
import tempfile
import threading
import time
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field

# Check for yt-dlp
try:
    import yt_dlp
    HAS_YTDLP = True
except ImportError:
    HAS_YTDLP = False

# Check for faster-whisper (preferred) or openai-whisper
try:
    from faster_whisper import WhisperModel
    HAS_FASTER_WHISPER = True
except ImportError:
    HAS_FASTER_WHISPER = False

try:
    import whisper
    HAS_WHISPER = True
except ImportError:
    HAS_WHISPER = False


@dataclass
class VideoMetadata:
    """Metadata extracted from video."""
    title: str = ""
    description: str = ""
    uploader: str = ""
    upload_date: str = ""
    duration: int = 0  # seconds
    view_count: int = 0
    like_count: int = 0
    thumbnail_url: str = ""
    webpage_url: str = ""
    extractor: str = ""
    tags: List[str] = field(default_factory=list)


@dataclass
class TranscriptSegment:
    """A segment of transcribed audio with timestamps."""
    text: str
    start: float  # seconds
    end: float  # seconds

    def to_srt_time(self, seconds: float) -> str:
        """Convert seconds to SRT timestamp format."""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

    def to_vtt_time(self, seconds: float) -> str:
        """Convert seconds to VTT timestamp format."""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"


@dataclass
class VideoFetchResult:
    """Result from a video fetch and transcription operation."""
    success: bool
    url: str = ""
    method: str = "video"
    error: Optional[str] = None
    response_time_ms: int = 0

    # Metadata
    metadata: Optional[VideoMetadata] = None

    # Transcript
    transcript: str = ""  # Plain text transcript
    segments: List[TranscriptSegment] = field(default_factory=list)
    language: str = ""
    language_probability: float = 0.0

    # Processing info
    audio_duration_seconds: float = 0.0
    transcription_time_seconds: float = 0.0
    speed_factor: float = 1.0  # 2.0 if processed at 2x speed
    whisper_model: str = ""

    def to_srt(self) -> str:
        """Convert transcript to SRT subtitle format."""
        lines = []
        for i, seg in enumerate(self.segments, 1):
            lines.append(str(i))
            lines.append(f"{seg.to_srt_time(seg.start)} --> {seg.to_srt_time(seg.end)}")
            lines.append(seg.text.strip())
            lines.append("")
        return "\n".join(lines)

    def to_vtt(self) -> str:
        """Convert transcript to WebVTT subtitle format."""
        lines = ["WEBVTT", ""]
        for seg in self.segments:
            lines.append(f"{seg.to_vtt_time(seg.start)} --> {seg.to_vtt_time(seg.end)}")
            lines.append(seg.text.strip())
            lines.append("")
        return "\n".join(lines)

    def to_json(self) -> str:
        """Convert to JSON with full segment data."""
        return json.dumps({
            "url": self.url,
            "metadata": {
                "title": self.metadata.title if self.metadata else "",
                "uploader": self.metadata.uploader if self.metadata else "",
                "duration": self.metadata.duration if self.metadata else 0,
            },
            "transcript": self.transcript,
            "language": self.language,
            "segments": [
                {"text": s.text, "start": s.start, "end": s.end}
                for s in self.segments
            ],
        }, indent=2)


class VideoFetcher:
    """
    Video/audio fetcher with transcription capabilities.

    Uses yt-dlp to extract audio from video platforms and Whisper
    for speech-to-text transcription.

    The 2x speed optimization:
    - Extracts audio at 2x speed using ffmpeg
    - Runs Whisper on the sped-up audio (2x faster processing)
    - Adjusts timestamps back to original timing

    This effectively halves transcription time with minimal quality loss.
    """

    # Regex patterns for supported video URLs
    VIDEO_URL_PATTERNS = [
        r"youtube\.com/watch",
        r"youtu\.be/",
        r"youtube\.com/shorts/",
        r"vimeo\.com/",
        r"twitter\.com/.+/status/",
        r"x\.com/.+/status/",
        r"tiktok\.com/",
        r"facebook\.com/.+/videos/",
        r"instagram\.com/reel/",
        r"instagram\.com/p/",
        r"twitch\.tv/videos/",
        r"dailymotion\.com/video/",
    ]

    # Whisper model sizes and their approximate memory requirements
    WHISPER_MODELS = {
        "tiny": {"size": "39M", "vram": "~1GB", "speed": "~32x"},
        "base": {"size": "74M", "vram": "~1GB", "speed": "~16x"},
        "small": {"size": "244M", "vram": "~2GB", "speed": "~6x"},
        "medium": {"size": "769M", "vram": "~5GB", "speed": "~2x"},
        "large-v3": {"size": "1550M", "vram": "~10GB", "speed": "~1x"},
    }

    def __init__(
        self,
        whisper_model: str = "base",
        use_2x_speed: bool = True,
        temp_dir: Optional[str] = None,
        device: str = "cpu",
        compute_type: str = "int8",
    ):
        """
        Initialize the video fetcher.

        Args:
            whisper_model: Whisper model size ("tiny", "base", "small", "medium", "large-v3")
            use_2x_speed: Whether to process audio at 2x speed for faster transcription
            temp_dir: Directory for temporary files. If None, uses system temp.
            device: Device for Whisper ("cpu", "cuda", "auto")
            compute_type: Compute type for faster-whisper ("int8", "float16", "float32")
        """
        self.whisper_model_name = whisper_model
        self.use_2x_speed = use_2x_speed
        self.temp_dir = temp_dir
        self.device = device
        self.compute_type = compute_type
        self._whisper_model: Any = None
        self._ffmpeg_path: Optional[str] = None

    def is_available(self) -> bool:
        """Check if the fetcher can operate."""
        return HAS_YTDLP and (HAS_FASTER_WHISPER or HAS_WHISPER)

    def is_video_url(self, url: str) -> bool:
        """Check if a URL is a supported video platform."""
        for pattern in self.VIDEO_URL_PATTERNS:
            if re.search(pattern, url, re.IGNORECASE):
                return True
        return False

    def _get_ffmpeg_path(self) -> Optional[str]:
        """Get path to ffmpeg if available."""
        if self._ffmpeg_path is not None:
            return self._ffmpeg_path

        # Check common locations
        ffmpeg = shutil.which("ffmpeg")
        if ffmpeg:
            self._ffmpeg_path = ffmpeg
            return ffmpeg

        # Check PATH explicitly on Windows
        if os.name == "nt":
            for path in ["C:\\ffmpeg\\bin\\ffmpeg.exe", "C:\\Program Files\\ffmpeg\\bin\\ffmpeg.exe"]:
                if os.path.exists(path):
                    self._ffmpeg_path = path
                    return path

        return None

    def _get_whisper_model(self):
        """Get or create the Whisper model instance."""
        if self._whisper_model is not None:
            return self._whisper_model

        if HAS_FASTER_WHISPER:
            # faster-whisper is more efficient
            self._whisper_model = WhisperModel(
                self.whisper_model_name,
                device=self.device,
                compute_type=self.compute_type,
            )
        elif HAS_WHISPER:
            # OpenAI whisper
            self._whisper_model = whisper.load_model(self.whisper_model_name)

        return self._whisper_model

    def _extract_audio(self, url: str, output_path: str) -> Dict[str, Any]:
        """
        Extract audio from video URL using yt-dlp.

        Returns metadata dict with video information.
        """
        ydl_opts = {
            "format": "bestaudio/best",
            "outtmpl": output_path.replace(".wav", ".%(ext)s"),
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "wav",
                "preferredquality": "192",
            }],
            "quiet": True,
            "no_warnings": True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            return info or {}

    def _speed_up_audio(self, input_path: str, output_path: str, factor: float = 2.0) -> bool:
        """
        Speed up audio file using ffmpeg.

        Returns True if successful.
        """
        ffmpeg = self._get_ffmpeg_path()
        if not ffmpeg:
            return False

        try:
            cmd = [
                ffmpeg, "-i", input_path,
                "-filter:a", f"atempo={factor}",
                "-y",  # Overwrite output
                output_path,
            ]
            result = subprocess.run(cmd, capture_output=True, timeout=120)
            return result.returncode == 0 and os.path.exists(output_path)
        except Exception:
            return False

    def _transcribe(self, audio_path: str) -> Dict[str, Any]:
        """
        Transcribe audio file using Whisper.

        Returns dict with transcript, segments, and language info.
        """
        model = self._get_whisper_model()
        if model is None:
            return {"error": "Whisper model not available"}

        if HAS_FASTER_WHISPER:
            # faster-whisper returns generator
            segments_gen, info = model.transcribe(
                audio_path,
                beam_size=5,
                vad_filter=True,  # Filter out non-speech
            )
            segments = list(segments_gen)

            return {
                "text": " ".join(s.text.strip() for s in segments),
                "segments": [
                    {"text": s.text, "start": s.start, "end": s.end}
                    for s in segments
                ],
                "language": info.language,
                "language_probability": info.language_probability,
            }

        elif HAS_WHISPER:
            # OpenAI whisper
            result = model.transcribe(audio_path)
            return {
                "text": result["text"],
                "segments": [
                    {"text": s["text"], "start": s["start"], "end": s["end"]}
                    for s in result.get("segments", [])
                ],
                "language": result.get("language", ""),
                "language_probability": 0.0,
            }

        return {"error": "No transcription backend available"}

    def fetch(
        self,
        url: str,
        timeout: int = 600000,
        **kwargs,
    ) -> VideoFetchResult:
        """
        Fetch and transcribe a video.

        Args:
            url: Video URL (YouTube, Vimeo, Twitter, etc.)
            timeout: Timeout in milliseconds

        Returns:
            VideoFetchResult with transcript and metadata
        """
        start_time = time.time()

        if not self.is_available():
            missing = []
            if not HAS_YTDLP:
                missing.append("yt-dlp")
            if not HAS_FASTER_WHISPER and not HAS_WHISPER:
                missing.append("faster-whisper or openai-whisper")
            return VideoFetchResult(
                success=False,
                url=url,
                error=f"Missing dependencies: {', '.join(missing)}. Install with: pip install {' '.join(missing)}",
                response_time_ms=int((time.time() - start_time) * 1000),
            )

        # Create temp directory
        temp_base = self.temp_dir or tempfile.gettempdir()
        work_dir = tempfile.mkdtemp(prefix="scrapefruit_video_", dir=temp_base)

        try:
            # Step 1: Extract audio with yt-dlp
            audio_path = os.path.join(work_dir, "audio.wav")
            info = self._extract_audio(url, audio_path)

            # Find the actual downloaded file (might have different extension)
            audio_file = None
            for f in os.listdir(work_dir):
                if f.startswith("audio"):
                    audio_file = os.path.join(work_dir, f)
                    break

            if not audio_file or not os.path.exists(audio_file):
                return VideoFetchResult(
                    success=False,
                    url=url,
                    error="Failed to extract audio from video",
                    response_time_ms=int((time.time() - start_time) * 1000),
                )

            # Build metadata
            metadata = VideoMetadata(
                title=info.get("title", ""),
                description=info.get("description", ""),
                uploader=info.get("uploader", ""),
                upload_date=info.get("upload_date", ""),
                duration=info.get("duration", 0),
                view_count=info.get("view_count", 0),
                like_count=info.get("like_count", 0),
                thumbnail_url=info.get("thumbnail", ""),
                webpage_url=info.get("webpage_url", url),
                extractor=info.get("extractor", ""),
                tags=info.get("tags", []) or [],
            )

            # Step 2: Optionally speed up audio for faster transcription
            speed_factor = 1.0
            transcribe_path = audio_file

            if self.use_2x_speed and self._get_ffmpeg_path():
                sped_up_path = os.path.join(work_dir, "audio_2x.wav")
                if self._speed_up_audio(audio_file, sped_up_path, factor=2.0):
                    transcribe_path = sped_up_path
                    speed_factor = 2.0

            # Step 3: Transcribe
            transcribe_start = time.time()
            transcript_result = self._transcribe(transcribe_path)
            transcribe_time = time.time() - transcribe_start

            if "error" in transcript_result:
                return VideoFetchResult(
                    success=False,
                    url=url,
                    error=transcript_result["error"],
                    metadata=metadata,
                    response_time_ms=int((time.time() - start_time) * 1000),
                )

            # Adjust timestamps if we used 2x speed
            segments = []
            for seg in transcript_result.get("segments", []):
                adjusted_start = seg["start"] * speed_factor
                adjusted_end = seg["end"] * speed_factor
                segments.append(TranscriptSegment(
                    text=seg["text"],
                    start=adjusted_start,
                    end=adjusted_end,
                ))

            return VideoFetchResult(
                success=True,
                url=url,
                metadata=metadata,
                transcript=transcript_result.get("text", ""),
                segments=segments,
                language=transcript_result.get("language", ""),
                language_probability=transcript_result.get("language_probability", 0.0),
                audio_duration_seconds=metadata.duration,
                transcription_time_seconds=transcribe_time,
                speed_factor=speed_factor,
                whisper_model=self.whisper_model_name,
                response_time_ms=int((time.time() - start_time) * 1000),
            )

        except Exception as e:
            return VideoFetchResult(
                success=False,
                url=url,
                error=str(e),
                response_time_ms=int((time.time() - start_time) * 1000),
            )

        finally:
            # Cleanup temp files
            try:
                shutil.rmtree(work_dir, ignore_errors=True)
            except Exception:
                pass

    def get_metadata_only(self, url: str) -> VideoFetchResult:
        """
        Get video metadata without downloading or transcribing.

        Useful for checking video info before full processing.
        """
        start_time = time.time()

        if not HAS_YTDLP:
            return VideoFetchResult(
                success=False,
                url=url,
                error="yt-dlp not installed. Install with: pip install yt-dlp",
                response_time_ms=int((time.time() - start_time) * 1000),
            )

        try:
            ydl_opts = {
                "quiet": True,
                "no_warnings": True,
                "extract_flat": False,
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)

            if not info:
                return VideoFetchResult(
                    success=False,
                    url=url,
                    error="Could not extract video information",
                    response_time_ms=int((time.time() - start_time) * 1000),
                )

            metadata = VideoMetadata(
                title=info.get("title", ""),
                description=info.get("description", ""),
                uploader=info.get("uploader", ""),
                upload_date=info.get("upload_date", ""),
                duration=info.get("duration", 0),
                view_count=info.get("view_count", 0),
                like_count=info.get("like_count", 0),
                thumbnail_url=info.get("thumbnail", ""),
                webpage_url=info.get("webpage_url", url),
                extractor=info.get("extractor", ""),
                tags=info.get("tags", []) or [],
            )

            return VideoFetchResult(
                success=True,
                url=url,
                metadata=metadata,
                response_time_ms=int((time.time() - start_time) * 1000),
            )

        except Exception as e:
            return VideoFetchResult(
                success=False,
                url=url,
                error=str(e),
                response_time_ms=int((time.time() - start_time) * 1000),
            )

    def get_status(self) -> Dict[str, Any]:
        """Get current fetcher status and capabilities."""
        return {
            "available": self.is_available(),
            "has_ytdlp": HAS_YTDLP,
            "has_faster_whisper": HAS_FASTER_WHISPER,
            "has_whisper": HAS_WHISPER,
            "has_ffmpeg": self._get_ffmpeg_path() is not None,
            "whisper_model": self.whisper_model_name,
            "use_2x_speed": self.use_2x_speed,
            "device": self.device,
            "supported_platforms": [
                "YouTube", "Vimeo", "Twitter/X", "TikTok",
                "Facebook", "Instagram", "Twitch", "Dailymotion",
                "and 1000+ more via yt-dlp"
            ],
        }


# Singleton instance with thread-safe initialization
_video_fetcher: Optional[VideoFetcher] = None
_video_fetcher_lock = threading.Lock()


def get_video_fetcher() -> VideoFetcher:
    """Get the singleton video fetcher instance (thread-safe)."""
    global _video_fetcher
    if _video_fetcher is None:
        with _video_fetcher_lock:
            # Double-check after acquiring lock
            if _video_fetcher is None:
                _video_fetcher = VideoFetcher()
    return _video_fetcher
