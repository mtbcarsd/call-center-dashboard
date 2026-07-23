"""Агент коучинга: рекомендации по обучению для конкретного оператора.

В отличие от 4 основных агентов (classifier/quality/compliance/summarizer),
не анализирует транскрипт заново — работает с уже посчитанной агрегированной
статистикой по звонкам оператора (чек-лист, compliance, оценки), как
agents/trends.py работает с резюме нескольких звонков. См. GET
/coaching/{operator_name} в api/main.py.
"""
from agents.base import BaseAgent

_PROMPT = """Ты тренер по качеству обслуживания в банковском колл-центре.
Ниже — сводка по {n} звонкам оператора «{operator}»:

{summary}

Дай короткую и конкретную обратную связь для этого оператора: в чём он силён,
в чём проседает, и что конкретно ему стоит потренировать.

Верни ТОЛЬКО валидный JSON, без пояснений и markdown:
{{
  "strengths": ["сильная сторона 1"],
  "weaknesses": ["слабое место 1"],
  "recommendations": ["конкретная рекомендация по обучению 1"]
}}
Если данных недостаточно для выводов — верни пустые списки."""


class CoachingAgent(BaseAgent):
    name = "coaching"

    def build_prompt(self, transcript: str, **kwargs) -> str:
        return _PROMPT.format(
            n=kwargs.get("n", 0), operator=kwargs.get("operator", "?"), summary=transcript
        )

    def fallback(self) -> dict:
        return {"strengths": [], "weaknesses": [], "recommendations": []}


def _format_summary(stats: dict) -> str:
    def _pct(value):
        return f"{value:.0f}%" if value is not None else "нет данных"

    def _score(value):
        return f"{value:.1f}/10" if value is not None else "нет данных"

    lines = [
        f"- Звонков: {stats['calls_count']}",
        f"- Средняя оценка по чек-листу: {_score(stats.get('avg_agent_score'))}",
        f"- Удовлетворённость клиентов: {_score(stats.get('avg_customer_satisfaction'))}",
        f"- Доля решённых обращений: {_pct(stats.get('resolution_rate'))}",
    ]
    checklist_rates = stats.get("checklist_rates") or {}
    if checklist_rates:
        lines.append("- Прохождение по пунктам чек-листа:")
        lines.extend(f"  · {label}: {_pct(pct)}" for label, pct in checklist_rates.items())
    issues = stats.get("compliance_issues") or []
    if issues:
        lines.append("- Compliance-нарушения, встречавшиеся у оператора:")
        lines.extend(f"  · {issue}" for issue in issues)
    return "\n".join(lines)


async def analyze_coaching(operator_name: str, stats: dict) -> dict:
    """stats — агрегаты по звонкам оператора, см. coaching_endpoint в api/main.py."""
    agent = CoachingAgent()
    if not stats.get("calls_count"):
        return agent.fallback()
    summary = _format_summary(stats)
    return await agent.run(summary, n=stats["calls_count"], operator=operator_name)
