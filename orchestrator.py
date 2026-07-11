"""Supervisor: запускает 4 независимых агента параллельно, собирает единый JSON-контракт.

Агенты (классификатор/качество/compliance/суммаризатор) не зависят друг от друга —
всем нужен только транскрипт, поэтому вместо графа зависимостей (LangGraph) достаточно
asyncio.gather. Используется и batch-пайплайном (pipeline.py → Postgres), и
OpenWebUI Pipeline (webui_pipeline.py), и REST API (api/main.py) — одна точка правды
для логики анализа звонка.
"""
import asyncio

from agents.classifier import ClassifierAgent
from agents.compliance import ComplianceAgent
from agents.quality import QualityAgent
from agents.summarizer import SummarizerAgent

_classifier = ClassifierAgent()
_quality = QualityAgent()
_compliance = ComplianceAgent()
_summarizer = SummarizerAgent()


async def analyze(transcript: str) -> dict:
    classification, quality, compliance, summary = await asyncio.gather(
        _classifier.run(transcript),
        _quality.run(transcript),
        _compliance.run(transcript),
        _summarizer.run(transcript),
    )
    return {
        # контракт из ТЗ (POST /analyze, OpenWebUI Pipeline)
        "classification": {
            "topic": classification.get("topic", "другое"),
            "priority": classification.get("priority", "medium"),
        },
        "quality_score": quality,
        "compliance": compliance,
        "summary": summary.get("summary", ""),
        "action_items": summary.get("action_items", []),
        # доп. поля — обратная совместимость с существующей Postgres-схемой/Streamlit-дашбордом,
        # которые не входят в минимальный контракт ТЗ, но переиспользуют те же агенты
        "customer_intent": classification.get("customer_intent", "unknown"),
        "resolution_status": summary.get("resolution_status", "unresolved"),
        "customer_satisfaction_score": summary.get("customer_satisfaction_score", 5),
        "escalation_flag": summary.get("escalation_flag", False),
        "key_topics": summary.get("key_topics", []),
    }
