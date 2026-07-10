"""
Call Center Analytics Pipeline
Whisper (medium) → пауза/диаризация (DIY) → ollama-чек-лист → PostgreSQL
"""

import os
import json
import time
import re
import requests
from faster_whisper import WhisperModel
from datetime import datetime

from db import get_connection
from checklist import CHECKLIST, weighted_score
from diarization import diarize, operator_talk_ratio

# ── Конфигурация ──────────────────────────────────────────────────────────────
AUDIO_ROOT = "/home/dsneo/claude_projects/call_center_dashboard/audio_original_data"
DEPT_MAP = {"ОО": "OO", "ОРККиП": "ORKKiP"}

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "qwen2.5-coder:7b"

WHISPER_MODEL = "medium"
WHISPER_LANGUAGE = "ru"

PAUSE_THRESHOLD_SEC = 2.0  # gap между репликами дольше этого считаем паузой

_CHECKLIST_QUESTIONS = "\n".join(
    f'  "{item["key"]}": <true/false — {item["question"]}>' for item in CHECKLIST
)

ANALYSIS_PROMPT = """Ты аналитик колл-центра банка. Проанализируй транскрипт звонка и верни ТОЛЬКО валидный JSON, без пояснений и markdown.

Транскрипт:
{transcript}

Верни JSON строго в этом формате (checklist — по каждому пункту true либо false):
{{
  "checklist": {{
{checklist_questions}
  }},
  "call_type": "тип обращения одной фразой",
  "customer_intent": "намерение клиента одной фразой",
  "urgency": "low | medium | high",
  "resolution_status": "resolved | unresolved | escalated",
  "customer_satisfaction_score": <целое число от 1 до 10>,
  "escalation_flag": <true | false>,
  "key_topics": ["тема1", "тема2"],
  "call_summary": "краткое резюме звонка 2-3 предложения на русском"
}}"""


# ── Шаг 1: Транскрипция ───────────────────────────────────────────────────────
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


def transcribe_all(model: WhisperModel) -> list[dict]:
    results = []
    for dept_ru, dept_en in DEPT_MAP.items():
        dept_path = os.path.join(AUDIO_ROOT, dept_ru)
        for fname in sorted(os.listdir(dept_path)):
            if not fname.endswith(".wav"):
                continue
            fpath = os.path.join(dept_path, fname)
            call_topic = fname.replace(".wav", "")
            print(f"  [{dept_en}] {call_topic} ...", end=" ", flush=True)
            t0 = time.time()
            raw_segments, info = model.transcribe(
                fpath, language=WHISPER_LANGUAGE, beam_size=5
            )
            segments = [
                {"start": seg.start, "end": seg.end, "text": seg.text.strip()}
                for seg in raw_segments
            ]
            text = " ".join(seg["text"] for seg in segments)
            elapsed = time.time() - t0
            print(f"{info.duration:.0f}с аудио → {elapsed:.0f}с транскрипция")

            pause_metrics = compute_pause_metrics(segments)

            speakers = diarize(fpath, segments)
            op_ratio = operator_talk_ratio(segments, speakers)

            results.append(
                {
                    "file_name": fname,
                    "department": dept_en,
                    "call_topic": call_topic,
                    "transcript_text": text,
                    "detected_language": info.language,
                    "duration_sec": round(info.duration, 1),
                    "segments": segments,
                    "speakers": speakers,
                    "operator_talk_ratio": op_ratio,
                    **pause_metrics,
                }
            )
    return results


# ── Шаг 2: Анализ через ollama (чек-лист) ─────────────────────────────────────
def extract_json(text: str) -> dict | None:
    # Убрать markdown-блоки если модель всё равно их добавила
    text = re.sub(r"```(?:json)?", "", text).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Попробовать найти JSON внутри текста
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                return None
    return None


def analyze_call(transcript: str) -> dict:
    prompt = ANALYSIS_PROMPT.format(
        transcript=transcript[:3000], checklist_questions=_CHECKLIST_QUESTIONS
    )
    try:
        resp = requests.post(
            OLLAMA_URL,
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.1},
            },
            timeout=120,
        )
        resp.raise_for_status()
        raw = resp.json().get("response", "")
        parsed = extract_json(raw)
        if parsed:
            return parsed
        print(f"\n    [!] Не удалось распарсить JSON: {raw[:200]}")
    except Exception as e:
        print(f"\n    [!] ollama ошибка: {e}")
    return {
        "checklist": {item["key"]: False for item in CHECKLIST},
        "call_type": "unknown",
        "customer_intent": "unknown",
        "urgency": "medium",
        "resolution_status": "unresolved",
        "customer_satisfaction_score": 5,
        "escalation_flag": False,
        "key_topics": [],
        "call_summary": "Анализ недоступен",
    }


def analyze_all(transcripts: list[dict]) -> list[dict]:
    results = []
    for item in transcripts:
        print(f"  [{item['department']}] {item['call_topic']} ...", end=" ", flush=True)
        t0 = time.time()
        analysis = analyze_call(item["transcript_text"])
        elapsed = time.time() - t0
        print(f"{elapsed:.0f}с")
        analysis["agent_performance_score"] = weighted_score(analysis.get("checklist", {}))
        results.append({**item, **analysis})
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
            operator_talk_ratio, checklist_json)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
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
    model = WhisperModel(WHISPER_MODEL, device="cpu", compute_type="int8")
    transcripts = transcribe_all(model)
    del model  # освободить RAM перед ollama
    print(f"      Готово: {len(transcripts)} файлов\n")

    print(f"[2/3] Анализ по чек-листу (ollama / {OLLAMA_MODEL})...")
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
