import uuid
import logging
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)

DEFAULT_WINDOW_SECONDS = 15.0


class TimestampAligner:
    """
    Groups multimodal segments into temporal or spatial windows.
    
    For video: groups by time window (default 15 seconds)
    For documents: groups by page or slide number
    """
    
    def __init__(self, window_size_seconds: float = DEFAULT_WINDOW_SECONDS):
        self.window_size = window_size_seconds
    
    def _get_window_id(self, source_id: str, window_start: float) -> str:
        return f'{source_id}_w{int(window_start)}'
    
    def _get_page_window_id(self, source_id: str, page: int) -> str:
        return f'{source_id}_p{page}'
    
    def align_video_segments(
        self,
        source_id: str,
        asr_segments: List[dict],
        ocr_segments: List[dict],
        vision_segments: List[dict],
        formula_segments: List[dict],
        code_segments: List[dict],
        total_duration: float
    ) -> List[dict]:  # list of AlignedWindow-compatible dicts
        windows = {}
        num_windows = max(1, int(total_duration / self.window_size) + 1)
        
        for i in range(num_windows):
            w_start = i * self.window_size
            w_end = min((i + 1) * self.window_size, total_duration)
            w_id = self._get_window_id(source_id, w_start)
            windows[w_id] = {
                'window_id': w_id,
                'source_id': source_id,
                'window_start': w_start,
                'window_end': w_end,
                'page': None,
                'slide': None,
                'asr_segments': [],
                'ocr_segments': [],
                'vision_segments': [],
                'formula_segments': [],
                'code_segments': []
            }
        
        def assign(segments, key):
            for seg in segments:
                ts = seg.get('timestamp_start') or seg.get('start') or 0.0
                w_idx = int(ts / self.window_size)
                w_start = w_idx * self.window_size
                w_id = self._get_window_id(source_id, w_start)
                if w_id in windows:
                    windows[w_id][key].append(seg)
        
        assign(asr_segments, 'asr_segments')
        assign(ocr_segments, 'ocr_segments')
        assign(vision_segments, 'vision_segments')
        assign(formula_segments, 'formula_segments')
        assign(code_segments, 'code_segments')
        
        # Filter empty windows
        non_empty = [w for w in windows.values()
                     if any(w[k] for k in ['asr_segments', 'ocr_segments', 'vision_segments',
                                           'formula_segments', 'code_segments'])]
        logger.info(f'Created {len(non_empty)} non-empty windows from {total_duration:.1f}s video')
        return non_empty
    
    def align_document_segments(
        self,
        source_id: str,
        text_segments: List[dict],
        ocr_segments: List[dict],
        total_pages: int,
        doc_type: str = 'pdf'
    ) -> List[dict]:
        windows = {}
        
        for page_num in range(1, total_pages + 1):
            w_id = self._get_page_window_id(source_id, page_num)
            windows[w_id] = {
                'window_id': w_id,
                'source_id': source_id,
                'window_start': None,
                'window_end': None,
                'page': page_num,
                'slide': page_num if doc_type == 'ppt' else None,
                'asr_segments': [],
                'ocr_segments': [],
                'vision_segments': [],
                'formula_segments': [],
                'code_segments': text_segments  # text segments across all pages initially
            }
        
        # Assign text segments to pages
        for seg in text_segments:
            page = seg.get('page')
            if page:
                w_id = self._get_page_window_id(source_id, page)
                if w_id in windows:
                    windows[w_id]['code_segments'] = []
                    windows[w_id]['asr_segments'].append(seg)  # treat as primary text
        
        for seg in ocr_segments:
            page = seg.get('page')
            if page:
                w_id = self._get_page_window_id(source_id, page)
                if w_id in windows:
                    windows[w_id]['ocr_segments'].append(seg)
        
        non_empty = [w for w in windows.values()
                     if any(w[k] for k in ['asr_segments', 'ocr_segments'])]
        logger.info(f'Created {len(non_empty)} page windows for {doc_type}')
        return non_empty
    
    def get_window_for_timestamp(self, timestamp: float) -> Tuple[float, float]:
        w_idx = int(timestamp / self.window_size)
        w_start = w_idx * self.window_size
        w_end = w_start + self.window_size
        return (w_start, w_end)
