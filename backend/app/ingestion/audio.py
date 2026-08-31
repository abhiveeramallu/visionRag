"""
Audio ingestion module for VisionRAG-X.

Prepares audio files for downstream ASR processing.
"""

import asyncio
import json
import logging
import subprocess
from pathlib import Path

import ffmpeg

logger = logging.getLogger(__name__)


class AudioIngestionError(Exception):
    """Raised when audio ingestion fails."""


class AudioIngester:
    """
    Prepares audio files for speech recognition.

    Converts arbitrary audio to 16 kHz mono WAV using ffmpeg, and
    exposes metadata via ffprobe.
    """

    # ------------------------------------------------------------------ #
    # Preparation
    # ------------------------------------------------------------------ #

    async def prepare_audio(self, audio_path: Path, output_dir: Path) -> Path:
        """
        Ensure audio is in 16 kHz mono WAV format.

        If *audio_path* is already a WAV file the content is still
        normalised to 16 kHz mono to guarantee ASR compatibility.

        Parameters
        ----------
        audio_path:
            Path to the source audio file.
        output_dir:
            Directory where the prepared WAV is written.

        Returns
        -------
        Path to the prepared WAV file.
        """
        audio_path = Path(audio_path)
        output_dir = Path(output_dir)

        if not audio_path.exists():
            raise AudioIngestionError(f"Audio file not found: {audio_path}")

        output_dir.mkdir(parents=True, exist_ok=True)
        out_path = output_dir / f"{audio_path.stem}_prepared.wav"

        # If the file is already a properly formatted WAV, skip re-encoding
        # by checking its metadata first.
        if audio_path.suffix.lower() == ".wav":
            try:
                meta = self.get_audio_metadata(audio_path)
                if meta["sample_rate"] == 16000 and meta["channels"] == 1:
                    logger.info(
                        "Audio already 16 kHz mono WAV — copying: %s", audio_path
                    )
                    import shutil
                    shutil.copy2(str(audio_path), str(out_path))
                    return out_path
            except AudioIngestionError:
                pass  # Fall through to ffmpeg conversion

        def _convert():
            try:
                (
                    ffmpeg
                    .input(str(audio_path))
                    .output(
                        str(out_path),
                        acodec="pcm_s16le",
                        ar=16000,
                        ac=1,
                    )
                    .overwrite_output()
                    .run(quiet=True)
                )
            except ffmpeg.Error as exc:
                stderr = exc.stderr.decode("utf-8", errors="replace") if exc.stderr else ""
                raise AudioIngestionError(
                    f"ffmpeg conversion failed for {audio_path}: {stderr}"
                ) from exc

        loop = asyncio.get_event_loop()
        try:
            await loop.run_in_executor(None, _convert)
        except AudioIngestionError:
            raise
        except Exception as exc:
            raise AudioIngestionError(
                f"Unexpected error preparing audio {audio_path}: {exc}"
            ) from exc

        logger.info("Prepared audio: %s -> %s", audio_path, out_path)
        return out_path

    # ------------------------------------------------------------------ #
    # Metadata
    # ------------------------------------------------------------------ #

    def get_audio_metadata(self, audio_path: Path) -> dict:
        """
        Return audio file metadata via ffprobe.

        Parameters
        ----------
        audio_path:
            Path to the audio file.

        Returns
        -------
        dict with keys: duration, sample_rate, channels, format, size_bytes
        """
        audio_path = Path(audio_path)
        if not audio_path.exists():
            raise AudioIngestionError(f"Audio file not found: {audio_path}")

        cmd = [
            "ffprobe",
            "-v", "quiet",
            "-print_format", "json",
            "-show_streams",
            "-show_format",
            str(audio_path),
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
            )
        except FileNotFoundError as exc:
            raise AudioIngestionError(
                "ffprobe not found. Ensure ffmpeg is installed and on PATH."
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise AudioIngestionError(
                f"ffprobe timed out for {audio_path}"
            ) from exc

        if result.returncode != 0:
            raise AudioIngestionError(
                f"ffprobe failed for {audio_path}: {result.stderr}"
            )

        try:
            info = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise AudioIngestionError(
                f"Could not parse ffprobe output for {audio_path}: {exc}"
            ) from exc

        # Extract the first audio stream
        audio_stream = next(
            (s for s in info.get("streams", []) if s.get("codec_type") == "audio"),
            None,
        )

        if audio_stream is None:
            raise AudioIngestionError(
                f"No audio stream found in {audio_path}"
            )

        fmt = info.get("format", {})
        duration = float(audio_stream.get("duration") or fmt.get("duration") or 0.0)
        sample_rate = int(audio_stream.get("sample_rate") or 0)
        channels = int(audio_stream.get("channels") or 0)
        fmt_name = fmt.get("format_long_name") or fmt.get("format_name") or "unknown"
        size_bytes = audio_path.stat().st_size

        return {
            "duration": duration,
            "sample_rate": sample_rate,
            "channels": channels,
            "format": fmt_name,
            "size_bytes": size_bytes,
        }
