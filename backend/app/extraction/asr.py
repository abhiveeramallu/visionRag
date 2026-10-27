import asyncio
import logging
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)


class ConfigurationError(Exception):
    pass


class ASRExtractor:
    """
    Automatic Speech Recognition using faster-whisper (CTranslate2) or WhisperX.

    Extracts word/segment level transcripts with timestamps and confidence scores.
    """

    def __init__(self, settings):
        self.settings = settings
        self._model = None
        self._backend = None  # 'faster_whisper' | 'whisperx' | None

    def _check_availability(self) -> bool:
        if self._backend is None:
            # 1. Prefer faster-whisper (faster, robust, no torchaudio 2.1+ breakage)
            try:
                import faster_whisper
                self._backend = 'faster_whisper'
                return True
            except ImportError:
                pass

            # 2. Fall back to whisperx if available
            try:
                import whisperx
                self._backend = 'whisperx'
                return True
            except (ImportError, Exception):
                pass

            self._backend = 'none'
            return False

        return self._backend in ('faster_whisper', 'whisperx')

    def _load_model(self):
        if not self._check_availability():
            raise ConfigurationError(
                'Neither faster-whisper nor WhisperX is installed. '
                'Install with: pip install faster-whisper'
            )

        if self._model is not None:
            return

        device = getattr(self.settings, 'whisper_device', 'cpu')
        model_size = getattr(self.settings, 'whisper_model', 'base')
        compute_type = getattr(self.settings, 'whisper_compute_type', 'int8')

        # Adjust compute_type on CPU if needed (CPU doesn't support float16)
        if device == 'cpu' and compute_type == 'float16':
            compute_type = 'int8'

        if self._backend == 'faster_whisper':
            from faster_whisper import WhisperModel
            logger.info(
                f'Loading faster-whisper model: {model_size} on {device} ({compute_type})'
            )
            self._model = WhisperModel(
                model_size,
                device=device,
                compute_type=compute_type,
            )
            logger.info('faster-whisper model loaded successfully')
        elif self._backend == 'whisperx':
            import whisperx
            logger.info(
                f'Loading WhisperX model: {model_size} on {device} ({compute_type})'
            )
            self._model = whisperx.load_model(
                model_size,
                device=device,
                compute_type=compute_type,
            )
            logger.info('WhisperX model loaded successfully')

    async def transcribe(
        self,
        audio_path: Path,
        source_id: str
    ) -> List[dict]:  # returns list of RawSegment-compatible dicts
        if not self._check_availability():
            raise ConfigurationError(
                f'ASR engine not available. Cannot transcribe {audio_path}. '
                'Install faster-whisper: pip install faster-whisper'
            )

        audio_path = Path(audio_path)
        if not audio_path.exists():
            raise FileNotFoundError(f'Audio file not found: {audio_path}')

        def _run_transcription():
            self._load_model()
            logger.info(f'Transcribing {audio_path} using {self._backend}')

            if self._backend == 'faster_whisper':
                segments_gen, info = self._model.transcribe(
                    str(audio_path),
                    beam_size=1,
                    vad_filter=True,
                    vad_parameters=dict(min_silence_duration_ms=500),
                )
                segments = []
                for seg in segments_gen:
                    text = seg.text.strip()
                    if not text:
                        continue
                    # Approximate confidence in [0.0, 1.0] from avg_logprob
                    # avg_logprob is typically in [-1.5, 0.0] for usable speech
                    conf = 0.85
                    if hasattr(seg, 'avg_logprob') and seg.avg_logprob is not None:
                        conf = max(0.1, min(1.0, 1.0 + (seg.avg_logprob / 2.0)))

                    segments.append({
                        'text': text,
                        'start': round(float(seg.start), 2),
                        'end': round(float(seg.end), 2),
                        'timestamp_start': round(float(seg.start), 2),
                        'timestamp_end': round(float(seg.end), 2),
                        'confidence': round(conf, 3),
                        'modality': 'asr',
                        'source_id': source_id,
                    })
                return segments

            elif self._backend == 'whisperx':
                import whisperx
                audio = whisperx.load_audio(str(audio_path))
                result = self._model.transcribe(audio, batch_size=16)

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
                    text = seg.get('text', '').strip()
                    if not text:
                        continue
                    conf = seg.get('avg_logprob', -0.5) + 1.0
                    conf = max(0.1, min(1.0, conf))
                    start = round(float(seg.get('start', 0.0)), 2)
                    end = round(float(seg.get('end', 0.0)), 2)
                    segments.append({
                        'text': text,
                        'start': start,
                        'end': end,
                        'timestamp_start': start,
                        'timestamp_end': end,
                        'confidence': round(conf, 3),
                        'modality': 'asr',
                        'source_id': source_id,
                    })
                return segments

            return []

        loop = asyncio.get_event_loop()
        segments = await loop.run_in_executor(None, _run_transcription)
        logger.info(f'Transcription complete for {source_id}: {len(segments)} segments extracted')
        return segments

    async def health_check(self) -> dict:
        available = self._check_availability()
        return {
            'available': available,
            'backend': self._backend,
            'model': getattr(self.settings, 'whisper_model', 'base'),
            'device': getattr(self.settings, 'whisper_device', 'cpu'),
            'error': None if available else 'neither faster-whisper nor whisperx installed'
        }
