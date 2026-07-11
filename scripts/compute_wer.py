"""Прогоняет Transcriber по test_data/*.wav, считает WER (jiwer) против эталонных
транскриптов (*.txt) и пишет test_data/wer_report.md.

Запуск: python scripts/compute_wer.py
"""
import os
import sys
import time
import warnings

import jiwer

warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from asr.transcriber import Transcriber  # noqa: E402

TEST_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "test_data")


def _reference_path(wav_name: str) -> str:
    # kredit_nalichnymi_8khz.wav → kredit_nalichnymi.txt (тот же эталон, другое качество звука)
    topic = wav_name.replace("_8khz", "").replace(".wav", "")
    return os.path.join(TEST_DATA_DIR, f"{topic}.txt")


def main() -> None:
    wav_files = sorted(f for f in os.listdir(TEST_DATA_DIR) if f.endswith(".wav"))
    if not wav_files:
        print(f"Нет .wav файлов в {TEST_DATA_DIR}. Сначала запустите generate_synthetic_calls.py")
        return

    transcriber = Transcriber("medium", "ru")
    rows = []
    for wav_name in wav_files:
        ref_path = _reference_path(wav_name)
        if not os.path.exists(ref_path):
            print(f"  [!] нет эталона для {wav_name}, пропуск")
            continue
        with open(ref_path, encoding="utf-8") as f:
            reference = f.read().strip()

        wav_path = os.path.join(TEST_DATA_DIR, wav_name)
        t0 = time.time()
        result = transcriber.run(wav_path)
        elapsed = time.time() - t0
        hypothesis = result["transcript_text"].strip()

        error = jiwer.wer(reference, hypothesis)
        rows.append((wav_name, result["duration_sec"], elapsed, error))
        print(f"  {wav_name}: WER={error:.1%} ({elapsed:.1f}с транскрипция)")

    report_path = os.path.join(TEST_DATA_DIR, "wer_report.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("# WER-отчёт (faster-whisper medium, синтетические звонки)\n\n")
        f.write("| Файл | Длительность, с | Время транскрипции, с | WER |\n")
        f.write("|---|---|---|---|\n")
        for name, dur, elapsed, error in rows:
            f.write(f"| {name} | {dur:.1f} | {elapsed:.1f} | {error:.1%} |\n")
        avg = sum(r[3] for r in rows) / len(rows) if rows else 0.0
        f.write(f"\n**Средний WER: {avg:.1%}**\n")
    print(f"\nОтчёт сохранён: {report_path}")


if __name__ == "__main__":
    main()
