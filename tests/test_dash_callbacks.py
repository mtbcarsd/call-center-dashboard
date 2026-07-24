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


# ── render_coaching_result (D3.1/D3.3) ───────────────────────────────────────

class TestRenderCoachingResult:
    """Тест чистой функции сборки UI по ответу GET /coaching/{operator_name}."""

    def setup_method(self):
        from dash_app.coaching_logic import render_coaching_result
        self._fn = render_coaching_result

    def test_error_contains_message(self):
        result = self._fn(None, "Connection refused")
        assert "Connection refused" in str(result)
        assert "недоступен" in str(result)

    def test_success_with_all_sections(self):
        api_result = {
            "strengths": ["Вежливый тон"],
            "weaknesses": ["Слабое выявление потребности"],
            "recommendations": ["Тренировать открытые вопросы"],
        }
        result_str = str(self._fn(api_result, None))
        assert "Вежливый тон" in result_str
        assert "Слабое выявление потребности" in result_str
        assert "Тренировать открытые вопросы" in result_str

    def test_empty_response_shows_no_data_message(self):
        result = self._fn({"strengths": [], "weaknesses": [], "recommendations": []}, None)
        assert "Недостаточно данных" in str(result)

    def test_none_result_shows_no_data_message(self):
        assert "Недостаточно данных" in str(self._fn(None, None))

    def test_only_strengths_no_other_sections(self):
        result_str = str(self._fn({"strengths": ["Сильная сторона"]}, None))
        assert "Сильная сторона" in result_str
        assert "Точки роста" not in result_str
        assert "Рекомендации" not in result_str


# ── score_dot (D4.1) ──────────────────────────────────────────────────────────

class TestScoreDot:
    def setup_method(self):
        from dash_app.components.cell_format import score_dot
        self._fn = score_dot

    def test_high_score_green(self):
        assert self._fn(8) == "🟢"

    def test_mid_score_orange(self):
        assert self._fn(6) == "🟠"

    def test_low_score_red(self):
        assert self._fn(3) == "🔴"

    def test_boundary_good_is_green(self):
        assert self._fn(7, good=7, warn=5) == "🟢"

    def test_none_is_grey(self):
        assert self._fn(None) == "⚪"

    def test_nan_is_grey(self):
        import math
        assert self._fn(float("nan")) == "⚪"


# ── render_call_card / render_call_detail (D4.1) ─────────────────────────────

class TestRenderCallCard:
    def setup_method(self):
        from dash_app.calls_logic import render_call_card
        self._fn = render_call_card

    def _row(self, **overrides):
        base = {
            "file_name": "test.wav", "call_topic": "Потеря карты", "department": "OO",
            "urgency": "high", "call_type": "карты", "call_type_override": None,
            "call_type_effective": "карты", "operator_name": None,
            "agent_performance_score": 8.0, "resolution_status": "resolved",
        }
        base.update(overrides)
        return base

    def test_contains_topic_and_department(self):
        result_str = str(self._fn(self._row(), {"type": "open-call-btn", "index": "test.wav"}))
        assert "Потеря карты" in result_str
        assert "OO" in result_str

    def test_shows_operator_when_present(self):
        result_str = str(self._fn(self._row(operator_name="Иванова"), {"type": "x", "index": "a"}))
        assert "Иванова" in result_str

    def test_hides_operator_when_absent(self):
        result_str = str(self._fn(self._row(), {"type": "x", "index": "a"}))
        assert "🧑‍💼" not in result_str

    def test_button_has_pattern_matching_id(self):
        btn_id = {"type": "open-call-btn", "index": "test.wav"}
        result = self._fn(self._row(), btn_id)
        button = result.children[-1]
        assert button.id == btn_id

    def test_override_shows_tag_icon(self):
        result_str = str(self._fn(self._row(call_type_override="переводы"), {"type": "x", "index": "a"}))
        assert "🏷️" in result_str


