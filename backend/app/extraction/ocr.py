"""
OCR extraction module for VisionRAG-X.

Wraps PaddleOCR for text extraction from images and video frames.
"""

import asyncio
import logging
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)


class ConfigurationError(Exception):
    """Raised when a required dependency is not installed or configured."""


class OCRExtractor:
    """
    Optical Character Recognition using PaddleOCR.

    Lazy-loads the PaddleOCR model on first use. Groups nearby text boxes
    into paragraph-level segments.

    EXPERIMENTAL: OCR accuracy depends on image quality and font clarity.
    """

    def __init__(self, settings):
        self.settings = settings
        self._model = None
        self._paddleocr_available: Optional[bool] = None

    # ------------------------------------------------------------------ #
    # Availability / model loading
    # ------------------------------------------------------------------ #

    def _check_availability(self) -> bool:
        if self._paddleocr_available is None:
            try:
                import paddleocr  # noqa: F401
                self._paddleocr_available = True
            except ImportError:
                self._paddleocr_available = False
        return self._paddleocr_available

    def _load_model(self):
        if not self._check_availability():
            raise ConfigurationError(
                "PaddleOCR is not installed. "
                "Install with: pip install paddleocr\n"
                "Note: PaddleOCR also requires paddlepaddle. "
                "See https://www.paddlepaddle.org.cn/install/quick for details."
            )
        if self._model is None:
            from paddleocr import PaddleOCR
            lang = getattr(self.settings, "ocr_language", "en")
            logger.info("Loading PaddleOCR model (lang=%s)", lang)
            self._model = PaddleOCR(use_angle_cls=True, lang=lang, show_log=False)
            logger.info("PaddleOCR model loaded successfully")

    # ------------------------------------------------------------------ #
    # Core OCR
    # ------------------------------------------------------------------ #

    def _run_ocr(self, image_path: Path) -> List[dict]:
        """
        Run PaddleOCR on a single image and return raw bounding-box results.

        Returns list of dicts: {text, confidence, bbox: [[x,y], ...]}
        """
        self._load_model()
        result = self._model.ocr(str(image_path), cls=True)

        raw_boxes = []
        if result is None:
            return raw_boxes

        # PaddleOCR returns List[List[box_result]] where box_result = [bbox, (text, confidence)]
        for page_result in result:
            if page_result is None:
                continue
            for line in page_result:
                bbox, (text, confidence) = line
                raw_boxes.append(
                    {
                        "text": text,
                        "confidence": float(confidence),
                        "bbox": bbox,  # [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
                    }
                )
        return raw_boxes

    # ------------------------------------------------------------------ #
    # Text grouping
    # ------------------------------------------------------------------ #

    @staticmethod
    def _group_into_paragraphs(raw_boxes: List[dict], y_gap_threshold: float = 20.0) -> List[str]:
        """
        Group bounding-box text lines into paragraphs by vertical proximity.

        Lines whose top-left y-coordinates are within *y_gap_threshold*
        pixels of the previous line are merged into the same paragraph.
        """
        if not raw_boxes:
            return []

        # Sort by top-left y, then x
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

        Parameters
        ----------
        image_path:
            Path to the image file.
        source_id:
            Identifier for the originating document/video.
        timestamp:
            Optional video timestamp in seconds (for frame-sourced images).
        page:
            Optional page number (for PDF/PPT-sourced images).
        slide:
            Optional slide number (alias for page in PPT context).

        Returns
        -------
        List of dicts compatible with RawSegment, each with modality='ocr'.
        """
        if not self._check_availability():
            raise ConfigurationError(
                f"PaddleOCR not available. Cannot extract OCR from {image_path}. "
                "Install paddleocr and paddlepaddle."
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
            segments = await loop.run_in_executor(None, _extract)
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
        """
        Run OCR over a list of frame dicts (as returned by VideoIngester).

        Parameters
        ----------
        frames:
            List of ``{frame_path: str, timestamp: float}`` dicts.
        source_id:
            Identifier for the originating video.

        Returns
        -------
        All OCR segments from all frames, each carrying a timestamp.
        """
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
        lang = getattr(self.settings, "ocr_language", "en")
        return {
            "available": available,
            "language": lang,
            "error": None if available else "paddleocr not installed",
        }
