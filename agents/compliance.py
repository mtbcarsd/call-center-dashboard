"""Compliance-агент: запрещённые фразы (regex) + LLM-проверка обязательных дисклеймеров.

Список фраз — стартовый иллюстративный набор. Для боевого использования его нужно
согласовать с реальным compliance-отделом банка (юридические формулировки,
обязательные для конкретных продуктов, здесь не приведены).
"""
import re

from agents.base import BaseAgent

FORBIDDEN_PATTERNS = [
    (re.compile(r"гаранти\w*\s+(доход|прибыль|результат)", re.IGNORECASE),
     "Обещание гарантированного дохода/результата"),
    (re.compile(r"100\s*%\s*(без\s*риска|гарант)", re.IGNORECASE),
     "Обещание отсутствия рисков"),
    (re.compile(r"\b(дура\w*|идиот\w*|тупо\w*)\b", re.IGNORECASE),
     "Оскорбление клиента"),
]

_PROMPT = """Ты compliance-агент банковского колл-центра. Проверь транскрипт на нарушения:
не упомянуты ли обязательные предупреждения (например, что разговор может записываться,
условия и риски финансового продукта), нет ли некорректных или незаконных обещаний оператора.

Транскрипт:
{transcript}

Верни ТОЛЬКО валидный JSON, без пояснений и markdown:
{{
  "llm_issues": ["найденная проблема 1", "найденная проблема 2"]
}}
Если нарушений нет — верни пустой список."""


class ComplianceAgent(BaseAgent):
    name = "compliance"

    def build_prompt(self, transcript: str, **kwargs) -> str:
        return _PROMPT.format(transcript=transcript[:3000])

    def fallback(self) -> dict:
        return {"llm_issues": []}

    async def run(self, transcript: str, **kwargs) -> dict:
        regex_issues = [label for pattern, label in FORBIDDEN_PATTERNS if pattern.search(transcript)]
        llm_result = await super().run(transcript, **kwargs)
        issues = regex_issues + list(llm_result.get("llm_issues", []))
        return {"passed": len(issues) == 0, "issues": issues}
