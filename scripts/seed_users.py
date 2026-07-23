"""Создаёт начальных пользователей в таблице users.

Запуск (из корня репозитория):
    python scripts/seed_users.py

Учётки:
    julia      — role=executive, пароль: 6o5OeXT8lPwuMP (как в Streamlit)
    boss_oo    — role=manager,   department=OO,     пароль: boss_oo
    boss_orkki — role=manager,   department=ORKKiP, пароль: boss_orkki
    sokolova   — role=employee,  department=OO,     пароль: sokolova123
                 (личный кабинет, operator_match_name="Соколова Екатерина Викторовна")

Скрипт идемпотентен (ON CONFLICT DO NOTHING) — безопасно запускать повторно.
Чтобы обновить пароль существующего пользователя, используй ON CONFLICT DO UPDATE.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from db import get_connection
from dash_app.auth import hash_password

_USERS = [
    {
        "username": "julia",
        "password": "6o5OeXT8lPwuMP",
        "role": "executive",
        "display_name": "Julia",
        "department": None,
        "operator_match_name": None,
    },
    {
        "username": "boss_oo",
        "password": "boss_oo",
        "role": "manager",
        "display_name": "Начальник ОО",
        "department": "OO",
        "operator_match_name": None,
    },
    {
        "username": "boss_orkki",
        "password": "boss_orkki",
        "role": "manager",
        "display_name": "Начальник ОРККиП",
        "department": "ORKKiP",
        "operator_match_name": None,
    },
    {
        "username": "sokolova",
        "password": "sokolova123",
        "role": "employee",
        "display_name": "Соколова Екатерина",
        "department": "OO",
        "operator_match_name": "Соколова Екатерина Викторовна",
    },
]


def main():
    conn = get_connection()
    try:
        cur = conn.cursor()
        for u in _USERS:
            cur.execute(
                """
                INSERT INTO users (username, password_hash, role, display_name,
                                   department, operator_match_name)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (username) DO NOTHING
                """,
                (
                    u["username"],
                    hash_password(u["password"]),
                    u["role"],
                    u["display_name"],
                    u["department"],
                    u["operator_match_name"],
                ),
            )
            print(f"✓ {u['username']:12s} role={u['role']:9s} dept={u['department']}")
        conn.commit()
    finally:
        conn.close()
    print("\nГотово. Смени пароли boss_oo / boss_orkki в проде через UPDATE users SET password_hash = ... WHERE username = '...'")


if __name__ == "__main__":
    main()
