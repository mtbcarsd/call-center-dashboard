"""Лёгкая DIY-диаризация оператор/клиент без готовых спикер-моделей.

Записи в этом проекте — моно (см. audio_original_data, 8kHz), поэтому
честного разделения каналов нет. Вместо тяжёлых pretrained-моделей (pyannote
требует HF-токен и одобрение лицензии) используем: MFCC-признаки по каждому
сегменту Whisper + кластеризация KMeans на 2 спикера + эвристика, кто из
кластеров — оператор (говорит первым / произносит приветствие).
"""
import re
import numpy as np
import librosa
from sklearn.cluster import KMeans

GREETING_WORDS = re.compile(
    r"\b(здравствуйте|добрый день|добрый вечер|слушаю вас|банк|чем могу помочь|меня зовут)\b",
    re.IGNORECASE,
)


def _segment_features(y: np.ndarray, sr: int, start: float, end: float) -> np.ndarray:
    i0, i1 = int(start * sr), int(end * sr)
    clip = y[i0:i1]
    if len(clip) < sr * 0.05:  # слишком короткий кусок для MFCC
        clip = np.pad(clip, (0, max(0, int(sr * 0.05) - len(clip))))
    mfcc = librosa.feature.mfcc(y=clip, sr=sr, n_mfcc=13)
    return np.concatenate([mfcc.mean(axis=1), mfcc.std(axis=1)])


def diarize(audio_path: str, segments: list[dict]) -> list[str]:
    """Возвращает список меток 'operator'/'client'/'unknown' — по одной на сегмент."""
    if len(segments) < 2:
        return ["unknown"] * len(segments)

    y, sr = librosa.load(audio_path, sr=None, mono=True)

    features = np.array([
        _segment_features(y, sr, seg["start"], seg["end"]) for seg in segments
    ])

    n_clusters = 2 if len(segments) >= 2 else 1
    labels = KMeans(n_clusters=n_clusters, n_init=10, random_state=0).fit_predict(features)

    # Эвристика: оператор — кластер сегмента с приветственной фразой среди первых
    # трёх реплик; если такой не нашли, считаем оператором того, кто говорит первым
    # (стандарт для входящих звонков банка).
    operator_cluster = labels[0]
    for seg, lbl in zip(segments[:3], labels[:3]):
        if GREETING_WORDS.search(seg["text"]):
            operator_cluster = lbl
            break

    return [
        "operator" if lbl == operator_cluster else "client"
        for lbl in labels
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
