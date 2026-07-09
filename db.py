"""Локальная SQLite-база для Call Center Analytics (замена Snowflake)."""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "call_center.db")

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
}


def _migrate(conn: sqlite3.Connection):
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(call_analysis)")
    existing = {row[1] for row in cur.fetchall()}
    for col, coltype in _NEW_CALL_ANALYSIS_COLUMNS.items():
        if col not in existing:
            cur.execute(f"ALTER TABLE call_analysis ADD COLUMN {col} {coltype}")
    conn.commit()


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA)
    _migrate(conn)
    return conn
