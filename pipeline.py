"""
Call Center Analytics Pipeline
Whisper (medium) → ollama (qwen2.5-coder:7b) → Snowflake
"""

import os
import json
import time
import re
import requests
import snowflake.connector
from faster_whisper import WhisperModel
from datetime import datetime

# ── Конфигурация ──────────────────────────────────────────────────────────────
AUDIO_ROOT = "/home/dsneo/claude_projects/call_center_dashboard/audio_original_data"
DEPT_MAP = {"ОО": "OO", "ОРККиП": "ORKKiP"}

SNOWFLAKE = dict(
    account="vwxavxk-uq47134",
    user="DYMSIA",
    password="Leha31Jeka04Leha31Jeka04",
    role="ACCOUNTADMIN",
    warehouse="CCA_WH",
    database="CALL_CENTER_DB",
    schema="ANALYTICS",
)

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "qwen2.5-coder:7b"

WHISPER_MODEL = "medium"
WHISPER_LANGUAGE = "ru"

ANALYSIS_PROMPT = """Ты аналитик колл-центра банка. Проанализируй транскрипт звонка и верни ТОЛЬКО валидный JSON, без пояснений и markdown.

Транскрипт:
{transcript}

Верни JSON строго в этом формате:
{{
  "call_type": "тип обращения одной фразой",
  "customer_intent": "намерение клиента одной фразой",
  "urgency": "low | medium | high",
  "resolution_status": "resolved | unresolved | escalated",
  "agent_performance_score": <целое число от 1 до 10>,
  "customer_satisfaction_score": <целое число от 1 до 10>,
  "escalation_flag": <true | false>,
  "key_topics": ["тема1", "тема2"],
  "call_summary": "краткое резюме звонка 2-3 предложения на русском"
}}"""


# ── Шаг 1: Транскрипция ───────────────────────────────────────────────────────
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
            segments, info = model.transcribe(
                fpath, language=WHISPER_LANGUAGE, beam_size=5
            )
            text = " ".join(seg.text.strip() for seg in segments)
            elapsed = time.time() - t0
            print(f"{info.duration:.0f}с аудио → {elapsed:.0f}с транскрипция")
            results.append(
                {
                    "file_name": fname,
                    "department": dept_en,
                    "call_topic": call_topic,
                    "transcript_text": text,
                    "detected_language": info.language,
                    "duration_sec": round(info.duration, 1),
                }
            )
    return results


# ── Шаг 2: Анализ через ollama ────────────────────────────────────────────────
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
    prompt = ANALYSIS_PROMPT.format(transcript=transcript[:3000])
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
        "call_type": "unknown",
        "customer_intent": "unknown",
        "urgency": "medium",
        "resolution_status": "unresolved",
        "agent_performance_score": 5,
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
        results.append({**item, **analysis})
    return results


# ── Шаг 3: Загрузка в Snowflake ───────────────────────────────────────────────
def upload_to_snowflake(records: list[dict]):
    conn = snowflake.connector.connect(**SNOWFLAKE)
    cur = conn.cursor()

    # Очистить таблицы перед повторной загрузкой
    cur.execute("TRUNCATE TABLE AI_TRANSCRIBED_CALLS")
    cur.execute("TRUNCATE TABLE CALL_ANALYSIS")

    transcription_rows = []
    analysis_rows = []
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
            None,  # sentiment_score (Cortex недоступен)
            r.get("urgency", ""),
            r.get("call_type", ""),
            r.get("customer_intent", ""),
            r.get("urgency", ""),
            r.get("resolution_status", ""),
            r.get("agent_performance_score"),
            r.get("customer_satisfaction_score"),
            r.get("escalation_flag", False),
            json.dumps(r.get("key_topics", []), ensure_ascii=False),
        ))

    cur.executemany(
        """INSERT INTO AI_TRANSCRIBED_CALLS
           (file_name, department, call_topic, transcript_text, detected_language, duration_sec)
           VALUES (%s, %s, %s, %s, %s, %s)""",
        transcription_rows,
    )
    print(f"  Загружено транскриптов: {len(transcription_rows)}")

    cur.executemany(
        """INSERT INTO CALL_ANALYSIS
           (file_name, department, call_topic, transcript_text, call_summary,
            sentiment_score, sentiment_label, call_type, customer_intent, urgency,
            resolution_status, agent_performance_score, customer_satisfaction,
            escalation_flag, key_topics)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, PARSE_JSON(%s))""",
        analysis_rows,
    )
    print(f"  Загружено аналитических записей: {len(analysis_rows)}")

    cur.close()
    conn.close()


# ── Главный запуск ────────────────────────────────────────────────────────────
def main():
    start = datetime.now()
    print(f"\n{'='*60}")
    print(f"Call Center Analytics Pipeline")
    print(f"Запуск: {start.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")

    print(f"[1/3] Транскрипция (Whisper {WHISPER_MODEL})...")
    model = WhisperModel(WHISPER_MODEL, device="cpu", compute_type="int8")
    transcripts = transcribe_all(model)
    del model  # освободить RAM перед ollama
    print(f"      Готово: {len(transcripts)} файлов\n")

    print(f"[2/3] Анализ (ollama / {OLLAMA_MODEL})...")
    records = analyze_all(transcripts)
    print(f"      Готово: {len(records)} записей\n")

    # Сохранить результаты локально на случай ошибки загрузки
    cache_path = os.path.join(os.path.dirname(__file__), "results_cache.json")
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
    print(f"      Кэш сохранён: {cache_path}\n")

    print("[3/3] Загрузка в Snowflake...")
    upload_to_snowflake(records)
    print("      Готово\n")

    elapsed = (datetime.now() - start).seconds
    print(f"{'='*60}")
    print(f"Pipeline завершён за {elapsed//60}м {elapsed%60}с")
    print(f"Таблицы: CALL_CENTER_DB.ANALYTICS.AI_TRANSCRIBED_CALLS")
    print(f"         CALL_CENTER_DB.ANALYTICS.CALL_ANALYSIS")
    print(f"{'='*60}\n")

    # Быстрая проверка в Snowflake
    conn = snowflake.connector.connect(**SNOWFLAKE)
    cur = conn.cursor()
    cur.execute("""
        SELECT department, call_topic, urgency, resolution_status,
               agent_performance_score, customer_satisfaction
        FROM CALL_ANALYSIS
        ORDER BY department, call_topic
    """)
    print(f"{'Отдел':<10} {'Тема':<30} {'Срочность':<10} {'Статус':<12} {'Оператор':>9} {'Клиент':>7}")
    print("-" * 80)
    for row in cur.fetchall():
        print(f"{row[0]:<10} {row[1]:<30} {row[2]:<10} {row[3]:<12} {str(row[4]):>9} {str(row[5]):>7}")
    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