class TestRenderCallDetail:
    def setup_method(self):
        from dash_app.calls_logic import render_call_detail
        self._fn = render_call_detail

    def _row(self, **overrides):
        base = {
            "call_topic": "Потеря карты", "department": "OO", "call_type": "карты",
            "call_type_override": None, "operator_name": "Иванова",
            "customer_intent": "восстановить доступ", "urgency": "high",
            "resolution_status": "resolved", "agent_performance_score": 7.5,
            "qa_score": None, "customer_satisfaction": 9, "escalation_flag": 0,
            "silence_pct": None, "pause_count": None, "operator_talk_ratio": None,
            "key_topics": None, "checklist_json": None, "compliance_json": None,
            "call_summary": None, "transcript_text": "Полный текст разговора.",
            "segments": None,
        }
        base.update(overrides)
        return base

    def test_shows_ai_unconfirmed_type(self):
        result_str = str(self._fn(self._row()))
        assert "AI, не подтверждено" in result_str

    def test_shows_confirmed_override_type(self):
        result_str = str(self._fn(self._row(call_type_override="переводы")))
        assert "переводы" in result_str
        assert "AI предложил: карты" in result_str

    def test_qa_score_shows_delta(self):
        result_str = str(self._fn(self._row(qa_score=9.0, agent_performance_score=7.0)))
        assert "+2.0" in result_str

    def test_no_qa_score_shows_placeholder(self):
        result_str = str(self._fn(self._row()))
        assert "не проставлена" in result_str

    def test_checklist_renders_pass_fail_icons(self):
        checklist = {item["key"]: True for item in __import__("checklist").CHECKLIST}
        result_str = str(self._fn(self._row(checklist_json=checklist)))
        assert "✅" in result_str

    def test_compliance_violations_shown(self):
        compliance = {"passed": False, "issues": ["Не представился"]}
        result_str = str(self._fn(self._row(compliance_json=compliance)))
        assert "Не представился" in result_str

    def test_compliance_clean_shows_success(self):
        compliance = {"passed": True, "issues": []}
        result_str = str(self._fn(self._row(compliance_json=compliance)))
        assert "нарушений не найдено" in result_str

    def test_transcript_fallback_without_segments(self):
        result_str = str(self._fn(self._row()))
        assert "Полный текст разговора." in result_str

    def test_segments_render_speaker_labels(self):
        segments = [{"speaker": "operator", "start_sec": 0, "end_sec": 5, "text": "Здравствуйте"}]
        result_str = str(self._fn(self._row(segments=segments)))
        assert "Здравствуйте" in result_str
        assert "Оператор" in result_str

    def test_summary_shown_when_present(self):
        result_str = str(self._fn(self._row(call_summary="Клиент решил вопрос.")))
        assert "Клиент решил вопрос." in result_str

    # ── D4.2: плеер + перемотка ────────────────────────────────────────────

    def test_no_audio_url_shows_unavailable_message(self):
        result_str = str(self._fn(self._row()))
        assert "Аудио для этого звонка недоступно" in result_str

    def test_audio_url_renders_audio_element(self):
        from dash_app.calls_logic import AUDIO_PLAYER_ID
        result = self._fn(self._row(), audio_url="https://example.com/a.mp3")
        result_str = str(result)
        assert "Аудио для этого звонка недоступно" not in result_str
        # html.Audio должен получить фиксированный id (нужен clientside_callback'у)
        audio_block = result.children[1]
        assert audio_block.id == AUDIO_PLAYER_ID
        assert audio_block.src == "https://example.com/a.mp3"

    def test_seek_buttons_rendered_only_with_audio_and_segments(self):
        segments = [{"speaker": "operator", "start_sec": 12.0, "end_sec": 15.0, "text": "Привет"}]
        without_audio = str(self._fn(self._row(segments=segments)))
        with_audio = str(self._fn(self._row(segments=segments), audio_url="https://example.com/a.mp3"))
        assert "seek-btn" not in without_audio
        assert "seek-btn" in with_audio

    def test_seek_button_id_carries_start_sec_as_centiseconds(self):
        # Не float — Dash 2.18 ломает внутренний парсер триггера на pattern-matching
        # id со значением-float (режет prop_id по точке внутри самого числа).
        segments = [{"speaker": "operator", "start_sec": 12.5, "end_sec": 15.0, "text": "Привет"}]
        result = self._fn(self._row(segments=segments), audio_url="https://example.com/a.mp3")
        # правая колонка -> блок реплик -> первая строка -> первый child (кнопка)
        seg_row = result.children[2].children[1].children[-1].children[0]
        seek_btn = seg_row.children[0]
        assert seek_btn.id == {"type": "seek-btn", "time_cs": 1250}
        assert isinstance(seek_btn.id["time_cs"], int)
