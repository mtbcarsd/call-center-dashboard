"""Агент трендов (бонус): анализирует резюме/темы нескольких последних звонков,
ищет повторяющиеся паттерны и проблемы — в отличие от остальных 4 агентов, работает
не с одним транскриптом, а с агрегатом по многим звонкам (данные берутся из Postgres,
см. GET /trends в api/main.py).
"""
from agents.base import BaseAgent

_PROMPT = """Ты аналитик колл-центра банка. Ниже — резюме и темы последних {n} звонков.
Найди повторяющиеся паттерны, частые проблемы клиентов или узкие места в работе операторов.

{calls}

Верни ТОЛЬКО валидный JSON, без пояснений и markdown:
{{
  "trends": ["найденный паттерн 1", "паттерн 2"],
  "recommendations": ["рекомендация для супервайзера 1"]
}}
Если данных недостаточно для выводов — верни пустые списки."""


class TrendsAgent(BaseAgent):
    name = "trends"

    def build_prompt(self, transcript: str, **kwargs) -> str:
        return _PROMPT.format(n=kwargs.get("n", 0), calls=transcript)

    def fallback(self) -> dict:
        return {"trends": [], "recommendations": []}


async def analyze_trends(calls: list[dict]) -> dict:
    """calls: [{"call_topic": ..., "call_summary": ..., "key_topics": [...]}, ...]"""
    agent = TrendsAgent()
    formatted = "\n".join(
        f"- [{c.get('call_topic', '?')}] {c.get('call_summary', '')} "
        f"(темы: {', '.join(c.get('key_topics') or [])})"
        for c in calls
    )
    if not formatted:
        return agent.fallback()
    return await agent.run(formatted, n=len(calls))
