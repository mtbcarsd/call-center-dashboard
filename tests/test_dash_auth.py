"""Юнит-тесты Phase D2: аутентификация и ролевая фильтрация данных.

Тестируются без Selenium/dash.testing:
  1. hash_password / verify_password  — bcrypt round-trip
  2. get_current_user / get_current_department — читают Flask-сессию
  3. load_calls(department=...)  — SQL-фильтр применяется корректно
"""
from unittest.mock import MagicMock, patch

import flask
import pytest

from dash_app.auth import (
    get_current_department,
    get_current_user,
    hash_password,
    verify_password,
)


# ── hash_password / verify_password ───────────────────────────────────────────

class TestPasswordHashing:
    def test_hash_is_bcrypt(self):
        h = hash_password("secret")
        assert h.startswith("$2b$")  # bcrypt $2b$ prefix

    def test_verify_correct(self):
        h = hash_password("mypassword")
        assert verify_password("mypassword", h) is True

    def test_verify_wrong(self):
        h = hash_password("mypassword")
        assert verify_password("wrongpass", h) is False

    def test_hashes_differ_for_same_input(self):
        # bcrypt генерирует разную соль каждый раз
        h1 = hash_password("abc")
        h2 = hash_password("abc")
        assert h1 != h2

    def test_verify_empty_password(self):
        h = hash_password("")
        assert verify_password("", h) is True
        assert verify_password("x", h) is False


# ── Flask-сессия: get_current_user / get_current_department ──────────────────

def _make_app():
    app = flask.Flask(__name__)
    app.secret_key = "test-secret"
    return app


class TestGetCurrentUser:
    def test_returns_none_when_no_session(self):
        app = _make_app()
        with app.test_request_context("/"):
            assert get_current_user() is None

    def test_returns_user_dict(self):
        app = _make_app()
        user = {"username": "julia", "role": "executive", "display_name": "Julia",
                "department": None, "operator_match_name": None}
        with app.test_request_context("/"):
            flask.session["user"] = user
            assert get_current_user() == user


class TestGetCurrentDepartment:
    def test_executive_returns_none(self):
        app = _make_app()
        with app.test_request_context("/"):
            flask.session["user"] = {"role": "executive", "department": None}
            assert get_current_department() is None

    def test_manager_oo_returns_oo(self):
        app = _make_app()
        with app.test_request_context("/"):
            flask.session["user"] = {"role": "manager", "department": "OO"}
            assert get_current_department() == "OO"

    def test_manager_orkki_returns_orkki(self):
        app = _make_app()
        with app.test_request_context("/"):
            flask.session["user"] = {"role": "manager", "department": "ORKKiP"}
            assert get_current_department() == "ORKKiP"

    def test_no_session_returns_none(self):
        app = _make_app()
        with app.test_request_context("/"):
            assert get_current_department() is None


# ── load_calls: проверка SQL-фильтра ─────────────────────────────────────────

class TestLoadCallsDepartmentFilter:
    """Проверяем, что department-фильтр попадает в SQL-запрос."""

    def _run_load_calls(self, department):
        import pandas as pd
        empty_df = pd.DataFrame(columns=[
            "file_name", "department", "call_topic", "call_summary",
            "call_type", "call_type_override", "customer_intent",
            "urgency", "resolution_status", "agent_performance_score",
            "customer_satisfaction", "escalation_flag", "operator_name",
            "call_datetime", "analyzed_at", "silence_pct",
            "checklist_json", "compliance_json", "qa_score",
        ])
        mock_conn = MagicMock()
        with patch("dash_app.data.get_connection", return_value=mock_conn), \
             patch("dash_app.data.pd.read_sql", return_value=empty_df) as mock_sql:
            from dash_app.data import load_calls
            load_calls(department=department)
            return mock_sql

    def test_no_filter_sql_has_no_where(self):
        mock_sql = self._run_load_calls(None)
        sql_arg = mock_sql.call_args[0][0]
        assert "WHERE" not in sql_arg

    def test_department_filter_adds_where(self):
        mock_sql = self._run_load_calls("OO")
        sql_arg = mock_sql.call_args[0][0]
        assert "WHERE department" in sql_arg

    def test_department_passed_as_param(self):
        mock_sql = self._run_load_calls("OO")
        kwargs = mock_sql.call_args[1]
        assert kwargs.get("params", {}).get("dept") == "OO"

    def test_orkki_filter(self):
        mock_sql = self._run_load_calls("ORKKiP")
        kwargs = mock_sql.call_args[1]
        assert kwargs.get("params", {}).get("dept") == "ORKKiP"
