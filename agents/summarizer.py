"""Агент-суммаризатор: краткое резюме звонка + список action items."""
from agents.base import BaseAgent

_PROMPT = """Ты суммаризатор звонков колл-центра банка. Составь краткое резюме и итоги звонка.

Транскрипт:
{transcript}

Верни ТОЛЬКО валидный JSON, без пояснений и markdown:
{{
  "summary": "краткое резюме звонка, 3-5 предложений на русском",
  "action_items": ["задача 1", "задача 2"],
  "resolution_status": "resolved | unresolved | escalated",
  "customer_satisfaction_score": <целое число от 1 до 10>,
  "escalation_flag": <true | false>,
  "key_topics": ["тема1", "тема2"]
}}
Если задач/тем нет — верни пустой список."""


class SummarizerAgent(BaseAgent):
    name = "summarizer"

    def build_prompt(self, transcript: str, **kwargs) -> str:
        return _PROMPT.format(transcript=transcript[:3000])

    def fallback(self) -> dict:
        return {
            "summary": "Анализ недоступен",
            "action_items": [],
            "resolution_status": "unresolved",
            "customer_satisfaction_score": 5,
            "escalation_flag": False,
            "key_topics": [],
        }
