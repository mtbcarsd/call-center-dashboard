"""
Call Center Analytics Pipeline
Whisper (medium) → пауза/диаризация (DIY) → ollama-чек-лист → PostgreSQL
"""

import asyncio
import os
import json
import time
from datetime import datetime

from db import get_connection
from asr.transcriber import Transcriber, DEFAULT_MODEL as WHISPER_MODEL, DEFAULT_LANGUAGE as WHISPER_LANGUAGE
from asr.diarizer import diarize, operator_talk_ratio
from orchestrator import analyze as orchestrate_analysis
from storage import upload_audio

# ── Конфигурация ──────────────────────────────────────────────────────────────
AUDIO_ROOT = "/home/dsneo/claude_projects/call_center_dashboard/audio_original_data"
# Известные отделы транслитерируются для читаемого ярлыка в консоли/БД; любая
# другая подпапка audio_original_data/ подхватывается автоматически под своим
# именем — так что новый отдел не нужно прописывать вручную.
DEPT_LABELS = {"ОО": "OO", "ОРККиП": "ORKKiP"}


def _discover_departments() -> dict[str, str]:
    depts = {
        name: DEPT_LABELS.get(name, name)
        for name in sorted(os.listdir(AUDIO_ROOT))
        if os.path.isdir(os.path.join(AUDIO_ROOT, name))
    }
    return depts


# ── Шаг 1: Транскрипция ───────────────────────────────────────────────────────
def transcribe_all(transcriber: Transcriber) -> list[dict]:
    results = []
    for dept_ru, dept_en in _discover_departments().items():
        dept_path = os.path.join(AUDIO_ROOT, dept_ru)
        for fname in sorted(os.listdir(dept_path)):
            if not fname.endswith(".wav"):
                continue
            fpath = os.path.join(dept_path, fname)
            call_topic = fname.replace(".wav", "")
            print(f"  [{dept_en}] {call_topic} ...", end=" ", flush=True)
            t0 = time.time()
            result = transcriber.run(fpath)
            elapsed = time.time() - t0
            print(f"{result['duration_sec']:.0f}с аудио → {elapsed:.0f}с транскрипция")

            speakers = diarize(fpath, result["segments"])
            op_ratio = operator_talk_ratio(result["segments"], speakers)
            audio_key = upload_audio(fpath, f"{dept_ru}/{fname}")

            results.append(
                {
                    "file_name": fname,
                    "department": dept_en,
                    "call_topic": call_topic,
                    "speakers": speakers,
                    "operator_talk_ratio": op_ratio,
                    "audio_key": audio_key,
                    **result,
                }
            )
    return results


# ── Шаг 2: Анализ через 4 агента (classifier/quality/compliance/summarizer) ───
def analyze_all(transcripts: list[dict]) -> list[dict]:
    results = []
    for item in transcripts:
        print(f"  [{item['department']}] {item['call_topic']} ...", end=" ", flush=True)
        t0 = time.time()
        analysis = asyncio.run(orchestrate_analysis(item["transcript_text"]))
        elapsed = time.time() - t0
        print(f"{elapsed:.0f}с")
        flat = {
            "call_type": analysis["classification"]["topic"],
            "urgency": analysis["classification"]["priority"],
            "customer_intent": analysis["customer_intent"],
            "resolution_status": analysis["resolution_status"],
            "customer_satisfaction_score": analysis["customer_satisfaction_score"],
            "escalation_flag": analysis["escalation_flag"],
            "key_topics": analysis["key_topics"],
            "call_summary": analysis["summary"],
            "checklist": analysis["quality_score"]["checklist"],
            "agent_performance_score": analysis["quality_score"]["total"] / 10,
            "compliance": analysis["compliance"],
            "action_items": analysis["action_items"],
        }
        results.append({**item, **flat})
    return results


