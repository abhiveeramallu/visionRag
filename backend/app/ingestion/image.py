"""
Image ingestion module for VisionRAG-X.

Simple metadata extractor for standalone image files using Pillow.
"""

import logging
from pathlib import Path

from PIL import Image

logger = logging.getLogger(__name__)


class ImageIngestionError(Exception):
    """Raised when image ingestion fails."""


class ImageIngester:
    """
    Extracts metadata from a standalone image file.

    Thin wrapper around Pillow; no heavy processing is performed here —
    the heavy lifting (OCR, vision description) is done by extraction modules.
    """

    async def extract(self, image_path: Path) -> dict:
        """
        Return metadata for a single image file.

        Parameters
        ----------
        image_path:
            Path to the image file (JPEG, PNG, BMP, TIFF, WebP, etc.).

        Returns
        -------
        dict with keys: image_path, width, height, format, mode, size_bytes
        """
        image_path = Path(image_path)
        if not image_path.exists():
            raise ImageIngestionError(f"Image file not found: {image_path}")

        try:
            with Image.open(str(image_path)) as img:
                width, height = img.size
                fmt = img.format or image_path.suffix.lstrip(".").upper()
                mode = img.mode
        except Exception as exc:
            raise ImageIngestionError(
                f"Pillow could not open image {image_path}: {exc}"
            ) from exc

        size_bytes = image_path.stat().st_size

        logger.debug(
            "Image metadata: %s — %dx%d %s (%s, %d bytes)",
            image_path.name, width, height, fmt, mode, size_bytes,
        )

        return {
            "image_path": str(image_path),
            "width": width,
            "height": height,
            "format": fmt,
            "mode": mode,
            "size_bytes": size_bytes,
        }
