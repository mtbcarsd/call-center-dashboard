"""Общий слой доступа к данным для Dash-страниц.

Все функции работают с PostgreSQL напрямую — через db.get_connection() (тот же
модуль, что и у Streamlit). Нет кэша: при 20 звонках запрос занимает <10 мс,
Dash multi-worker gunicorn не может шарить in-process кэш между воркерами.
"""
import pandas as pd

from db import get_connection
# Реэкспорт: единственный источник этих функций — checklist.py (используется
# и Streamlit-дашбордом, и Dash-страницами).
from checklist import parse_checklist, parse_compliance, checklist_pass_rates  # noqa: F401


def load_calls(
    department: str | None = None,
    operator_match_name: str | None = None,
) -> pd.DataFrame:
    """Загружает звонки из БД.

    department — server-side фильтр для manager, operator_match_name — для
    employee (личный кабинет, видит только свои звонки). Оба фильтра
    применяются на уровне SQL, а не в Python после загрузки — так сотрудник
    не увидит чужие звонки, даже если напрямую дёрнет callback.
    """
    _base_sql = """
        SELECT
            file_name, department, call_topic, call_summary, transcript_text,
            call_type, call_type_override, customer_intent,
            urgency, resolution_status,
            agent_performance_score, customer_satisfaction,
            escalation_flag, operator_name, call_datetime, analyzed_at,
            silence_pct, pause_count, operator_talk_ratio, key_topics,
            checklist_json, compliance_json, qa_score, audio_key
        FROM call_analysis
        {where}
        ORDER BY COALESCE(call_datetime, analyzed_at) DESC NULLS LAST
    """
    conditions = []
    params = {}
    if department:
        conditions.append("department = %(dept)s")
        params["dept"] = department
    if operator_match_name:
        conditions.append("operator_name = %(operator)s")
        params["operator"] = operator_match_name
    where = "WHERE " + " AND ".join(conditions) if conditions else ""

    conn = get_connection()
    try:
        df = pd.read_sql(_base_sql.format(where=where), conn, params=params or None)
    finally:
        conn.close()
    df["call_type_effective"] = df["call_type_override"].where(
        df["call_type_override"].notna() & (df["call_type_override"] != ""),
        other=df["call_type"],
    )
    return df


def set_call_type_override(file_name: str, value: str | None) -> None:
    """Ручное подтверждение/исправление категории звонка (D4.3).
    Эквивалент dashboard.py:set_call_type_override — тот же SQL, отдельная
    копия для Dash (эти write-хелперы не выносил в общий модуль вместе с
    parse_*/checklist_pass_rates в D3.2 — это side-effect'ы конкретной
    страницы, а не read-only данные, используемые везде)."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE call_analysis SET call_type_override = %s WHERE file_name = %s",
                (value, file_name),
            )
        conn.commit()
    finally:
        conn.close()


def set_operator_name(file_name: str, value: str | None) -> None:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE call_analysis SET operator_name = %s WHERE file_name = %s",
                (value, file_name),
            )
        conn.commit()
    finally:
        conn.close()


def set_qa_score(file_name: str, value: float | None) -> None:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE call_analysis SET qa_score = %s WHERE file_name = %s",
                (value, file_name),
            )
        conn.commit()
    finally:
        conn.close()


def load_segments(file_name: str) -> pd.DataFrame:
    """Реплики транскрипта звонка (для деталки в /calls, клик-перемотка в D4.2)."""
    conn = get_connection()
    try:
        df = pd.read_sql(
            "SELECT seg_index, start_sec, end_sec, speaker, text FROM call_segments "
            "WHERE file_name = %(fn)s ORDER BY seg_index",
            conn,
            params={"fn": file_name},
        )
    finally:
        conn.close()
    return df
