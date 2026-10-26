"""
YouTube ingestion module for VisionRAG-X.

Downloads video/audio from YouTube using yt-dlp.
No DRM bypass — only publicly accessible content.
"""

import asyncio
import logging
import shutil
import subprocess
import uuid
from pathlib import Path
from typing import Optional
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

import yt_dlp

logger = logging.getLogger(__name__)

MAX_DURATION_SECONDS = 7200  # 2 hours hard cap

# Format selector prioritizing universally decodable H.264 (avc1) video
# with M4A audio, and falling back gracefully to any valid video/audio stream.
VIDEO_FORMAT_SELECTOR = (
    "bestvideo[ext=mp4][vcodec^=avc1]+bestaudio[ext=m4a]/"
    "bestvideo[ext=mp4][vcodec^=avc1]+bestaudio/"
    "bestvideo[vcodec^=avc1]+bestaudio/"
    "bestvideo[ext=mp4]+bestaudio[ext=m4a]/"
    "bestvideo[ext=mp4]+bestaudio/"
    "bestvideo+bestaudio/"
    "best[ext=mp4][vcodec^=avc1]/"
    "best[ext=mp4]/"
    "best"
)

AUDIO_FORMAT_SELECTOR = "bestaudio[ext=m4a]/bestaudio/best"


class YouTubeIngestionError(Exception):
    """Raised when YouTube ingestion fails."""


def get_ffmpeg_location() -> Optional[str]:
    """Find the path of the ffmpeg executable across standard macOS and Linux locations."""
    candidate = shutil.which("ffmpeg")
    if candidate and Path(candidate).exists():
        return candidate
    for p in ["/opt/homebrew/bin/ffmpeg", "/usr/local/bin/ffmpeg", "/usr/bin/ffmpeg"]:
        if Path(p).exists():
            return p
    return None


def classify_youtube_error(exc: Exception, url: str) -> str:
    """
    Translate raw yt-dlp or network exceptions into clear, human-readable explanations.
    """
    msg = str(exc)
    lower = msg.lower()

    if "requested format is not available" in lower:
        return f"Requested video/audio format could not be found for {url}. No compatible stream is available."

    if any(k in lower for k in ["failed to resolve", "name or service not known", "connection refused", "timed out", "unreachable", "errno 8", "errno 54"]):
        return f"Network error connecting to YouTube. Please check network connectivity and retry ({url})."

    if "too many requests" in lower or "429" in lower:
        return f"YouTube rate limit reached (HTTP 429). Please wait before retrying ({url})."

    if any(k in lower for k in ["sign in to confirm your age", "confirm your age", "age-restricted", "inappropriate for some users"]):
        return f"This YouTube video requires age verification or sign-in, which is not supported ({url})."

    if any(k in lower for k in ["country", "georestricted", "uploader has not made this video available"]):
        return f"This YouTube video is not available in your region ({url})."

    if any(k in lower for k in ["private video", "removed", "video unavailable", "not available"]):
        return f"This YouTube video is unavailable, deleted, or private ({url})."

    if any(k in lower for k in ["sign in", "login required", "members-only", "requires payment"]):
        return f"This YouTube video requires authentication or membership ({url})."

    return f"YouTube ingestion failed: {msg}"


