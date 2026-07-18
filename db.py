"""PostgreSQL-подключение для Call Center Analytics (замена SQLite)."""
import os

import psycopg2
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.environ["DATABASE_URL"]

SCHEMA = """
CREATE TABLE IF NOT EXISTS ai_transcribed_calls (
    file_name TEXT,
    department TEXT,
    call_topic TEXT,
    transcript_text TEXT,
    detected_language TEXT,
    duration_sec REAL
);

CREATE TABLE IF NOT EXISTS call_analysis (
    file_name TEXT,
    department TEXT,
    call_topic TEXT,
    transcript_text TEXT,
    call_summary TEXT,
    sentiment_score REAL,
    sentiment_label TEXT,
    call_type TEXT,
    customer_intent TEXT,
    urgency TEXT,
    resolution_status TEXT,
    agent_performance_score REAL,
    customer_satisfaction INTEGER,
    escalation_flag INTEGER,
    key_topics TEXT,
    analyzed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS call_segments (
    file_name TEXT,
    seg_index INTEGER,
    start_sec REAL,
    end_sec REAL,
    speaker TEXT,
    text TEXT
);

CREATE TABLE IF NOT EXISTS tags (
    id SERIAL PRIMARY KEY,
    name TEXT UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS call_tags (
    file_name TEXT NOT NULL,
    tag_id INTEGER NOT NULL REFERENCES tags(id),
    PRIMARY KEY (file_name, tag_id)
);

CREATE TABLE IF NOT EXISTS collections (
    id SERIAL PRIMARY KEY,
    name TEXT UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS call_collections (
    file_name TEXT NOT NULL,
    collection_id INTEGER NOT NULL REFERENCES collections(id),
    PRIMARY KEY (file_name, collection_id)
);
"""

# Колонки, добавленные после первого релиза (тишина/паузы, диаризация, чек-лист).
# CREATE TABLE IF NOT EXISTS не расширяет уже существующую таблицу, поэтому
# недостающие столбцы добавляем миграцией при подключении.
_NEW_CALL_ANALYSIS_COLUMNS = {
    "silence_sec": "REAL",
    "silence_pct": "REAL",
    "pause_count": "INTEGER",
    "operator_talk_ratio": "REAL",
    "checklist_json": "TEXT",
    "compliance_json": "TEXT",
    "action_items_json": "TEXT",
    # Ключ объекта в S3-совместимом бакете (Railway Bucket) для аудиоплеера
    # в дашборде. NULL, если аудио для этого звонка не заливалось.
    "audio_key": "TEXT",
    # Ручная валидация AI-категории звонка. NULL, пока оператор её не подтвердил
    # и не поправил. Если не пусто — имеет приоритет над call_type везде в UI.
    "call_type_override": "TEXT",
    # Имя оператора, принявшего звонок. Простое текстовое поле (не FK на
    # отдельную таблицу operators) — при 11 звонках отдельная таблица избыточна,
    # для статистики достаточно GROUP BY operator_name.
    "operator_name": "TEXT",
}


def _migrate(conn):
    with conn.cursor() as cur:
        for col, coltype in _NEW_CALL_ANALYSIS_COLUMNS.items():
            cur.execute(f"ALTER TABLE call_analysis ADD COLUMN IF NOT EXISTS {col} {coltype}")
    conn.commit()


def get_connection():
    conn = psycopg2.connect(DATABASE_URL)
    with conn.cursor() as cur:
        cur.execute(SCHEMA)
    conn.commit()
    _migrate(conn)
    return conn
