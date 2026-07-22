"""Общий слой доступа к данным для Dash-страниц.

Все функции работают с PostgreSQL напрямую — через db.get_connection() (тот же
модуль, что и у Streamlit). Нет кэша: при 20 звонках запрос занимает <10 мс,
Dash multi-worker gunicorn не может шарить in-process кэш между воркерами.
"""
import json

import pandas as pd

from db import get_connection
from checklist import CHECKLIST


def load_calls() -> pd.DataFrame:
    conn = get_connection()
    try:
        df = pd.read_sql(
            """
            SELECT
                file_name, department, call_topic, call_summary,
                call_type, call_type_override, customer_intent,
                urgency, resolution_status,
                agent_performance_score, customer_satisfaction,
                escalation_flag, operator_name, call_datetime, analyzed_at,
                silence_pct, checklist_json, compliance_json, qa_score
            FROM call_analysis
            ORDER BY COALESCE(call_datetime, analyzed_at) DESC NULLS LAST
            """,
            conn,
        )
    finally:
        conn.close()
    df["call_type_effective"] = df["call_type_override"].where(
        df["call_type_override"].notna() & (df["call_type_override"] != ""),
        other=df["call_type"],
    )
    return df


def parse_checklist(raw) -> dict:
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return {}


def parse_compliance(raw):
    if not raw:
        return None
    try:
        parsed = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return None
    return {
        "passed": bool(parsed.get("passed", True)),
        "issues": parsed.get("issues") or [],
    }


def checklist_pass_rates(checklists: list) -> dict:
    """Процент прохождения каждого пункта чек-листа (0–100 или None если нет данных)."""
    rates = {}
    for item in CHECKLIST:
        key = item["key"]
        results = [c[key] for c in checklists if key in c]
        rates[item["label"]] = (
            sum(1 for r in results if r) / len(results) * 100
            if results else None
        )
    return rates