# ── Шаг 3: Загрузка в PostgreSQL ────────────────────────────────────────────
def upload_to_db(records: list[dict]):
    conn = get_connection()
    cur = conn.cursor()

    # Очистить таблицы перед повторной загрузкой
    cur.execute("DELETE FROM ai_transcribed_calls")
    cur.execute("DELETE FROM call_analysis")
    cur.execute("DELETE FROM call_segments")

    transcription_rows = []
    analysis_rows = []
    segment_rows = []
    for r in records:
        transcription_rows.append((
            r["file_name"],
            r["department"],
            r["call_topic"],
            r["transcript_text"],
            r["detected_language"],
            r["duration_sec"],
        ))
        analysis_rows.append((
            r["file_name"],
            r["department"],
            r["call_topic"],
            r["transcript_text"],
            r.get("call_summary", ""),
            None,  # sentiment_score (не считается локальной моделью)
            r.get("urgency", ""),
            r.get("call_type", ""),
            r.get("customer_intent", ""),
            r.get("urgency", ""),
            r.get("resolution_status", ""),
            r.get("agent_performance_score"),
            r.get("customer_satisfaction_score"),
            int(bool(r.get("escalation_flag", False))),
            json.dumps(r.get("key_topics", []), ensure_ascii=False),
            r.get("silence_sec"),
            r.get("silence_pct"),
            r.get("pause_count"),
            r.get("operator_talk_ratio"),
            json.dumps(r.get("checklist", {}), ensure_ascii=False),
            json.dumps(r.get("compliance", {}), ensure_ascii=False),
            json.dumps(r.get("action_items", []), ensure_ascii=False),
            r.get("audio_key"),
        ))
        for i, (seg, spk) in enumerate(zip(r.get("segments", []), r.get("speakers", []))):
            segment_rows.append((r["file_name"], i, seg["start"], seg["end"], spk, seg["text"]))

    cur.executemany(
        """INSERT INTO ai_transcribed_calls
           (file_name, department, call_topic, transcript_text, detected_language, duration_sec)
           VALUES (%s, %s, %s, %s, %s, %s)""",
        transcription_rows,
    )
    print(f"  Загружено транскриптов: {len(transcription_rows)}")

    cur.executemany(
        """INSERT INTO call_analysis
           (file_name, department, call_topic, transcript_text, call_summary,
            sentiment_score, sentiment_label, call_type, customer_intent, urgency,
            resolution_status, agent_performance_score, customer_satisfaction,
            escalation_flag, key_topics, silence_sec, silence_pct, pause_count,
            operator_talk_ratio, checklist_json, compliance_json, action_items_json,
            audio_key)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
        analysis_rows,
    )
    print(f"  Загружено аналитических записей: {len(analysis_rows)}")

    cur.executemany(
        """INSERT INTO call_segments (file_name, seg_index, start_sec, end_sec, speaker, text)
           VALUES (%s, %s, %s, %s, %s, %s)""",
        segment_rows,
    )
    print(f"  Загружено сегментов (диаризация): {len(segment_rows)}")

    conn.commit()
    conn.close()


# ── Главный запуск ────────────────────────────────────────────────────────────
def main():
    start = datetime.now()
    print(f"\n{'='*60}")
    print(f"Call Center Analytics Pipeline")
    print(f"Запуск: {start.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")

    print(f"[1/3] Транскрипция + паузы + диаризация (Whisper {WHISPER_MODEL})...")
    transcriber = Transcriber(WHISPER_MODEL, WHISPER_LANGUAGE)
    transcripts = transcribe_all(transcriber)
    del transcriber  # освободить RAM перед ollama
    print(f"      Готово: {len(transcripts)} файлов\n")

    print("[2/3] Анализ через 4 агента (classifier/quality/compliance/summarizer)...")
    records = analyze_all(transcripts)
    print(f"      Готово: {len(records)} записей\n")

    # Сохранить результаты локально на случай ошибки загрузки
    cache_path = os.path.join(os.path.dirname(__file__), "results_cache.json")
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
    print(f"      Кэш сохранён: {cache_path}\n")

    print("[3/3] Загрузка в PostgreSQL...")
    upload_to_db(records)
    print("      Готово\n")

    elapsed = (datetime.now() - start).seconds
    print(f"{'='*60}")
    print(f"Pipeline завершён за {elapsed//60}м {elapsed%60}с")
    print(f"База: PostgreSQL (таблицы ai_transcribed_calls, call_analysis, call_segments)")
    print(f"{'='*60}\n")

    # Быстрая проверка
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT department, call_topic, urgency, resolution_status,
               agent_performance_score, silence_pct, operator_talk_ratio
        FROM call_analysis
        ORDER BY department, call_topic
    """)
    print(f"{'Отдел':<10} {'Тема':<24} {'Срочность':<10} {'Статус':<12} {'Оценка':>7} {'Тишина%':>8} {'Оператор%':>10}")
    print("-" * 90)
    for row in cur.fetchall():
        print(f"{row[0]:<10} {row[1]:<24} {row[2]:<10} {row[3]:<12} {str(row[4]):>7} {str(row[5]):>8} {str(row[6]):>10}")
    conn.close()


if __name__ == "__main__":
    main()
