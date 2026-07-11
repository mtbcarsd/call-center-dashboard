"""Агент качества: чек-лист оператора (переиспользует checklist.py)."""
from agents.base import BaseAgent
from checklist import CHECKLIST, weighted_score

_QUESTIONS = "\n".join(
    f'  "{item["key"]}": <true/false — {item["question"]}>' for item in CHECKLIST
)

_PROMPT = """Ты агент контроля качества колл-центра банка. Оцени звонок по чек-листу.

Транскрипт:
{transcript}

Верни ТОЛЬКО валидный JSON, без пояснений и markdown (по каждому пункту true либо false):
{{
  "checklist": {{
{questions}
  }}
}}"""

_EMPTY_CHECKLIST = {item["key"]: False for item in CHECKLIST}


class QualityAgent(BaseAgent):
    name = "quality"

    def build_prompt(self, transcript: str, **kwargs) -> str:
        return _PROMPT.format(transcript=transcript[:3000], questions=_QUESTIONS)

    def fallback(self) -> dict:
        return {"checklist": dict(_EMPTY_CHECKLIST)}

    async def run(self, transcript: str, **kwargs) -> dict:
        result = await super().run(transcript, **kwargs)
        checklist = result.get("checklist") or dict(_EMPTY_CHECKLIST)
        total = round(weighted_score(checklist) * 10)  # weighted_score: 0-10 → total: 0-100
        return {"total": total, "checklist": checklist}
