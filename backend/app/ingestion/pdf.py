"""
PDF ingestion module for VisionRAG-X.

Extracts text and images from PDF files using PyMuPDF (fitz).
"""

import asyncio
import logging
from pathlib import Path
from typing import List

import fitz  # PyMuPDF

logger = logging.getLogger(__name__)


class PDFIngestionError(Exception):
    """Raised when PDF ingestion fails."""


class PDFIngester:
    """
    Extracts structured content (text + images) from PDF files.

    Uses PyMuPDF (fitz) for high-fidelity text extraction and
    embedded image export.
    """

    # ------------------------------------------------------------------ #
    # Extraction
    # ------------------------------------------------------------------ #

    async def extract(self, pdf_path: Path, output_dir: Path) -> List[dict]:
        """
        Extract text and images from every page of a PDF.

        Parameters
        ----------
        pdf_path:
            Path to the PDF file.
        output_dir:
            Root directory for extracted assets. Images are saved under
            ``output_dir/images/``.

        Returns
        -------
        List of page dicts::

            [
                {
                    "page_num": int,          # 1-indexed
                    "text": str,
                    "images": [
                        {
                            "image_path": str,
                            "width": int,
                            "height": int,
                        },
                        ...
                    ],
                },
                ...
            ]
        """
        pdf_path = Path(pdf_path)
        output_dir = Path(output_dir)

        if not pdf_path.exists():
            raise PDFIngestionError(f"PDF file not found: {pdf_path}")

        images_dir = output_dir / "images"
        images_dir.mkdir(parents=True, exist_ok=True)

        def _extract():
            try:
                doc = fitz.open(str(pdf_path))
            except Exception as exc:
                raise PDFIngestionError(
                    f"PyMuPDF could not open {pdf_path}: {exc}"
                ) from exc

            pages = []
            try:
                for page_idx in range(len(doc)):
                    page = doc[page_idx]
                    page_num = page_idx + 1  # 1-indexed

                    # --- Text ---
                    try:
                        text = page.get_text()
                    except Exception as exc:
                        logger.warning(
                            "Failed to extract text from page %d of %s: %s",
                            page_num, pdf_path, exc,
                        )
                        text = ""

                    # --- Images ---
                    image_records = []
                    try:
                        image_list = page.get_images(full=True)
                    except Exception as exc:
                        logger.warning(
                            "Failed to list images on page %d of %s: %s",
                            page_num, pdf_path, exc,
                        )
                        image_list = []

                    for img_idx, img_info in enumerate(image_list):
                        xref = img_info[0]
                        try:
                            base_img = doc.extract_image(xref)
                            img_bytes = base_img["image"]
                            img_ext = base_img.get("ext", "png")
                            img_w = base_img.get("width", 0)
                            img_h = base_img.get("height", 0)

                            img_filename = f"page_{page_num}_img_{img_idx + 1}.png"
                            img_path = images_dir / img_filename

                            # Prefer PNG output for lossless archival
                            if img_ext.lower() in ("png", "jpeg", "jpg", "bmp", "tiff"):
                                img_path.write_bytes(img_bytes)
                            else:
                                # Use fitz Pixmap for conversion to PNG
                                pix = fitz.Pixmap(doc, xref)
                                if pix.n > 4:  # CMYK → RGB
                                    pix = fitz.Pixmap(fitz.csRGB, pix)
                                pix.save(str(img_path))

                            image_records.append(
                                {
                                    "image_path": str(img_path),
                                    "width": img_w,
                                    "height": img_h,
                                }
                            )
                        except Exception as exc:
                            logger.warning(
                                "Failed to extract image %d on page %d of %s: %s",
                                img_idx + 1, page_num, pdf_path, exc,
                            )

                    pages.append(
                        {
                            "page_num": page_num,
                            "text": text,
                            "images": image_records,
                        }
                    )
            finally:
                doc.close()

            logger.info(
                "Extracted %d pages from %s (%d images total)",
                len(pages),
                pdf_path,
                sum(len(p["images"]) for p in pages),
            )
            return pages

        loop = asyncio.get_event_loop()
        try:
            pages = await loop.run_in_executor(None, _extract)
        except PDFIngestionError:
            raise
        except Exception as exc:
            raise PDFIngestionError(
                f"Unexpected error extracting {pdf_path}: {exc}"
            ) from exc

        return pages

    # ------------------------------------------------------------------ #
    # Metadata
    # ------------------------------------------------------------------ #

    def get_metadata(self, pdf_path: Path) -> dict:
        """
        Return document-level metadata for a PDF.

        Returns
        -------
        dict with keys: num_pages, title, author, subject,
                        creation_date, file_size
        """
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            raise PDFIngestionError(f"PDF file not found: {pdf_path}")

        try:
            doc = fitz.open(str(pdf_path))
        except Exception as exc:
            raise PDFIngestionError(
                f"PyMuPDF could not open {pdf_path}: {exc}"
            ) from exc

        try:
            num_pages = len(doc)
            meta = doc.metadata or {}
        finally:
            doc.close()

        return {
            "num_pages": num_pages,
            "title": meta.get("title", ""),
            "author": meta.get("author", ""),
            "subject": meta.get("subject", ""),
            "creation_date": meta.get("creationDate", ""),
            "file_size": pdf_path.stat().st_size,
        }
