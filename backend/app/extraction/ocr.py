"""
OCR extraction module for VisionRAG-X.

Supports Tesseract (system binary) with bounded concurrency, frame deduplication,
pre-scaling, and fallback protection. Prevents thread deadlock on macOS ARM64.
"""

import asyncio
import logging
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Callable, Coroutine, List, Optional, Tuple

from PIL import Image
import numpy as np

logger = logging.getLogger(__name__)

# Prevent OpenMP / thread deadlock on macOS ARM64
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("VECLIB_MAXIMUM_THREADS", "1")
os.environ.setdefault("NUMEXPR_NUM_THREADS", "1")


class ConfigurationError(Exception):
    """Raised when a required dependency is not installed or configured."""


class OCRExtractor:
    """
    Optical Character Recognition using Tesseract (preferred for stability on macOS)
    with safe fallback, bounded concurrency, frame deduplication, and stage timeouts.

    Groups nearby text boxes into paragraph-level segments.
    """

    def __init__(self, settings):
        self.settings = settings
        self._model = None
        self._paddleocr_available: Optional[bool] = None
        self._tesseract_path: Optional[str] = self._find_tesseract()
        self._concurrency: int = getattr(settings, "ocr_concurrency", 2) or 2

    # ------------------------------------------------------------------ #
    # Availability / model loading
    # ------------------------------------------------------------------ #

    def _find_tesseract(self) -> Optional[str]:
        """Find local tesseract executable if available."""
        candidates = [
            shutil.which("tesseract"),
            "/opt/homebrew/bin/tesseract",
            "/usr/local/bin/tesseract",
            "/usr/bin/tesseract",
        ]
        for c in candidates:
            if c and Path(c).is_file() and os.access(c, os.X_OK):
                return c
        return None

    def _check_availability(self) -> bool:
        if self._tesseract_path is not None:
            return True
        if self._paddleocr_available is None:
            try:
                import paddleocr  # noqa: F401
                self._paddleocr_available = True
            except ImportError:
                self._paddleocr_available = False
        return bool(self._paddleocr_available)

    def _load_paddle_model(self):
        """Lazy load PaddleOCR model only if Tesseract is strictly unavailable."""
        if self._model is None:
            from paddleocr import PaddleOCR
            lang = getattr(self.settings, "ocr_language", "en")
            logger.info("Loading PaddleOCR model (lang=%s)", lang)
            self._model = PaddleOCR(
                use_angle_cls=False,
                lang=lang,
                show_log=False,
                enable_mkldnn=False,
                cpu_threads=1,
            )
            logger.info("PaddleOCR model loaded successfully")

    # ------------------------------------------------------------------ #
    # Image preprocessing
    # ------------------------------------------------------------------ #

    @staticmethod
    def _prepare_image_for_ocr(image_path: Path, max_dim: int = 1920) -> Path:
        """
        Resize oversized frames to avoid excessive memory and latency during OCR.
        Returns the original path if within bounds, or a temporary resized copy.
        """
        try:
            with Image.open(image_path) as img:
                w, h = img.size
                if max(w, h) > max_dim:
                    scale = max_dim / float(max(w, h))
                    new_size = (int(w * scale), int(h * scale))
                    resized = img.resize(new_size, Image.Resampling.BILINEAR)
                    tmp_file = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
                    tmp_path = Path(tmp_file.name)
                    resized.save(tmp_path, format="JPEG", quality=85)
                    tmp_file.close()
                    return tmp_path
        except Exception as e:
            logger.debug("Failed pre-processing image %s: %s", image_path, e)
        return image_path

    # ------------------------------------------------------------------ #
    # Core OCR
    # ------------------------------------------------------------------ #

    def _run_tesseract(self, image_path: Path) -> Tuple[bool, List[dict]]:
        """
        Execute Tesseract CLI on image.
        Returns (success, raw_boxes).
        If Tesseract runs with returncode 0 and produces empty text, success is True
        and raw_boxes is [].
        """
        if not self._tesseract_path:
            return False, []
        try:
            cmd = [self._tesseract_path, str(image_path), "stdout"]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=12)
            if res.returncode == 0:
                raw_boxes = []
                if res.stdout.strip():
                    lines = [line.strip() for line in res.stdout.splitlines() if line.strip()]
                    for idx, line in enumerate(lines):
                        raw_boxes.append({
                            "text": line,
                            "confidence": 0.88,
                            "bbox": [[0, idx * 25], [100, idx * 25], [100, (idx + 1) * 25], [0, (idx + 1) * 25]],
                        })
                return True, raw_boxes
            else:
                logger.warning(
                    "Tesseract failed for %s (exit code %d): %s",
                    image_path, res.returncode, res.stderr.strip()[:200]
                )
                return False, []
        except subprocess.TimeoutExpired:
            logger.warning("Tesseract subprocess timed out after 12s for %s", image_path)
            return False, []
        except Exception as e:
            logger.warning("Tesseract execution exception for %s: %s", image_path, e)
            return False, []

    def _run_ocr(self, image_path: Path) -> List[dict]:
        """
        Run OCR on a single image and return raw bounding-box results.
        Tries Tesseract first; only falls back to PaddleOCR if Tesseract is missing
        or threw an execution failure (never on empty text).
        """
        prep_path = self._prepare_image_for_ocr(image_path)
        is_temp = prep_path != image_path
        try:
            if self._tesseract_path:
                tesseract_ok, res = self._run_tesseract(prep_path)
                if tesseract_ok:
                    # Tesseract succeeded (even if empty text)
                    return res

            # Fallback to PaddleOCR only if Tesseract was missing or crashed
            if self._paddleocr_available is not False:
                try:
                    self._load_paddle_model()
                    result = self._model.ocr(str(prep_path), cls=False)
                    raw_boxes = []
                    if result is None:
                        return raw_boxes

                    for page_result in result:
                        if page_result is None:
                            continue
                        for line in page_result:
                            bbox, (text, confidence) = line
                            raw_boxes.append({
                                "text": text,
                                "confidence": float(confidence),
                                "bbox": bbox,
                            })
                    return raw_boxes
                except Exception as e:
                    logger.warning("PaddleOCR fallback failed: %s", e)
                    return []
            return []
        finally:
            if is_temp and prep_path.exists():
                try:
                    prep_path.unlink()
                except Exception:
                    pass

    # ------------------------------------------------------------------ #
    # Text grouping
    # ------------------------------------------------------------------ #

    @staticmethod
    def _group_into_paragraphs(raw_boxes: List[dict], y_gap_threshold: float = 20.0) -> List[str]:
        """Group bounding-box text lines into paragraphs by vertical proximity."""
        if not raw_boxes:
            return []

        sorted_boxes = sorted(raw_boxes, key=lambda b: (b["bbox"][0][1], b["bbox"][0][0]))
        paragraphs: List[List[str]] = []
        current: List[str] = [sorted_boxes[0]["text"]]
        prev_y = sorted_boxes[0]["bbox"][0][1]

        for box in sorted_boxes[1:]:
            curr_y = box["bbox"][0][1]
            if abs(curr_y - prev_y) > y_gap_threshold:
                paragraphs.append(current)
                current = []
            current.append(box["text"])
            prev_y = curr_y

        if current:
            paragraphs.append(current)

        return [" ".join(lines) for lines in paragraphs]

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    async def extract_from_image(
        self,
        image_path: Path,
        source_id: str,
        timestamp: Optional[float] = None,
        page: Optional[int] = None,
        slide: Optional[int] = None,
    ) -> List[dict]:
        """
        Run OCR on a single image and return RawSegment-compatible dicts.
        Protected with an asyncio timeout to ensure the pipeline never deadlocks.
        """
        if not self._check_availability():
            raise ConfigurationError(
                f"No OCR engine (Tesseract or PaddleOCR) available for {image_path}."
            )

        image_path = Path(image_path)
        if not image_path.exists():
            logger.warning("OCR: image file not found — %s", image_path)
            return []

        def _extract():
            raw_boxes = self._run_ocr(image_path)
            if not raw_boxes:
                return []

            paragraphs = self._group_into_paragraphs(raw_boxes)
            avg_confidence = (
                sum(b["confidence"] for b in raw_boxes) / len(raw_boxes)
                if raw_boxes else 0.0
            )

            segments = []
            for para_text in paragraphs:
                if not para_text.strip():
                    continue
                seg: dict = {
                    "text": para_text,
                    "confidence": avg_confidence,
                    "modality": "ocr",
                    "source_id": source_id,
                    "raw_output": {"image_path": str(image_path)},
                }
                if timestamp is not None:
                    seg["timestamp_start"] = timestamp
                    seg["timestamp_end"] = timestamp
                if page is not None:
                    seg["page"] = page
                if slide is not None:
                    seg["slide"] = slide
                segments.append(seg)

            return segments

        loop = asyncio.get_event_loop()
        try:
            segments = await asyncio.wait_for(loop.run_in_executor(None, _extract), timeout=15.0)
        except asyncio.TimeoutError:
            logger.warning("OCR timed out after 15s for %s (continuing without OCR)", image_path)
            return []
        except ConfigurationError:
            raise
        except Exception as exc:
            logger.error("OCR failed for %s: %s", image_path, exc, exc_info=True)
            return []

        logger.debug(
            "OCR extracted %d segments from %s", len(segments), image_path.name
        )
        return segments

    # ------------------------------------------------------------------ #
    # Frame list extraction with Deduplication, Concurrency & Callbacks
    # ------------------------------------------------------------------ #

    @staticmethod
    def _compute_thumbnail_fingerprint(image_path: Path) -> Optional[np.ndarray]:
        """Compute a low-resolution grayscale thumbnail fingerprint for duplicate detection."""
        try:
            with Image.open(image_path) as img:
                thumb = img.convert("L").resize((64, 64), Image.Resampling.BILINEAR)
                return np.array(thumb, dtype=np.float32)
        except Exception:
            return None

    @staticmethod
    def _is_duplicate_frame(fp1: Optional[np.ndarray], fp2: Optional[np.ndarray], threshold_pct: float = 2.0) -> bool:
        """Return True if two frame fingerprints differ by less than threshold_pct."""
        if fp1 is None or fp2 is None:
            return False
        diff = np.mean(np.abs(fp1 - fp2)) / 255.0 * 100.0
        return diff < threshold_pct

    async def extract_from_frame_list(
        self,
        frames: List[dict],
        source_id: str,
        progress_callback: Optional[Callable[[int, int], Coroutine]] = None,
    ) -> List[dict]:
        """
        Run OCR over a list of frame dicts with:
        1. Sub-sampling if frame count exceeds ocr_max_frames.
        2. Visual duplicate frame skipping (consecutive slides).
        3. Bounded concurrency via Semaphore to prevent event loop starvation.
        4. Progress callback invocation.
        5. Overall stage timeout.
        """
        if not frames:
            return []

        max_frames = getattr(self.settings, "ocr_max_frames", 120) or 120
        timeout_seconds = float(getattr(self.settings, "ocr_timeout_seconds", 300) or 300)
        diff_threshold = float(getattr(self.settings, "ocr_frame_diff_threshold", 2.0) or 2.0)

        # 1. Sample frames if exceeding cap
        if len(frames) > max_frames:
            step = max(1, len(frames) // max_frames)
            sampled_frames = frames[::step][:max_frames]
            logger.info("Sampled %d frames from %d total for OCR", len(sampled_frames), len(frames))
        else:
            sampled_frames = frames

        total_frames = len(sampled_frames)
        semaphore = asyncio.Semaphore(self._concurrency)
        processed_count = 0

        async def _run_extraction():
            nonlocal processed_count

            # Step 1: Detect duplicate frames in milliseconds using thumbnails
            frames_to_ocr = []
            frame_duplicates_map = {}  # index -> previous_index
            prev_fp = None
            last_to_ocr_idx = None

            for i, frame in enumerate(sampled_frames):
                frame_path = Path(frame.get("frame_path", ""))
                curr_fp = self._compute_thumbnail_fingerprint(frame_path)
                if prev_fp is not None and self._is_duplicate_frame(prev_fp, curr_fp, diff_threshold) and last_to_ocr_idx is not None:
                    frame_duplicates_map[i] = last_to_ocr_idx
                else:
                    frames_to_ocr.append((i, frame))
                    last_to_ocr_idx = i
                    prev_fp = curr_fp

            # Step 2: Concurrently extract text from distinct frames with semaphore
            async def _ocr_task(idx: int, frame: dict):
                nonlocal processed_count
                frame_path = Path(frame.get("frame_path", ""))
                timestamp = frame.get("timestamp", 0.0)
                async with semaphore:
                    try:
                        segments = await self.extract_from_image(
                            frame_path,
                            source_id=source_id,
                            timestamp=timestamp,
                        )
                    except Exception as exc:
                        logger.warning("Error during OCR on frame %s: %s", frame_path, exc)
                        segments = []

                    processed_count += 1
                    if progress_callback and (processed_count % 3 == 0 or processed_count == len(frames_to_ocr)):
                        try:
                            await progress_callback(processed_count, total_frames)
                        except Exception as e:
                            logger.debug("OCR progress callback error: %s", e)

                    return idx, segments

            tasks = [_ocr_task(idx, f) for idx, f in frames_to_ocr]
            ocr_results = await asyncio.gather(*tasks) if tasks else []
            results_by_idx = dict(ocr_results)

            # Step 3: Stitch chronological segments, extending time bounds for duplicate frames
            all_segments = []
            for i, frame in enumerate(sampled_frames):
                ts = frame.get("timestamp", 0.0)
                if i in results_by_idx:
                    all_segments.extend(results_by_idx[i])
                elif i in frame_duplicates_map:
                    ref_idx = frame_duplicates_map[i]
                    for seg in results_by_idx.get(ref_idx, []):
                        seg["timestamp_end"] = ts

            logger.info(
                "OCR complete: %d segments from %d frames (%d duplicate frames skipped)",
                len(all_segments),
                total_frames,
                len(frame_duplicates_map),
            )
            return all_segments

        try:
            return await asyncio.wait_for(_run_extraction(), timeout=timeout_seconds)
        except asyncio.TimeoutError:
            logger.warning(
                "OCR stage timed out after %ds (%d/%d frames processed).",
                timeout_seconds, processed_count, total_frames
            )
            return []

    # ------------------------------------------------------------------ #
    # Health check
    # ------------------------------------------------------------------ #

    async def health_check(self) -> dict:
        available = self._check_availability()
        engine_name = "tesseract" if self._tesseract_path else ("paddleocr" if self._paddleocr_available else "none")
        lang = getattr(self.settings, "ocr_language", "en")
        return {
            "available": available,
            "engine": engine_name,
            "language": lang,
            "error": None if available else "Neither Tesseract nor PaddleOCR available",
        }
