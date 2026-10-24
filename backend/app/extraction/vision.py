"""
Vision extraction module for VisionRAG-X.

Integrates multimodal vision language models (VLMs) to describe video
frames, presentation slides, diagrams, and figures.
Supports OpenAI (GPT-4o), Google Gemini, and local OpenAI-compatible endpoints.
"""

import base64
import logging
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)


class VisionExtractor:
    """
    Describes images / video frames using a vision language model (VLM).

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
        """
        if not self.is_configured:
            logger.debug("Vision model not configured, skipping frame description")
            return None

        image_path = Path(image_path)
        if not image_path.exists():
            logger.warning("Frame image not found for vision extraction: %s", image_path)
            return None

        provider = getattr(self.settings, "llm_provider", "openai").lower()
        model_name = getattr(self.settings, "vision_model", "")
        prompt_text = (
            "Describe the educational content of this frame or slide concisely. "
            "Focus on diagrams, formulas, charts, visual demonstrations, or key text shown."
        )

        description = ""
        try:
            if provider == "openai":
                from openai import AsyncOpenAI
                client = AsyncOpenAI(
                    api_key=self.settings.openai_api_key,
                    base_url=self.settings.openai_base_url,
                )
                with open(image_path, "rb") as f:
                    b64 = base64.b64encode(f.read()).decode("utf-8")
                ext = image_path.suffix.lower().replace(".", "")
                mime = f"image/{ext}" if ext in ("png", "jpeg", "jpg", "webp", "gif") else "image/jpeg"
                response = await client.chat.completions.create(
                    model=model_name or self.settings.openai_model,
                    messages=[{
                        "role": "user",
                        "content": [
                            {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
                            {"type": "text", "text": prompt_text},
                        ],
                    }],
                    max_tokens=300,
                    temperature=0.2,
                )
                description = response.choices[0].message.content or ""

            elif provider == "gemini":
                import google.generativeai as genai
                from PIL import Image
                genai.configure(api_key=self.settings.gemini_api_key)
                gemini_model = model_name or self.settings.gemini_model
                model = genai.GenerativeModel(gemini_model)
                img = Image.open(image_path)
                response = await model.generate_content_async([img, prompt_text])
                description = response.text or ""

            elif provider == "local":
                from openai import AsyncOpenAI
                base_url = getattr(self.settings, "local_llm_base_url", "http://localhost:11434/v1")
                client = AsyncOpenAI(api_key="not-needed", base_url=base_url)
                with open(image_path, "rb") as f:
                    b64 = base64.b64encode(f.read()).decode("utf-8")
                ext = image_path.suffix.lower().replace(".", "")
                mime = f"image/{ext}" if ext in ("png", "jpeg", "jpg", "webp", "gif") else "image/jpeg"
                response = await client.chat.completions.create(
                    model=model_name or getattr(self.settings, "local_llm_model", "llama3.1:8b"),
                    messages=[{
                        "role": "user",
                        "content": [
                            {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
                            {"type": "text", "text": prompt_text},
                        ],
                    }],
                    max_tokens=300,
                    temperature=0.2,
                )
                description = response.choices[0].message.content or ""

            else:
                logger.warning("Unsupported LLM provider for vision: %s", provider)
                return None

        except Exception as e:
            logger.warning("Vision extraction failed for %s: %s", image_path.name, e)
            return None

        if not description.strip():
            return None

        return {
            "text": description.strip(),
            "confidence": 0.85,
            "modality": "vision",
            "source_id": source_id,
            "timestamp_start": timestamp,
            "timestamp_end": timestamp,
            "page": page,
            "raw_output": {
                "image_path": str(image_path),
                "model": model_name,
                "provider": provider,
            },
        }

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
        provider = getattr(self.settings, "llm_provider", "openai")
        return {
            "available": configured,
            "model": vision_model,
            "provider": provider,
            "note": (
                f"Vision extraction active with model '{vision_model}' via {provider}."
                if configured
                else "Set VISION_MODEL in settings to enable vision descriptions."
            ),
        }
