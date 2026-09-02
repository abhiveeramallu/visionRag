import asyncio
import logging
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)


class ConfigurationError(Exception):
    pass


class ASRExtractor:
    """
    Automatic Speech Recognition using WhisperX.

    EXPERIMENTAL: Results depend on audio quality and model size.
    Confidence scores are WhisperX word-level probabilities, not calibrated.
    """

    def __init__(self, settings):
        self.settings = settings
        self._model = None
        self._whisperx_available = None

    def _check_availability(self) -> bool:
        if self._whisperx_available is None:
            try:
                import whisperx
                self._whisperx_available = True
            except ImportError:
                self._whisperx_available = False
        return self._whisperx_available

    def _load_model(self):
        if not self._check_availability():
            raise ConfigurationError(
                'WhisperX is not installed. '
                'Install with: pip install whisperx\n'
                'Note: WhisperX requires torch and may need CUDA for fast inference.'
            )
        if self._model is None:
            import whisperx
            logger.info(f'Loading WhisperX model: {self.settings.whisper_model} on {self.settings.whisper_device}')
            self._model = whisperx.load_model(
                self.settings.whisper_model,
                device=self.settings.whisper_device,
                compute_type=self.settings.whisper_compute_type
            )
            logger.info('WhisperX model loaded successfully')

    async def transcribe(
        self,
        audio_path: Path,
        source_id: str
    ) -> List[dict]:  # returns list of RawSegment-compatible dicts
        if not self._check_availability():
            raise ConfigurationError(
                f'WhisperX not available. Cannot transcribe {audio_path}. '
                'Set WHISPER_MODEL env var and install whisperx.'
            )

        def _run_transcription():
            import whisperx
            self._load_model()
            logger.info(f'Transcribing {audio_path}')
            audio = whisperx.load_audio(str(audio_path))
            result = self._model.transcribe(audio, batch_size=16)

            # Word-level alignment for precise timestamps
            try:
                model_a, metadata = whisperx.load_align_model(
                    language_code=result['language'],
                    device=self.settings.whisper_device
                )
                result = whisperx.align(
                    result['segments'], model_a, metadata,
                    audio, self.settings.whisper_device,
                    return_char_alignments=False
                )
            except Exception as e:
                logger.warning(f'Word alignment failed, using segment-level timestamps: {e}')

            segments = []
            for seg in result.get('segments', []):
                segments.append({
                    'text': seg.get('text', '').strip(),
                    'start': seg.get('start', 0.0),
                    'end': seg.get('end', 0.0),
                    'confidence': seg.get('avg_logprob', -0.5) + 1.0,  # approximate
                    'modality': 'asr',
                    'source_id': source_id
                })
            return segments

        loop = asyncio.get_event_loop()
        segments = await loop.run_in_executor(None, _run_transcription)
        logger.info(f'Transcription complete: {len(segments)} segments')
        return segments

    async def health_check(self) -> dict:
        available = self._check_availability()
        return {
            'available': available,
            'model': self.settings.whisper_model,
            'device': self.settings.whisper_device,
            'error': None if available else 'whisperx not installed'
        }
