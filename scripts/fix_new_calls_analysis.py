"""Пересчитывает LLM-анализ (4 агента) для звонков из new_calls_cache.json и
обновляет уже вставленные строки в обеих базах (локальной и Railway).

Нужен, потому что при первом запуске add_new_calls.py в системе не хватило
RAM для Ollama (whisper+pyannote всё ещё были в памяти) — все 10 звонков
получили пустой fallback-анализ. Транскрипция и диаризация уже посчитаны
верно (в кэше), поэтому этот скрипт НЕ трогает asr/ (torch+whisper+pyannote
не импортируются) — только agents/orchestrator, что оставляет намного
больше свободной RAM для Ollama.

Запуск: python scripts/fix_new_calls_analysis.py
"""
import asyncio
import json
import os
import sys
import time

import psycopg2

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from orchestrator import analyze as orchestrate_analysis
from db import DATABASE_URL as LOCAL_DATABASE_URL

# Публичный (proxy) DATABASE_URL сервиса Postgres на Railway — не хардкодим:
# см. `railway variables --service Postgres --kv` → DATABASE_PUBLIC_URL.
RAILWAY_DATABASE_URL = os.environ.get("RAILWAY_DATABASE_PUBLIC_URL")

CACHE_PATH = os.path.join(os.path.dirname(__file__), "..", "new_calls_cache.json")

MAX_RETRIES = 3
RETRY_DELAY_SEC = 15


def analyze_with_retry(transcript_text: str, label: str) -> dict:
    for attempt in range(1, MAX_RETRIES + 1):
        analysis = asyncio.run(orchestrate_analysis(transcript_text))
        checklist = analysis["quality_score"]["checklist"]
        # Если чек-лист весь False и summary "Анализ недоступен" — типичный
        # признак того, что все 4 агента упали на fallback (обычно нехватка RAM).
        if any(checklist.values()) or analysis["summary"] != "":
            return analysis
        print(f"    [{label}] попытка {attempt}/{MAX_RETRIES}: похоже на fallback, "
              f"жду {RETRY_DELAY_SEC}с и пробую снова...")
        time.sleep(RETRY_DELAY_SEC)
    print(f"    [{label}] ВНИМАНИЕ: анализ так и не удался за {MAX_RETRIES} попыток, "
          f"оставляю последний результат (возможен fallback)")
    return analysis


def update_record(database_url: str, label: str, file_name: str, analysis: dict) -> None:
    conn = psycopg2.connect(database_url)
    with conn.cursor() as cur:
        cur.execute(
            """UPDATE call_analysis SET
                   call_type = %s, urgency = %s, customer_intent = %s,
                   resolution_status = %s, customer_satisfaction = %s,
                   escalation_flag = %s, key_topics = %s, call_summary = %s,
                   checklist_json = %s, agent_performance_score = %s,
                   compliance_json = %s, action_items_json = %s
               WHERE file_name = %s""",
            (
                analysis["classification"]["topic"],
                analysis["classification"]["priority"],
                analysis["customer_intent"],
                analysis["resolution_status"],
                analysis["customer_satisfaction_score"],
                int(bool(analysis["escalation_flag"])),
                json.dumps(analysis["key_topics"], ensure_ascii=False),
                analysis["summary"],
                json.dumps(analysis["quality_score"]["checklist"], ensure_ascii=False),
                analysis["quality_score"]["total"] / 10,
                json.dumps(analysis["compliance"], ensure_ascii=False),
                json.dumps(analysis["action_items"], ensure_ascii=False),
                file_name,
            ),
        )
    conn.commit()
    conn.close()
    print(f"    [{label}] обновлено: {file_name}")


def main() -> None:
    with open(CACHE_PATH, encoding="utf-8") as f:
        records = json.load(f)

    print(f"Пересчитываю анализ для {len(records)} звонков...\n")
    for r in records:
        print(f"  {r['file_name']}...")
        analysis = analyze_with_retry(r["transcript_text"], r["file_name"])
        update_record(LOCAL_DATABASE_URL, "локальная БД", r["file_name"], analysis)
        if RAILWAY_DATABASE_URL:
            update_record(RAILWAY_DATABASE_URL, "Railway БД", r["file_name"], analysis)
        else:
            print(f"    [Railway БД] RAILWAY_DATABASE_PUBLIC_URL не задан — пропуск")

    print("\nГотово.")


if __name__ == "__main__":
    main()
