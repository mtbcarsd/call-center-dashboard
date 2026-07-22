"""Генерирует облегчённые синтетические звонки напрямую в call_analysis —
без синтеза аудио и без прогона через LLM-пайплайн (Whisper/pyannote/Ollama).

Зачем: чтобы дневной/часовой разрез (аналог вкладок WYNIKI DZIENNE/GODZINOWE
из польского Power BI-примера) на наших метриках (compliance %, оценка
оператора, resolution) выглядел содержательно — для этого нужен только
реалистичный разброс call_datetime по дням/часам, а не реальные аудио/тексты.

Формулы согласованы с реальным пайплайном (agents/quality.py, checklist.py):
    agent_performance_score == checklist.weighted_score(checklist_json)
Остальные поля (customer_satisfaction, escalation_flag, compliance_json) в
реальном пайплайне — независимые LLM-суждения без жёсткой формулы, поэтому
здесь они смоделированы с правдоподобной корреляцией к «скиллу» оператора.

Пишет ТОЛЬКО в локальную Postgres (DATABASE_URL из .env) — на Railway
сознательно не льём (см. обсуждение с пользователем 2026-07-22).

Запуск:
    python -m scripts.generate_synthetic_metrics_calls
"""
import json
import os
import random
from datetime import datetime, timedelta

import psycopg2
from dotenv import load_dotenv

from db import get_connection, DATABASE_URL as LOCAL_DATABASE_URL
from checklist import CHECKLIST, weighted_score

load_dotenv()
# Публичный (proxy) DATABASE_URL сервиса Postgres на Railway — не хардкодим,
# см. .env / scripts/add_new_calls.py (тот же паттерн).
RAILWAY_DATABASE_URL = os.environ.get("RAILWAY_DATABASE_PUBLIC_URL")

random.seed(42)

N_CALLS = 320
END_DATE = datetime(2026, 7, 21, 23, 59, 59)  # вчера относительно текущей даты сессии
START_DATE = END_DATE - timedelta(days=90)
FILE_PREFIX = "synth2_"  # отличается от именования первого синтетического батча

# Операторы — те же 10 уже существующих ФИО (сессия 9), с приписанным условным
# «скиллом» 0..1, который тянет за собой чек-лист/жалобы/compliance.
OPERATORS = {
    "OO": [
        ("Соколова Екатерина Викторовна", 0.85),
        ("Кузнецов Дмитрий Олегович", 0.55),
        ("Иванова Мария Сергеевна", 0.75),
        ("Петров Алексей Николаевич", 0.65),
        ("Волкова Наталья Игоревна", 0.70),
    ],
    "ORKKiP": [
        ("Сидоров Виктор Андреевич", 0.80),
        ("Лебедева Анна Дмитриевна", 0.50),
        ("Козлов Сергей Викторович", 0.60),
        ("Морозова Ольга Павловна", 0.90),
        ("Новикова Татьяна Романовна", 0.68),
    ],
}

# Насколько трудно дался пункт чек-листа при данном «скилле» оператора —
# needs_discovery специально занижен, чтобы сохранить уже подмеченный в
# реальных данных паттерн («Выявление потребности» — слабое место у всех).
_ITEM_DIFFICULTY = {
    "greeting": 1.05,
    "needs_discovery": 0.55,
    "solution_presented": 0.85,
    "objection_handling": 0.75,
    "politeness": 1.05,
    "closing": 1.0,
}

_COMPLIANCE_ISSUES_POOL = [
    "не упомянуты обязательные предупреждения (например, что разговор может "
    "записываться, условия и риски финансового продукта)",
    "некорректные или незаконные обещания оператора",
]

# Часовые веса (08:00–19:00) — пик к 10-11 и 14-15, спад в обед и к вечеру,
# по форме похоже на «WYNIKI GODZINOWE» из референса.
_HOUR_WEIGHTS = {
    8: 0.5, 9: 0.85, 10: 1.0, 11: 1.0, 12: 0.6, 13: 0.55,
    14: 0.9, 15: 1.0, 16: 0.9, 17: 0.7, 18: 0.5, 19: 0.3,
}
# Веса дней недели: пн-пт полная нагрузка, выходные — сильно меньше (0=пн).
_WEEKDAY_WEIGHTS = [1.0, 1.0, 1.0, 1.0, 1.0, 0.3, 0.15]


