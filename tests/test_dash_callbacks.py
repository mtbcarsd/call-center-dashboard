"""Юнит-тесты Phase D1.4: callback-логика Dash-дашборда.

Callback'и тестируются как обычные Python-функции — без Selenium/dash.testing.
Сетевые вызовы (GET /trends) замоканы через unittest.mock.

Две категории:
  1. Функции данных в dash_app.data — parse_checklist, parse_compliance,
     checklist_pass_rates — не зависят от Dash вообще.
  2. _render_trends_result — чистая функция сборки UI-компонента, тоже без Dash-runtime.
"""
import json
from unittest.mock import MagicMock, patch

import pytest

from dash_app.data import checklist_pass_rates, parse_checklist, parse_compliance
from checklist import CHECKLIST


# ── parse_checklist ───────────────────────────────────────────────────────────

class TestParseChecklist:
    def test_valid_json(self):
        raw = json.dumps({"greeting": True, "closing": False})
        assert parse_checklist(raw) == {"greeting": True, "closing": False}

    def test_none_returns_empty(self):
        assert parse_checklist(None) == {}

    def test_empty_string_returns_empty(self):
        assert parse_checklist("") == {}

    def test_invalid_json_returns_empty(self):
        assert parse_checklist("{broken json") == {}

    def test_non_string_type_returns_empty(self):
        assert parse_checklist(42) == {}


# ── parse_compliance ──────────────────────────────────────────────────────────

class TestParseCompliance:
    def test_passed_no_issues(self):
        raw = json.dumps({"passed": True, "issues": []})
        assert parse_compliance(raw) == {"passed": True, "issues": []}

    def test_violation_with_issues(self):
        raw = json.dumps({"passed": False, "issues": ["Не представился", "Грубил"]})
        result = parse_compliance(raw)
        assert result["passed"] is False
        assert "Не представился" in result["issues"]

    def test_none_returns_none(self):
        assert parse_compliance(None) is None

    def test_invalid_json_returns_none(self):
        assert parse_compliance("{broken}") is None

    def test_missing_passed_defaults_true(self):
        raw = json.dumps({"issues": []})
        result = parse_compliance(raw)
        assert result["passed"] is True

    def test_null_issues_becomes_empty_list(self):
        raw = json.dumps({"passed": True, "issues": None})
        result = parse_compliance(raw)
        assert result["issues"] == []


# ── checklist_pass_rates ──────────────────────────────────────────────────────

class TestChecklistPassRates:
    _all_keys = {item["key"] for item in CHECKLIST}

    def test_all_pass(self):
        checklists = [{k: True for k in self._all_keys}] * 3
        rates = checklist_pass_rates(checklists)
        for item in CHECKLIST:
            assert rates[item["label"]] == 100.0

    def test_all_fail(self):
        checklists = [{k: False for k in self._all_keys}] * 2
        rates = checklist_pass_rates(checklists)
        for item in CHECKLIST:
            assert rates[item["label"]] == 0.0

    def test_half_pass(self):
        checklists = [
            {k: True for k in self._all_keys},
            {k: False for k in self._all_keys},
        ]
        rates = checklist_pass_rates(checklists)
        for item in CHECKLIST:
            assert rates[item["label"]] == pytest.approx(50.0)

    def test_missing_key_returns_none(self):
        # Чеклист содержит только greeting; остальные ключи отсутствуют
        checklists = [{"greeting": True}]
        rates = checklist_pass_rates(checklists)
        assert rates["Приветствие"] == 100.0
        # Пункт "Прощание" (closing) — нет данных → None
        assert rates["Прощание"] is None

    def test_empty_list_returns_all_none(self):
        rates = checklist_pass_rates([])
        for item in CHECKLIST:
            assert rates[item["label"]] is None


# ── _render_trends_result ─────────────────────────────────────────────────────

class TestRenderTrendsResult:
    """Тест чистой функции сборки Dash-компонентов по результату API."""

    def setup_method(self):
        from dash_app.trends_logic import render_trends_result
        self._fn = render_trends_result

    def test_error_contains_message(self):
        result = self._fn(None, "Connection refused")
        assert "Connection refused" in str(result)
        assert "недоступен" in str(result)

    def test_success_with_trends_and_recommendations(self):
        api_result = {
            "trends": ["Частые жалобы на ожидание"],
            "recommendations": ["Сократить время удержания на линии"],
        }
        result = self._fn(api_result, None)
        result_str = str(result)
        assert "Частые жалобы на ожидание" in result_str
        assert "Сократить время удержания" in result_str

    def test_empty_response_shows_no_data_message(self):
        result = self._fn({"trends": [], "recommendations": []}, None)
        assert "Недостаточно данных" in str(result)

    def test_none_result_shows_no_data_message(self):
        result = self._fn(None, None)
        assert "Недостаточно данных" in str(result)

    def test_only_trends_no_recommendations(self):
        api_result = {"trends": ["Паттерн А"], "recommendations": []}
        result = self._fn(api_result, None)
        assert "Паттерн А" in str(result)
        # Заголовок «Рекомендации» не должен появляться
        assert "Рекомендации" not in str(result)

    def test_only_recommendations_no_trends(self):
        api_result = {"trends": [], "recommendations": ["Совет Б"]}
        result = self._fn(api_result, None)
        assert "Совет Б" in str(result)
        assert "Найденные паттерны" not in str(result)
