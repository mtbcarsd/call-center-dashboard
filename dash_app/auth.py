"""Аутентификация и авторизация — helpers для Flask-сессии."""
import bcrypt

from db import get_connection


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def get_user_from_db(username: str) -> dict | None:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT username, password_hash, role, display_name, department, operator_match_name "
            "FROM users WHERE username = %s",
            (username,),
        )
        row = cur.fetchone()
    finally:
        conn.close()
    if not row:
        return None
    return {
        "username": row[0],
        "password_hash": row[1],
        "role": row[2],
        "display_name": row[3],
        "department": row[4],
        "operator_match_name": row[5],
    }


def get_current_user() -> dict | None:
    """Текущий пользователь из Flask-сессии. Только внутри request-контекста."""
    from flask import session
    return session.get("user")


def get_current_department() -> str | None:
    """department из сессии для manager, None — executive видит все данные."""
    user = get_current_user()
    if user and user["role"] == "manager":
        return user["department"]
    return None
