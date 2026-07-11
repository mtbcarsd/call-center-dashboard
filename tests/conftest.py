"""Общие фикстуры для тестов агентов и оркестратора."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest


class _FakeMessage:
    def __init__(self, content: str):
        self.content = content


class _FakeChoice:
    def __init__(self, content: str):
        self.message = _FakeMessage(content)


class _FakeResponse:
    def __init__(self, content: str):
        self.choices = [_FakeChoice(content)]


class _FakeCompletions:
    def __init__(self, content: str):
        self._content = content

    async def create(self, **kwargs):
        return _FakeResponse(self._content)


class _FakeChat:
    def __init__(self, content: str):
        self.completions = _FakeCompletions(content)


class FakeOpenAIClient:
    """Подменяет agents.base.BaseAgent._client — возвращает заранее заданный ответ LLM."""

    def __init__(self, content: str):
        self.chat = _FakeChat(content)


class BrokenOpenAIClient:
    """Имитирует сбой LLM (сеть/таймаут) — вызывает fallback() агента."""

    class _Completions:
        async def create(self, **kwargs):
            raise RuntimeError("LLM недоступен")

    class _Chat:
        def __init__(self):
            self.completions = BrokenOpenAIClient._Completions()

    def __init__(self):
        self.chat = self._Chat()


@pytest.fixture
def fake_client():
    return FakeOpenAIClient


@pytest.fixture
def broken_client():
    return BrokenOpenAIClient()


@pytest.fixture
def sample_transcript() -> str:
    return (
        "Добрый день, банк, меня зовут Анна, чем могу помочь? "
        "Здравствуйте, хочу узнать про условия по кредиту наличными. "
        "Конечно, какая сумма вас интересует? Десять тысяч рублей на год. "
        "Спасибо, до свидания."
    )
