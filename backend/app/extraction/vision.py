"""
Vision extraction module for VisionRAG-X.

Placeholder for multimodal vision model integration.
When a vision model is configured, this module will produce natural-language
descriptions of video frames or document page images.
"""

import logging
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)


class VisionExtractor:
    """
    Describes images / video frames using a vision language model (VLM).

    Currently a configured placeholder — the actual API integration must
    be added once a vision model backend is chosen (e.g. GPT-4o, Gemini
    Vision, LLaVA, or a self-hosted model via Ollama/vLLM).

    Configuration
    -------------
    Set ``settings.vision_model`` to a non-empty string to enable.
    When not configured, all methods silently return empty results.
    """

    def __init__(self, settings):
        self.settings = settings

    # ------------------------------------------------------------------ #
    # Properties
    # ------------------------------------------------------------------ #

    @property
    def is_configured(self) -> bool:
        """True if a vision model has been specified in settings."""
        return bool(getattr(self.settings, "vision_model", None))

    # ------------------------------------------------------------------ #
    # Frame description
    # ------------------------------------------------------------------ #

    async def describe_frame(
        self,
        image_path: Path,
        source_id: str,
        timestamp: Optional[float] = None,
        page: Optional[int] = None,
    ) -> Optional[dict]:
        """
        Produce a natural-language description of a single image.

        Parameters
        ----------
        image_path:
            Path to the image file to describe.
        source_id:
            Identifier for the originating document/video.
        timestamp:
            Optional video timestamp in seconds.
        page:
            Optional page/slide number for document images.

        Returns
        -------
        RawSegment-compatible dict with modality='vision', or None if
        vision is not configured.

        Raises
        ------
        NotImplementedError
            When a vision model is configured but the API integration
            has not yet been implemented.
        """
        if not self.is_configured:
            logger.debug("Vision model not configured, skipping frame description")
            return None

        # ----------------------------------------------------------------
        # TODO: Implement vision model API call here.
        #
        # Suggested integration points:
        #
        #   OpenAI GPT-4o (vision):
        #       from openai import AsyncOpenAI
        #       client = AsyncOpenAI(api_key=settings.openai_api_key)
        #       with open(image_path, "rb") as f:
        #           b64 = base64.b64encode(f.read()).decode()
        #       response = await client.chat.completions.create(
        #           model=settings.vision_model,
        #           messages=[{"role": "user", "content": [
        #               {"type": "image_url",
        #                "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
        #               {"type": "text", "text": "Describe this image concisely."}
        #           ]}]
        #       )
        #       description = response.choices[0].message.content
        #
        #   Google Gemini Vision:
        #       import google.generativeai as genai
        #       model = genai.GenerativeModel(settings.vision_model)
        #       img = PIL.Image.open(image_path)
        #       response = model.generate_content([img, "Describe this image."])
        #       description = response.text
        #
        #   Local (Ollama / LLaVA):
        #       import httpx
        #       async with httpx.AsyncClient() as client:
        #           resp = await client.post(
        #               "http://localhost:11434/api/generate",
        #               json={"model": settings.vision_model, "prompt": "...", ...}
        #           )
        # ----------------------------------------------------------------

        raise NotImplementedError(
            f"Vision model '{self.settings.vision_model}' is configured but the "
            "API integration has not been implemented yet.\n\n"
            "To add vision support, edit:\n"
            "  app/extraction/vision.py → VisionExtractor.describe_frame()\n\n"
            "See the inline TODO comment for integration examples (OpenAI, Gemini, Ollama)."
        )

    async def describe_frames(
        self,
        frames: List[dict],
        source_id: str,
    ) -> List[dict]:
        """
        Describe a list of frames (batch helper).

        Parameters
        ----------
        frames:
            List of ``{frame_path: str, timestamp: float}`` dicts.
        source_id:
            Identifier for the originating video.

        Returns
        -------
        List of vision segments (empty list if vision is not configured).
        """
        if not self.is_configured:
            logger.debug(
                "Vision model not configured — skipping description of %d frames",
                len(frames),
            )
            return []

        results = []
        for frame in frames:
            frame_path = Path(frame.get("frame_path", ""))
            timestamp = frame.get("timestamp", None)
            try:
                seg = await self.describe_frame(
                    frame_path,
                    source_id=source_id,
                    timestamp=timestamp,
                )
                if seg is not None:
                    results.append(seg)
            except NotImplementedError:
                raise
            except Exception as exc:
                logger.warning(
                    "Vision description failed for frame %s: %s",
                    frame_path.name,
                    exc,
                )

        return results

    # ------------------------------------------------------------------ #
    # Health check
    # ------------------------------------------------------------------ #

    async def health_check(self) -> dict:
        configured = self.is_configured
        vision_model = getattr(self.settings, "vision_model", None) or ""
        return {
            "available": configured,
            "model": vision_model,
            "note": (
                "Vision model is configured but API integration is not yet implemented. "
                "Edit app/extraction/vision.py to add the API call."
                if configured
                else "Set VISION_MODEL in settings to enable vision descriptions."
            ),
        }