def _load_topic_pool(conn) -> dict[str, list[tuple]]:
    """Пул (call_topic, call_type, customer_intent) по отделу — из уже существующих
    20 звонков, чтобы темы синтетических звонков были в стиле реальных данных."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT DISTINCT department, call_topic, call_type, customer_intent "
            "FROM call_analysis WHERE NOT file_name LIKE %s",
            (f"{FILE_PREFIX}%",),
        )
        rows = cur.fetchall()
    pool: dict[str, list[tuple]] = {"OO": [], "ORKKiP": []}
    for dept, topic, ctype, intent in rows:
        if dept in pool:
            pool[dept].append((topic, ctype, intent))
    return pool


def _weighted_choice(items, weights):
    return random.choices(items, weights=weights, k=1)[0]


def _random_datetime() -> datetime:
    day_offset = random.randrange((END_DATE.date() - START_DATE.date()).days + 1)
    day = START_DATE.date() + timedelta(days=day_offset)
    day_weight = _WEEKDAY_WEIGHTS[day.weekday()]
    # Отбрасываем дни с низким весом вероятностно (weekend reduced traffic).
    if random.random() > day_weight:
        return _random_datetime()
    hour = _weighted_choice(list(_HOUR_WEIGHTS.keys()), list(_HOUR_WEIGHTS.values()))
    minute = random.randrange(60)
    second = random.randrange(60)
    return datetime(day.year, day.month, day.day, hour, minute, second)


def _gen_checklist(skill: float) -> dict:
    result = {}
    for item in CHECKLIST:
        key = item["key"]
        prob = min(0.97, max(0.03, skill * _ITEM_DIFFICULTY[key]))
        result[key] = random.random() < prob
    return result


def _gen_compliance(skill: float) -> dict:
    pass_prob = min(0.95, 0.5 + skill * 0.45)
    if random.random() < pass_prob:
        return {"passed": True, "issues": []}
    n_issues = 1 if random.random() < 0.7 else 2
    issues = random.sample(_COMPLIANCE_ISSUES_POOL, k=min(n_issues, len(_COMPLIANCE_ISSUES_POOL)))
    return {"passed": False, "issues": issues}


def _clip(value, lo, hi):
    return max(lo, min(hi, value))


def generate_row(idx: int, topic_pool: dict) -> tuple:
    department = random.choice(["OO", "ORKKiP"])
    operator_name, skill = random.choice(OPERATORS[department])
    call_topic, call_type, customer_intent = random.choice(topic_pool[department])

    checklist = _gen_checklist(skill)
    agent_score = weighted_score(checklist)  # 0-10, как в agents/quality.py

    customer_satisfaction = round(_clip(
        agent_score + 2.0 + random.gauss(0, 1.0), 1, 10
    ))
    resolved_prob = _clip(0.45 + agent_score / 18, 0.35, 0.95)
    resolution_status = "resolved" if random.random() < resolved_prob else "unresolved"

    escalation_prob = 0.30 if resolution_status == "unresolved" else 0.04
    escalation_flag = int(random.random() < escalation_prob)

    urgency = _weighted_choice(["medium", "high", "low"], [0.70, 0.22, 0.08])
    silence_pct = round(_clip(random.gauss(15 - skill * 12, 6), 0, 35), 1)
    compliance = _gen_compliance(skill)

    call_dt = _random_datetime()
    file_name = f"{FILE_PREFIX}{department}_{call_dt:%Y%m%d_%H%M%S}_{idx:04d}.wav"
    call_summary = f"Синтетический звонок ({department}): {call_topic}."

    return (
        file_name, department, call_topic, call_summary,
        call_type, customer_intent, urgency, resolution_status,
        agent_score, customer_satisfaction, escalation_flag,
        operator_name, call_dt,
        silence_pct, json.dumps(checklist, ensure_ascii=False),
        json.dumps(compliance, ensure_ascii=False),
    )


_INSERT_SQL = """
    INSERT INTO call_analysis (
        file_name, department, call_topic, call_summary,
        call_type, customer_intent, urgency, resolution_status,
        agent_performance_score, customer_satisfaction, escalation_flag,
        operator_name, call_datetime,
        silence_pct, checklist_json, compliance_json
    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
"""


def _already_seeded(conn) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT count(*) FROM call_analysis WHERE file_name LIKE %s",
            (f"{FILE_PREFIX}%",),
        )
        return cur.fetchone()[0] > 0


def insert_rows(rows, database_url: str, label: str):
    conn = psycopg2.connect(database_url)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")  # проверка соединения перед проверкой дублей
        if _already_seeded(conn):
            print(f"[{label}] Уже есть записи '{FILE_PREFIX}*' — пропускаю "
                  f"(во избежание дублей повторного запуска).")
            return
        with conn.cursor() as cur:
            cur.executemany(_INSERT_SQL, rows)
        conn.commit()
        print(f"[{label}] Вставлено {len(rows)} синтетических звонков "
              f"(период {START_DATE.date()} — {END_DATE.date()}).")
    finally:
        conn.close()


def main():
    conn = get_connection()
    try:
        topic_pool = _load_topic_pool(conn)
    finally:
        conn.close()

    rows = [generate_row(i, topic_pool) for i in range(N_CALLS)]

    insert_rows(rows, LOCAL_DATABASE_URL, "локальная БД")
    if RAILWAY_DATABASE_URL:
        insert_rows(rows, RAILWAY_DATABASE_URL, "Railway БД")
    else:
        print("  RAILWAY_DATABASE_PUBLIC_URL не задан — Railway пропущен.")


if __name__ == "__main__":
    main()
