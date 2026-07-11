"""Интеграционный тест: orchestrator.analyze() — Supervisor над 4 агентами.

Агенты замоканы (быстро, детерминированно). Реальный сквозной прогон с живым
Ollama — опциональный smoke-тест, включается через RUN_SLOW_TESTS=1.
"""
import json
import os

import pytest

import orchestrator
from checklist import CHECKLIST


async def test_analyze_merges_all_four_agents(monkeypatch, fake_client, sample_transcript):
    monkeypatch.setattr(orchestrator._classifier, "_client", fake_client(json.dumps({
        "topic": "кредиты", "priority": "medium", "customer_intent": "узнать ставку",
    })))
    monkeypatch.setattr(orchestrator._quality, "_client", fake_client(json.dumps({
        "checklist": {item["key"]: True for item in CHECKLIST},
    })))
    monkeypatch.setattr(orchestrator._compliance, "_client", fake_client(json.dumps({"llm_issues": []})))
    monkeypatch.setattr(orchestrator._summarizer, "_client", fake_client(json.dumps({
        "summary": "Резюме звонка.",
        "action_items": ["Перезвонить клиенту"],
        "resolution_status": "resolved",
        "customer_satisfaction_score": 8,
        "escalation_flag": False,
        "key_topics": ["кредит"],
    })))

    result = await orchestrator.analyze(sample_transcript)

    # контракт из ТЗ
    assert result["classification"] == {"topic": "кредиты", "priority": "medium"}
    assert result["quality_score"]["total"] == 100
    assert result["compliance"] == {"passed": True, "issues": []}
    assert result["summary"] == "Резюме звонка."
    assert result["action_items"] == ["Перезвонить клиенту"]

    # доп. поля — обратная совместимость с Postgres/Streamlit-схемой
    assert result["customer_intent"] == "узнать ставку"
    assert result["resolution_status"] == "resolved"
    assert result["customer_satisfaction_score"] == 8
    assert result["escalation_flag"] is False
    assert result["key_topics"] == ["кредит"]


async def test_analyze_survives_partial_agent_failure(monkeypatch, fake_client, broken_client, sample_transcript):
    """Если один агент падает, остальные всё равно возвращают результат (нет общего краха)."""
    monkeypatch.setattr(orchestrator._classifier, "_client", broken_client)
    monkeypatch.setattr(orchestrator._quality, "_client", fake_client(json.dumps({
        "checklist": {item["key"]: False for item in CHECKLIST},
    })))
    monkeypatch.setattr(orchestrator._compliance, "_client", fake_client(json.dumps({"llm_issues": []})))
    monkeypatch.setattr(orchestrator._summarizer, "_client", fake_client(json.dumps({
        "summary": "ok", "action_items": [], "resolution_status": "resolved",
        "customer_satisfaction_score": 5, "escalation_flag": False, "key_topics": [],
    })))

    result = await orchestrator.analyze(sample_transcript)

    fallback = orchestrator._classifier.fallback()
    assert result["classification"] == {"topic": fallback["topic"], "priority": fallback["priority"]}
    assert result["customer_intent"] == fallback["customer_intent"]
    assert result["summary"] == "ok"


@pytest.mark.skipif(not os.environ.get("RUN_SLOW_TESTS"), reason="требует запущенный Ollama (RUN_SLOW_TESTS=1)")
async def test_analyze_real_ollama_smoke(sample_transcript):
    result = await orchestrator.analyze(sample_transcript)
    assert "classification" in result
    assert "quality_score" in result
    assert "compliance" in result
    assert isinstance(result["summary"], str)
