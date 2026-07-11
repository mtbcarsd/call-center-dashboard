"""faster-whisper обёртка: один аудиофайл → сегменты, текст, метрики пауз."""
from faster_whisper import WhisperModel

DEFAULT_MODEL = "medium"
DEFAULT_LANGUAGE = "ru"
PAUSE_THRESHOLD_SEC = 2.0  # gap между репликами дольше этого считаем паузой


def compute_pause_metrics(segments: list[dict], threshold: float = PAUSE_THRESHOLD_SEC) -> dict:
    if len(segments) < 2:
        return {"silence_sec": 0.0, "pause_count": 0, "silence_pct": 0.0}
    total_pause = 0.0
    pause_count = 0
    for prev, cur in zip(segments, segments[1:]):
        gap = cur["start"] - prev["end"]
        if gap > threshold:
            total_pause += gap
            pause_count += 1
    duration = segments[-1]["end"] - segments[0]["start"]
    silence_pct = round(total_pause / duration * 100, 1) if duration > 0 else 0.0
    return {
        "silence_sec": round(total_pause, 1),
        "pause_count": pause_count,
        "silence_pct": silence_pct,
    }


class Transcriber:
    """Обёртка над faster-whisper: аудиофайл → сегменты + текст + метрики пауз."""

    def __init__(self, model_size: str = DEFAULT_MODEL, language: str = DEFAULT_LANGUAGE):
        self.language = language
        self._model = WhisperModel(model_size, device="cpu", compute_type="int8")

    def run(self, audio_path: str) -> dict:
        raw_segments, info = self._model.transcribe(
            audio_path, language=self.language, beam_size=5
        )
        segments = [
            {"start": seg.start, "end": seg.end, "text": seg.text.strip()}
            for seg in raw_segments
        ]
        text = " ".join(seg["text"] for seg in segments)
        return {
            "segments": segments,
            "transcript_text": text,
            "detected_language": info.language,
            "duration_sec": round(info.duration, 1),
            **compute_pause_metrics(segments),
        }
