"""
OCR extraction module for VisionRAG-X.

Supports Tesseract (system binary) and PaddleOCR for robust text extraction
from images and video frames. Prevents thread deadlock on macOS ARM64.
"""

import asyncio
import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import List, Optional

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
    or PaddleOCR with fallback protection.

    Groups nearby text boxes into paragraph-level segments.
    """

    def __init__(self, settings):
        self.settings = settings
        self._model = None
        self._paddleocr_available: Optional[bool] = None
        self._tesseract_path: Optional[str] = self._find_tesseract()

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
    # Core OCR
    # ------------------------------------------------------------------ #

    def _run_tesseract(self, image_path: Path) -> List[dict]:
        """Execute Tesseract CLI on image."""
        if not self._tesseract_path:
            return []
        try:
            cmd = [self._tesseract_path, str(image_path), "stdout"]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if res.returncode == 0 and res.stdout.strip():
                lines = [line.strip() for line in res.stdout.splitlines() if line.strip()]
                raw_boxes = []
                for idx, line in enumerate(lines):
                    raw_boxes.append({
                        "text": line,
                        "confidence": 0.88,
                        "bbox": [[0, idx * 25], [100, idx * 25], [100, (idx + 1) * 25], [0, (idx + 1) * 25]],
                    })
                return raw_boxes
        except Exception as e:
            logger.warning("Tesseract execution failed: %s", e)
        return []

    def _run_ocr(self, image_path: Path) -> List[dict]:
        """
        Run OCR on a single image and return raw bounding-box results.
        Tries Tesseract first; falls back to PaddleOCR.
        """
        if self._tesseract_path:
            res = self._run_tesseract(image_path)
            if res:
                return res

        # Fallback to PaddleOCR if Tesseract didn't return text or is missing
        try:
            self._load_paddle_model()
            result = self._model.ocr(str(image_path), cls=False)
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
            logger.warning("PaddleOCR execution failed: %s", e)
            return []

    # ------------------------------------------------------------------ #
    # Text grouping
    # ------------------------------------------------------------------ #

    @staticmethod
    def _group_into_paragraphs(raw_boxes: List[dict], y_gap_threshold: float = 20.0) -> List[str]:
        """
        Group bounding-box text lines into paragraphs by vertical proximity.
        """
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

    async def extract_from_frame_list(
        self,
        frames: List[dict],
        source_id: str,
    ) -> List[dict]:
        """Run OCR over a list of frame dicts."""
        all_segments: List[dict] = []
        for frame in frames:
            frame_path = Path(frame.get("frame_path", ""))
            timestamp = frame.get("timestamp", 0.0)
            segments = await self.extract_from_image(
                frame_path,
                source_id=source_id,
                timestamp=timestamp,
            )
            all_segments.extend(segments)

        logger.info(
            "OCR complete: %d segments from %d frames",
            len(all_segments),
            len(frames),
        )
        return all_segments

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

