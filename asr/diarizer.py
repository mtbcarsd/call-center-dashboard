"""Диаризация оператор/клиент через pyannote.audio (pretrained pipeline).

Whisper даёт сегменты речи без привязки к спикеру. pyannote определяет
временные интервалы речи каждого спикера независимо от Whisper; сегмент
Whisper относим к спикеру с наибольшим пересечением по времени. Кто из
двух спикеров — оператор, определяем эвристикой: приветственная фраза
среди первых реплик (иначе — говорит первым, стандарт для входящих
звонков банка).
"""
import os
import re

import librosa
import torch
from dotenv import load_dotenv
from pyannote.audio import Pipeline

load_dotenv()

GREETING_WORDS = re.compile(
    r"\b(здравствуйте|добрый день|добрый вечер|слушаю вас|банк|чем могу помочь|меня зовут)\b",
    re.IGNORECASE,
)

_pipeline = None


def _get_pipeline() -> Pipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = Pipeline.from_pretrained(
            "pyannote/speaker-diarization-3.1", token=os.environ["HF_TOKEN"]
        )
    return _pipeline


def _overlap(a_start: float, a_end: float, b_start: float, b_end: float) -> float:
    return max(0.0, min(a_end, b_end) - max(a_start, b_start))


def diarize(audio_path: str, segments: list[dict]) -> list[str]:
    """Возвращает список меток 'operator'/'client'/'unknown' — по одной на сегмент Whisper."""
    if not segments:
        return []

    # torchcodec (дефолтный аудио-бэкенд pyannote 4.x) требует ffmpeg 4/5 (libavutil
    # so.56/57); в системе стоит ffmpeg 6 (so.58) — грузим waveform сами через librosa
    # и обходим torchcodec целиком.
    y, sr = librosa.load(audio_path, sr=None, mono=True)
    audio_input = {"waveform": torch.from_numpy(y).unsqueeze(0), "sample_rate": sr}
    output = _get_pipeline()(audio_input, num_speakers=2)
    annotation = output.speaker_diarization
    turns = [
        (turn.start, turn.end, label)
        for turn, _, label in annotation.itertracks(yield_label=True)
    ]

    raw_labels = []
    for seg in segments:
        best_label, best_overlap = None, 0.0
        for t_start, t_end, label in turns:
            ov = _overlap(seg["start"], seg["end"], t_start, t_end)
            if ov > best_overlap:
                best_overlap, best_label = ov, label
        raw_labels.append(best_label)  # None — нет пересечения (тишина/шум)

    speaker_labels = sorted({lbl for lbl in raw_labels if lbl is not None})
    if len(speaker_labels) < 2:
        return ["unknown"] * len(segments)

    operator_label = raw_labels[0] if raw_labels[0] is not None else speaker_labels[0]
    for seg, lbl in zip(segments[:3], raw_labels[:3]):
        if lbl is not None and GREETING_WORDS.search(seg["text"]):
            operator_label = lbl
            break

    return [
        "unknown" if lbl is None else ("operator" if lbl == operator_label else "client")
        for lbl in raw_labels
    ]


def operator_talk_ratio(segments: list[dict], speakers: list[str]) -> float:
    total = sum(seg["end"] - seg["start"] for seg in segments)
    if total <= 0:
        return 0.0
    operator_time = sum(
        seg["end"] - seg["start"]
        for seg, spk in zip(segments, speakers)
        if spk == "operator"
    )
    return round(operator_time / total * 100, 1)
