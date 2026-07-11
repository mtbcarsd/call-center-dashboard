"""Общая база для агентов: вызов LLM через OpenAI-совместимый эндпоинт + JSON-логирование.

LLM_BASE_URL по умолчанию указывает на Ollama (http://localhost:11434/v1, сам Ollama
отдаёт OpenAI-совместимый /v1/chat/completions) — переключение на Groq/OpenRouter/
Together делается только через .env, без изменений кода.
"""
import json
import logging
import os
import re
import sys
import time

from dotenv import load_dotenv
from openai import AsyncOpenAI

load_dotenv()

logger = logging.getLogger("agents")
if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False


def extract_json(text: str) -> dict | None:
    """Достаёт JSON-объект из ответа LLM, даже если модель обернула его в markdown/текст."""
    text = re.sub(r"```(?:json)?", "", text).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                return None
    return None


class BaseAgent:
    """Один сфокусированный LLM-вызов → JSON-результат. Наследники задают промпт и фолбэк."""

    name: str = "base"

    def __init__(self, base_url: str | None = None, model: str | None = None):
        self.base_url = base_url or os.environ.get("LLM_BASE_URL", "http://localhost:11434/v1")
        self.model = model or os.environ.get("LLM_MODEL", "qwen2.5-coder:7b")
        # Ollama не проверяет api_key, но клиент openai требует непустую строку
        self._client = AsyncOpenAI(
            base_url=self.base_url, api_key=os.environ.get("LLM_API_KEY", "ollama")
        )

    def build_prompt(self, transcript: str, **kwargs) -> str:
        raise NotImplementedError

    def fallback(self) -> dict:
        """Результат при ошибке LLM/невалидном JSON — переопределяется в наследниках."""
        return {}

    async def run(self, transcript: str, **kwargs) -> dict:
        t0 = time.time()
        prompt = self.build_prompt(transcript, **kwargs)
        parsed, error = None, None
        try:
            resp = await self._client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
            )
            raw = resp.choices[0].message.content or ""
            parsed = extract_json(raw)
        except Exception as e:
            error = str(e)

        output = parsed if parsed is not None else self.fallback()
        logger.info(json.dumps({
            "agent": self.name,
            "input_chars": len(transcript),
            "output": output,
            "elapsed_ms": round((time.time() - t0) * 1000),
            "parse_failed": parsed is None,
            "error": error,
        }, ensure_ascii=False))
        return output