class YouTubeIngester:
    """
    Downloads and extracts metadata from YouTube videos using yt-dlp.

    No DRM bypass is performed. Only publicly accessible, non-DRM content
    is supported. Playlists are explicitly disabled.
    """

    # ------------------------------------------------------------------ #
    # Validation & Cleaning
    # ------------------------------------------------------------------ #

    def validate_url(self, url: str) -> bool:
        """Return True if *url* looks like a YouTube URL."""
        if not isinstance(url, str):
            return False
        url = url.strip()
        return "youtube.com" in url or "youtu.be" in url

    def clean_url(self, url: str) -> str:
        """
        Normalize a YouTube video URL by removing playlist or tracking parameters,
        ensuring yt-dlp downloads only the intended single video.
        """
        if not isinstance(url, str):
            return ""
        url = url.strip()
        try:
            parsed = urlparse(url)
            if "youtube.com" in parsed.netloc and "/watch" in parsed.path:
                qs = parse_qs(parsed.query)
                if "v" in qs:
                    clean_qs = urlencode({"v": qs["v"][0]})
                    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", clean_qs, ""))
            elif "youtu.be" in parsed.netloc:
                # Strip query parameters (like ?t=... or ?list=...)
                clean_path = parsed.path
                return urlunparse((parsed.scheme, parsed.netloc, clean_path, "", "", ""))
        except Exception as exc:
            logger.debug("Failed to normalize URL %r: %s", url, exc)
        return url

    # ------------------------------------------------------------------ #
    # Metadata
    # ------------------------------------------------------------------ #

    async def fetch_metadata(self, url: str) -> dict:
        """
        Fetch video metadata without downloading.

        Parameters
        ----------
        url:
            YouTube video URL.

        Returns
        -------
        dict with keys: title, duration, channel, upload_date,
                        description, thumbnail, id
        """
        if not self.validate_url(url):
            raise YouTubeIngestionError(f"Invalid YouTube URL: {url!r}")

        clean_url = self.clean_url(url)

        def _extract():
            ydl_opts = {
                "quiet": True,
                "no_warnings": True,
                "skip_download": True,
                "noplaylist": True,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                try:
                    info = ydl.extract_info(clean_url, download=False)
                except Exception as exc:
                    classified = classify_youtube_error(exc, clean_url)
                    raise YouTubeIngestionError(classified) from exc

            if info is None:
                raise YouTubeIngestionError(
                    f"yt-dlp returned no metadata for {clean_url!r}"
                )

            duration = info.get("duration") or 0
            if duration > MAX_DURATION_SECONDS:
                raise YouTubeIngestionError(
                    f"Video duration {duration}s exceeds maximum allowed "
                    f"{MAX_DURATION_SECONDS}s."
                )

            return {
                "title": info.get("title", ""),
                "duration": duration,
                "channel": info.get("channel") or info.get("uploader", ""),
                "upload_date": info.get("upload_date", ""),
                "description": info.get("description", ""),
                "thumbnail": info.get("thumbnail", ""),
                "id": info.get("id", ""),
            }

        loop = asyncio.get_event_loop()
        try:
            metadata = await loop.run_in_executor(None, _extract)
        except YouTubeIngestionError:
            raise
        except Exception as exc:
            classified = classify_youtube_error(exc, clean_url)
            raise YouTubeIngestionError(classified) from exc

        logger.info(
            "Fetched metadata for '%s' (id=%s, duration=%ss)",
            metadata["title"],
            metadata["id"],
            metadata["duration"],
        )
        return metadata

    # ------------------------------------------------------------------ #
    # Download
    # ------------------------------------------------------------------ #

    async def download(self, url: str, output_dir: Path) -> dict:
        """
        Download video (best mp4) and audio (best m4a) from YouTube.

        Parameters
        ----------
        url:
            YouTube video URL.
        output_dir:
            Directory where downloaded files are saved.

        Returns
        -------
        dict with keys: file_path, audio_path, metadata, source_id,
                        title, duration, channel, upload_date
        """
        if not self.validate_url(url):
            raise YouTubeIngestionError(f"Invalid YouTube URL: {url!r}")

        clean_url = self.clean_url(url)
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        source_id = str(uuid.uuid4())

        # Fetch metadata first to enforce duration guard and obtain source info
        metadata = await self.fetch_metadata(clean_url)

        video_outtmpl = str(output_dir / f"{source_id}_video.%(ext)s")
        audio_outtmpl = str(output_dir / f"{source_id}_audio.%(ext)s")

        ffmpeg_loc = get_ffmpeg_location()

        def _download_video():
            ydl_opts = {
                "format": VIDEO_FORMAT_SELECTOR if ffmpeg_loc else "best[ext=mp4][vcodec^=avc1]/best[ext=mp4]/best",
                "outtmpl": video_outtmpl,
                "writeinfojson": False,
                "quiet": True,
                "no_warnings": True,
                "noplaylist": True,
            }
            if ffmpeg_loc:
                ydl_opts["ffmpeg_location"] = ffmpeg_loc
                ydl_opts["merge_output_format"] = "mp4"

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                try:
                    ydl.download([clean_url])
                except Exception as exc:
                    classified = classify_youtube_error(exc, clean_url)
                    raise YouTubeIngestionError(classified) from exc

        def _download_audio():
            ydl_opts = {
                "format": AUDIO_FORMAT_SELECTOR,
                "outtmpl": audio_outtmpl,
                "writeinfojson": False,
                "quiet": True,
                "no_warnings": True,
                "noplaylist": True,
            }
            if ffmpeg_loc:
                ydl_opts["ffmpeg_location"] = ffmpeg_loc
                ydl_opts["postprocessors"] = [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "m4a",
                        "preferredquality": "0",
                    }
                ]

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                try:
                    ydl.download([clean_url])
                except Exception as exc:
                    logger.warning("Separate audio stream download failed: %s", exc)

        loop = asyncio.get_event_loop()
        try:
            logger.info("Downloading video: %s", clean_url)
            await loop.run_in_executor(None, _download_video)
        except YouTubeIngestionError:
            raise
        except Exception as exc:
            classified = classify_youtube_error(exc, clean_url)
            raise YouTubeIngestionError(classified) from exc

        # Locate downloaded video
        file_path = _find_downloaded_file(output_dir, f"{source_id}_video")
        if file_path is None or not file_path.exists() or file_path.stat().st_size == 0:
            raise YouTubeIngestionError(
                f"Downloaded video file not found or empty in {output_dir} for {clean_url}"
            )

        # Attempt separate audio download or extract audio from the downloaded video
        audio_path = None
        try:
            logger.info("Attempting audio retrieval: %s", clean_url)
            await loop.run_in_executor(None, _download_audio)
            audio_path = _find_downloaded_file(output_dir, f"{source_id}_audio")
        except Exception as exc:
            logger.warning("Separate audio download encountered issue: %s", exc)

        # Fallback: if separate audio was not created, extract directly from video file via ffmpeg
        if audio_path is None or not audio_path.exists() or audio_path.stat().st_size == 0:
            logger.info("Extracting audio from downloaded video: %s", file_path)
            target_audio_file = output_dir / f"{source_id}_audio.m4a"
            audio_path = _extract_audio_from_video(file_path, target_audio_file)

        logger.info(
            "Download complete — video: %s, audio: %s",
            file_path,
            audio_path,
        )

        return {
            "file_path": str(file_path) if file_path else None,
            "audio_path": str(audio_path) if audio_path else None,
            "metadata": metadata,
            "source_id": source_id,
            "title": metadata["title"],
            "duration": metadata["duration"],
            "channel": metadata["channel"],
            "upload_date": metadata["upload_date"],
        }


