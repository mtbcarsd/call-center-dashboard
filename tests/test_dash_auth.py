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
    get_current_operator_match_name,
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


class TestGetCurrentOperatorMatchName:
    def test_employee_returns_operator_match_name(self):
        app = _make_app()
        with app.test_request_context("/"):
            flask.session["user"] = {
                "role": "employee", "operator_match_name": "Соколова Екатерина Викторовна",
            }
            assert get_current_operator_match_name() == "Соколова Екатерина Викторовна"

    def test_executive_returns_none(self):
        app = _make_app()
        with app.test_request_context("/"):
            flask.session["user"] = {"role": "executive", "operator_match_name": None}
            assert get_current_operator_match_name() is None

    def test_manager_returns_none(self):
        app = _make_app()
        with app.test_request_context("/"):
            flask.session["user"] = {"role": "manager", "operator_match_name": None}
            assert get_current_operator_match_name() is None

    def test_no_session_returns_none(self):
        app = _make_app()
        with app.test_request_context("/"):
            assert get_current_operator_match_name() is None


# ── load_calls: проверка SQL-фильтра ─────────────────────────────────────────

class TestLoadCallsDepartmentFilter:
    """Проверяем, что department/operator-фильтры попадают в SQL-запрос."""

    def _run_load_calls(self, department=None, operator_match_name=None):
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
            load_calls(department=department, operator_match_name=operator_match_name)
            return mock_sql

    def test_no_filter_sql_has_no_where(self):
        mock_sql = self._run_load_calls()
        sql_arg = mock_sql.call_args[0][0]
        assert "WHERE" not in sql_arg

    def test_department_filter_adds_where(self):
        mock_sql = self._run_load_calls(department="OO")
        sql_arg = mock_sql.call_args[0][0]
        assert "WHERE department" in sql_arg

    def test_department_passed_as_param(self):
        mock_sql = self._run_load_calls(department="OO")
        kwargs = mock_sql.call_args[1]
        assert kwargs.get("params", {}).get("dept") == "OO"

    def test_orkki_filter(self):
        mock_sql = self._run_load_calls(department="ORKKiP")
        kwargs = mock_sql.call_args[1]
        assert kwargs.get("params", {}).get("dept") == "ORKKiP"

    def test_operator_filter_adds_where(self):
        mock_sql = self._run_load_calls(operator_match_name="Соколова Екатерина Викторовна")
        sql_arg = mock_sql.call_args[0][0]
        assert "WHERE operator_name" in sql_arg

    def test_operator_passed_as_param(self):
        mock_sql = self._run_load_calls(operator_match_name="Соколова Екатерина Викторовна")
        kwargs = mock_sql.call_args[1]
        assert kwargs.get("params", {}).get("operator") == "Соколова Екатерина Викторовна"

    def test_department_and_operator_combine_with_and(self):
        mock_sql = self._run_load_calls(department="OO", operator_match_name="Иванова")
        sql_arg = mock_sql.call_args[0][0]
        assert "WHERE department" in sql_arg and "AND operator_name" in sql_arg


# ── D4.3: write-хелперы инлайн-редакторов ─────────────────────────────────────

class TestCallEditWriteHelpers:
    """set_call_type_override/set_operator_name/set_qa_score — проверяем SQL
    и что транзакция коммитится (без реальной БД, курсор замокан)."""

    def _run(self, fn_name, *args):
        from dash_app import data
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        with patch("dash_app.data.get_connection", return_value=mock_conn):
            getattr(data, fn_name)(*args)
        return mock_conn, mock_cursor

    def test_set_call_type_override_sql(self):
        conn, cursor = self._run("set_call_type_override", "a.wav", "переводы")
        sql_arg, params = cursor.execute.call_args[0]
        assert "UPDATE call_analysis SET call_type_override" in sql_arg
        assert params == ("переводы", "a.wav")
        conn.commit.assert_called_once()

    def test_set_operator_name_sql(self):
        conn, cursor = self._run("set_operator_name", "a.wav", "Иванова")
        sql_arg, params = cursor.execute.call_args[0]
        assert "UPDATE call_analysis SET operator_name" in sql_arg
        assert params == ("Иванова", "a.wav")
        conn.commit.assert_called_once()

    def test_set_operator_name_can_clear_to_none(self):
        conn, cursor = self._run("set_operator_name", "a.wav", None)
        params = cursor.execute.call_args[0][1]
        assert params == (None, "a.wav")

    def test_set_qa_score_sql(self):
        conn, cursor = self._run("set_qa_score", "a.wav", 8.5)
        sql_arg, params = cursor.execute.call_args[0]
        assert "UPDATE call_analysis SET qa_score" in sql_arg
        assert params == (8.5, "a.wav")
        conn.commit.assert_called_once()

    def test_connection_closed_after_write(self):
        conn, _ = self._run("set_qa_score", "a.wav", 5.0)
        conn.close.assert_called_once()
