"""Агент-классификатор: тематика обращения + приоритет."""
from agents.base import BaseAgent

_PROMPT = """Ты классификатор обращений в колл-центр банка. Определи тематику, приоритет и намерение клиента по транскрипту.

Транскрипт:
{transcript}

Верни ТОЛЬКО валидный JSON, без пояснений и markdown:
{{
  "topic": "кредиты | карты | переводы | жалобы | другое",
  "priority": "low | medium | high",
  "customer_intent": "намерение клиента одной фразой"
}}"""


class ClassifierAgent(BaseAgent):
    name = "classifier"

    def build_prompt(self, transcript: str, **kwargs) -> str:
        return _PROMPT.format(transcript=transcript[:3000])

    def fallback(self) -> dict:
        return {"topic": "другое", "priority": "medium", "customer_intent": "unknown"}
