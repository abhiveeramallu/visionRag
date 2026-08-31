"""
YouTube ingestion module for VisionRAG-X.

Downloads video/audio from YouTube using yt-dlp.
No DRM bypass — only publicly accessible content.
"""

import asyncio
import logging
import uuid
from pathlib import Path
from typing import Optional

import yt_dlp

logger = logging.getLogger(__name__)

MAX_DURATION_SECONDS = 7200  # 2 hours hard cap


class YouTubeIngestionError(Exception):
    """Raised when YouTube ingestion fails."""


class YouTubeIngester:
    """
    Downloads and extracts metadata from YouTube videos using yt-dlp.

    No DRM bypass is performed. Only publicly accessible, non-DRM content
    is supported. Playlists are explicitly disabled.
    """

    # ------------------------------------------------------------------ #
    # Validation
    # ------------------------------------------------------------------ #

    def validate_url(self, url: str) -> bool:
        """Return True if *url* looks like a YouTube URL."""
        if not isinstance(url, str):
            return False
        url = url.strip()
        return "youtube.com" in url or "youtu.be" in url

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

        def _extract():
            ydl_opts = {
                "quiet": True,
                "no_warnings": True,
                "skip_download": True,
                "noplaylist": True,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                try:
                    info = ydl.extract_info(url, download=False)
                except yt_dlp.utils.DownloadError as exc:
                    raise YouTubeIngestionError(
                        f"yt-dlp could not fetch metadata for {url!r}: {exc}"
                    ) from exc

            if info is None:
                raise YouTubeIngestionError(
                    f"yt-dlp returned no metadata for {url!r}"
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
            raise YouTubeIngestionError(
                f"Unexpected error fetching metadata for {url!r}: {exc}"
            ) from exc

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

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        source_id = str(uuid.uuid4())

        # Fetch metadata first to enforce duration guard
        metadata = await self.fetch_metadata(url)

        video_outtmpl = str(output_dir / f"{source_id}_video.%(ext)s")
        audio_outtmpl = str(output_dir / f"{source_id}_audio.%(ext)s")

        def _download_video():
            ydl_opts = {
                "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
                "outtmpl": video_outtmpl,
                "writeinfojson": False,
                "quiet": True,
                "no_warnings": True,
                "noplaylist": True,
                "merge_output_format": "mp4",
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                try:
                    ydl.download([url])
                except yt_dlp.utils.DownloadError as exc:
                    raise YouTubeIngestionError(
                        f"yt-dlp download failed for {url!r}: {exc}"
                    ) from exc

        def _download_audio():
            ydl_opts = {
                "format": "bestaudio/best",
                "outtmpl": audio_outtmpl,
                "writeinfojson": False,
                "quiet": True,
                "no_warnings": True,
                "noplaylist": True,
                "postprocessors": [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "m4a",
                        "preferredquality": "0",
                    }
                ],
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                try:
                    ydl.download([url])
                except yt_dlp.utils.DownloadError as exc:
                    raise YouTubeIngestionError(
                        f"yt-dlp audio download failed for {url!r}: {exc}"
                    ) from exc

        loop = asyncio.get_event_loop()
        try:
            logger.info("Downloading video: %s", url)
            await loop.run_in_executor(None, _download_video)
            logger.info("Downloading audio: %s", url)
            await loop.run_in_executor(None, _download_audio)
        except YouTubeIngestionError:
            raise
        except Exception as exc:
            raise YouTubeIngestionError(
                f"Unexpected error downloading {url!r}: {exc}"
            ) from exc

        # Locate the downloaded files (yt-dlp substitutes %(ext)s)
        file_path = _find_downloaded_file(output_dir, f"{source_id}_video")
        audio_path = _find_downloaded_file(output_dir, f"{source_id}_audio")

        if file_path is None:
            raise YouTubeIngestionError(
                f"Downloaded video file not found in {output_dir} for source_id={source_id}"
            )
        if audio_path is None:
            logger.warning(
                "Downloaded audio file not found in %s for source_id=%s; "
                "audio extraction may be needed separately.",
                output_dir,
                source_id,
            )

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
    Return the first file in *directory* whose stem starts with *stem_prefix*.
    yt-dlp substitutes the extension at download time, so we can't predict it.
    """
    matches = sorted(directory.glob(f"{stem_prefix}*"))
    for candidate in matches:
        if candidate.is_file():
            return candidate
    return None
