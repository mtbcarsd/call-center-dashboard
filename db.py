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
    agent_performance_score INTEGER,
    customer_satisfaction INTEGER,
    escalation_flag INTEGER,
    key_topics TEXT,
    analyzed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA)
    return conn