# ------------------------------------------------------------------ #
# Helpers
# ------------------------------------------------------------------ #

def _find_downloaded_file(directory: Path, stem_prefix: str) -> Optional[Path]:
    """
    Return the first non-empty file in *directory* whose name starts with *stem_prefix*.
    yt-dlp substitutes the extension at download time, so we can't predict it.
    """
    matches = sorted(directory.glob(f"{stem_prefix}*"))
    for candidate in matches:
        if candidate.is_file() and candidate.stat().st_size > 0:
            if not candidate.name.endswith((".part", ".ytdl", ".temp")):
                return candidate
    return None


def _extract_audio_from_video(video_path: Path, target_audio_path: Path) -> Optional[Path]:
    """Extract audio from downloaded video file via ffmpeg as fallback."""
    ffmpeg_binary = get_ffmpeg_location() or "ffmpeg"
    try:
        cmd = [
            ffmpeg_binary,
            "-y",
            "-i", str(video_path),
            "-vn",
            "-acodec", "aac",
            "-b:a", "192k",
            str(target_audio_path),
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if res.returncode == 0 and target_audio_path.exists() and target_audio_path.stat().st_size > 0:
            return target_audio_path
        else:
            logger.warning("FFmpeg audio fallback failed with rc=%s: %s", res.returncode, res.stderr)
    except Exception as exc:
        logger.warning("FFmpeg audio fallback execution error: %s", exc)
    return None
