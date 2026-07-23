"""Unit-тесты агентов: LLM-вызов замокан (FakeOpenAIClient/BrokenOpenAIClient из conftest)."""
import json

import pytest

from agents.classifier import ClassifierAgent
from agents.coaching import CoachingAgent, _format_summary, analyze_coaching
from agents.compliance import ComplianceAgent
from agents.quality import QualityAgent
from agents.summarizer import SummarizerAgent
from checklist import CHECKLIST


# ── Classifier ────────────────────────────────────────────────────────────────
async def test_classifier_parses_valid_json(fake_client, sample_transcript):
    agent = ClassifierAgent()
    agent._client = fake_client(json.dumps({
        "topic": "кредиты", "priority": "high", "customer_intent": "узнать ставку",
    }))
    result = await agent.run(sample_transcript)
    assert result["topic"] == "кредиты"
    assert result["priority"] == "high"
    assert result["customer_intent"] == "узнать ставку"


async def test_classifier_falls_back_on_invalid_json(fake_client, sample_transcript):
    agent = ClassifierAgent()
    agent._client = fake_client("это не json")
    result = await agent.run(sample_transcript)
    assert result == agent.fallback()


async def test_classifier_falls_back_on_llm_error(broken_client, sample_transcript):
    agent = ClassifierAgent()
    agent._client = broken_client
    result = await agent.run(sample_transcript)
    assert result == agent.fallback()


# ── Quality ───────────────────────────────────────────────────────────────────
async def test_quality_computes_total_from_checklist(fake_client, sample_transcript):
    agent = QualityAgent()
    checklist = {item["key"]: True for item in CHECKLIST}
    agent._client = fake_client(json.dumps({"checklist": checklist}))
    result = await agent.run(sample_transcript)
    assert result["total"] == 100
    assert result["checklist"] == checklist


async def test_quality_falls_back_to_empty_checklist(fake_client, sample_transcript):
    agent = QualityAgent()
    agent._client = fake_client("не json")
    result = await agent.run(sample_transcript)
    assert result["total"] == 0
    assert all(v is False for v in result["checklist"].values())


# ── Compliance ────────────────────────────────────────────────────────────────
async def test_compliance_detects_forbidden_phrase_via_regex(fake_client):
    agent = ComplianceAgent()
    agent._client = fake_client(json.dumps({"llm_issues": []}))
    transcript = "Мы гарантируем доход по этому вкладу, никаких рисков."
    result = await agent.run(transcript)
    assert result["passed"] is False
    assert len(result["issues"]) >= 1


async def test_compliance_passes_clean_transcript(fake_client, sample_transcript):
    agent = ComplianceAgent()
    agent._client = fake_client(json.dumps({"llm_issues": []}))
    result = await agent.run(sample_transcript)
    assert result["passed"] is True
    assert result["issues"] == []


async def test_compliance_includes_llm_issues(fake_client, sample_transcript):
    agent = ComplianceAgent()
    agent._client = fake_client(json.dumps({"llm_issues": ["не сообщил о записи разговора"]}))
    result = await agent.run(sample_transcript)
    assert result["passed"] is False
    assert "не сообщил о записи разговора" in result["issues"]


# ── Summarizer ────────────────────────────────────────────────────────────────
async def test_summarizer_parses_all_fields(fake_client, sample_transcript):
    agent = SummarizerAgent()
    payload = {
        "summary": "Клиент уточнил условия кредита.",
        "action_items": ["Отправить расчёт на email"],
        "resolution_status": "resolved",
        "customer_satisfaction_score": 9,
        "escalation_flag": False,
        "key_topics": ["кредит наличными"],
    }
    agent._client = fake_client(json.dumps(payload))
    result = await agent.run(sample_transcript)
    assert result == payload


async def test_summarizer_falls_back_on_invalid_json(fake_client, sample_transcript):
    agent = SummarizerAgent()
    agent._client = fake_client("не json")
    result = await agent.run(sample_transcript)
    assert result == agent.fallback()


# ── Coaching (D3.3) ─────────────────────────────────────────────────────────────
async def test_coaching_parses_valid_json(fake_client):
    agent = CoachingAgent()
    payload = {
        "strengths": ["Вежливый тон"],
        "weaknesses": ["Слабое выявление потребности"],
        "recommendations": ["Потренировать открытые вопросы"],
    }
    agent._client = fake_client(json.dumps(payload))
    result = await agent.run("- Звонков: 10", n=10, operator="Иванова")
    assert result == payload


async def test_coaching_falls_back_on_invalid_json(fake_client):
    agent = CoachingAgent()
    agent._client = fake_client("не json")
    result = await agent.run("- Звонков: 10", n=10, operator="Иванова")
    assert result == agent.fallback()


def test_coaching_format_summary_includes_checklist_and_issues():
    stats = {
        "calls_count": 5,
        "avg_agent_score": 6.5,
        "avg_customer_satisfaction": 8.0,
        "resolution_rate": 80.0,
        "checklist_rates": {"Приветствие": 100.0, "Выявление потребности": 20.0},
        "compliance_issues": ["не представился"],
    }
    summary = _format_summary(stats)
    assert "Звонков: 5" in summary
    assert "6.5/10" in summary
    assert "Выявление потребности: 20%" in summary
    assert "не представился" in summary


def test_coaching_format_summary_handles_missing_data():
    stats = {"calls_count": 3}
    summary = _format_summary(stats)
    assert "нет данных" in summary


async def test_analyze_coaching_no_calls_returns_fallback():
    result = await analyze_coaching("Иванова", {"calls_count": 0})
    assert result == {"strengths": [], "weaknesses": [], "recommendations": []}
