"""
Video ingestion module for VisionRAG-X.

Handles audio extraction and frame sampling from video files.
"""

import asyncio
import logging
from pathlib import Path
from typing import List, Optional

import cv2
import ffmpeg

logger = logging.getLogger(__name__)


class VideoIngestionError(Exception):
    """Raised when video ingestion fails."""


class VideoIngester:
    """
    Extracts audio and frames from local video files.

    Uses ffmpeg-python for audio extraction and OpenCV for frame sampling.
    """

    # ------------------------------------------------------------------ #
    # Audio extraction
    # ------------------------------------------------------------------ #

    async def extract_audio(self, video_path: Path, output_dir: Path) -> Path:
        """
        Extract audio from a video file as 16 kHz mono WAV.

        Parameters
        ----------
        video_path:
            Path to the source video file.
        output_dir:
            Directory where the WAV file will be written.

        Returns
        -------
        Path to the extracted WAV file.
        """
        video_path = Path(video_path)
        output_dir = Path(output_dir)

        if not video_path.exists():
            raise VideoIngestionError(f"Video file not found: {video_path}")

        output_dir.mkdir(parents=True, exist_ok=True)
        audio_path = output_dir / f"{video_path.stem}_audio.wav"

        def _extract():
            try:
                (
                    ffmpeg
                    .input(str(video_path))
                    .output(
                        str(audio_path),
                        acodec="pcm_s16le",
                        ar=16000,
                        ac=1,
                        vn=None,          # no video stream
                    )
                    .overwrite_output()
                    .run(quiet=True)
                )
            except ffmpeg.Error as exc:
                stderr = exc.stderr.decode("utf-8", errors="replace") if exc.stderr else ""
                raise VideoIngestionError(
                    f"ffmpeg audio extraction failed for {video_path}: {stderr}"
                ) from exc

        loop = asyncio.get_event_loop()
        try:
            await loop.run_in_executor(None, _extract)
        except VideoIngestionError:
            raise
        except Exception as exc:
            raise VideoIngestionError(
                f"Unexpected error extracting audio from {video_path}: {exc}"
            ) from exc

        logger.info("Extracted audio: %s", audio_path)
        return audio_path

    # ------------------------------------------------------------------ #
    # Frame extraction
    # ------------------------------------------------------------------ #

    async def extract_frames(
        self,
        video_path: Path,
        output_dir: Path,
        interval_seconds: Optional[float] = None,
    ) -> List[dict]:
        """
        Sample frames from a video at a configurable interval.

        Parameters
        ----------
        video_path:
            Path to the source video file.
        output_dir:
            Directory where JPEG frames will be written.
        interval_seconds:
            Seconds between sampled frames. Defaults to 1 frame per second.

        Returns
        -------
        List of dicts: [{frame_path: str, timestamp: float}, ...]
        """
        video_path = Path(video_path)
        output_dir = Path(output_dir)

        if not video_path.exists():
            raise VideoIngestionError(f"Video file not found: {video_path}")

        output_dir.mkdir(parents=True, exist_ok=True)

        def _extract():
            cap = cv2.VideoCapture(str(video_path))
            if not cap.isOpened():
                raise VideoIngestionError(
                    f"OpenCV could not open video: {video_path}"
                )

            fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            duration = total_frames / fps if fps > 0 else 0.0

            interval = interval_seconds if interval_seconds and interval_seconds > 0 else 1.0
            frame_interval = max(1, int(fps * interval))

            frames = []
            frame_idx = 0
            saved_idx = 0

            try:
                while True:
                    ret, frame = cap.read()
                    if not ret:
                        break

                    if frame_idx % frame_interval == 0:
                        timestamp = frame_idx / fps
                        ts_str = _seconds_to_timestamp(timestamp)
                        frame_filename = f"frame_{saved_idx:06d}_{ts_str.replace(':', '-')}.jpg"
                        frame_path = output_dir / frame_filename

                        ok = cv2.imwrite(str(frame_path), frame)
                        if not ok:
                            logger.warning(
                                "Failed to write frame %d to %s", frame_idx, frame_path
                            )
                        else:
                            frames.append(
                                {
                                    "frame_path": str(frame_path),
                                    "timestamp": timestamp,
                                }
                            )
                        saved_idx += 1

                    frame_idx += 1
            finally:
                cap.release()

            logger.info(
                "Extracted %d frames from %s (interval=%.1fs, duration=%.1fs)",
                len(frames),
                video_path,
                interval,
                duration,
            )
            return frames

        loop = asyncio.get_event_loop()
        try:
            frames = await loop.run_in_executor(None, _extract)
        except VideoIngestionError:
            raise
        except Exception as exc:
            raise VideoIngestionError(
                f"Unexpected error extracting frames from {video_path}: {exc}"
            ) from exc

        return frames

    # ------------------------------------------------------------------ #
    # Metadata
    # ------------------------------------------------------------------ #

    def get_video_metadata(self, video_path: Path) -> dict:
        """
        Return basic metadata for a video file.

        Returns
        -------
        dict with keys: duration, fps, width, height, frame_count,
                        size_bytes, codec
        """
        video_path = Path(video_path)
        if not video_path.exists():
            raise VideoIngestionError(f"Video file not found: {video_path}")

        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            raise VideoIngestionError(f"OpenCV could not open video: {video_path}")

        try:
            fps = cap.get(cv2.CAP_PROP_FPS)
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            duration = frame_count / fps if fps > 0 else 0.0
            fourcc_int = int(cap.get(cv2.CAP_PROP_FOURCC))
            codec = "".join(chr((fourcc_int >> 8 * i) & 0xFF) for i in range(4)).strip("\x00")
        finally:
            cap.release()

        size_bytes = video_path.stat().st_size

        return {
            "duration": duration,
            "fps": fps,
            "width": width,
            "height": height,
            "frame_count": frame_count,
            "size_bytes": size_bytes,
            "codec": codec,
        }

    # ------------------------------------------------------------------ #
    # Utilities
    # ------------------------------------------------------------------ #

    @staticmethod
    def _seconds_to_timestamp(seconds: float) -> str:
        """Convert float seconds to '00:14:32.450' format."""
        return _seconds_to_timestamp(seconds)


# ------------------------------------------------------------------ #
# Module-level helper (shared with extract_frames inner func)
# ------------------------------------------------------------------ #

def _seconds_to_timestamp(seconds: float) -> str:
    """Convert float seconds to 'HH:MM:SS.mmm' format."""
    seconds = max(0.0, float(seconds))
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs:06.3f}"
