"""OpenWebUI Pipeline: загрузка аудио в чат → транскрипт + диаризация + анализ 4 агентами.

Переиспользует общий ASR-слой (asr/) и оркестратор агентов (orchestrator.py) — тот же
код, что и batch-пайплайн (pipeline.py → Postgres) и REST API (api/main.py).

Формат интеграции (проверено на реальном контейнере ghcr.io/open-webui/pipelines:main):
- framework вызывает `pipe(user_message, model_id, messages, body)` синхронно
  (без await — async def здесь не работает, framework не умеет ждать корутины);
- OpenWebUI НЕ кладёт файл в body["files"] при обращении к внешней OpenAI-совместимой
  модели — вместо этого встраивает тег `<file type="file" url="<file_id>"
  content_type="..." name="..."/>` прямо в текст последнего сообщения пользователя,
  где url — это id файла в БД OpenWebUI, а не ссылка;
- скачать содержимое можно через `GET {OPENWEBUI_BASE_URL}/api/v1/files/{id}/content`,
  требует Bearer-токена верифицированного пользователя (создаётся в OpenWebUI:
  Settings → Account → API Keys);
- модель дополнительно дёргается на служебные генерации OpenWebUI (поисковые запросы,
  follow-up вопросы) с промптами, начинающимися на "### Task:" — для них нужно отдавать
  безопасную заглушку, а не пытаться анализировать аудио.
"""
import asyncio
import os
import re
import tempfile

import requests
from pydantic import BaseModel

from asr.diarizer import diarize, operator_talk_ratio
from asr.transcriber import Transcriber
from orchestrator import analyze

FILE_TAG_RE = re.compile(
    r'<file\s+[^>]*url="(?P<id>[^"]+)"[^>]*content_type="(?P<content_type>[^"]+)"[^>]*/>'
)


class Pipeline:
    class Valves(BaseModel):
        WHISPER_MODEL: str = os.environ.get("WHISPER_MODEL", "medium")
        WHISPER_LANGUAGE: str = os.environ.get("WHISPER_LANGUAGE", "ru")
        OPENWEBUI_BASE_URL: str = os.environ.get("OPENWEBUI_BASE_URL", "http://openwebui:8080")
        OPENWEBUI_API_KEY: str = os.environ.get("OPENWEBUI_API_KEY", "")

    def __init__(self):
        self.valves = self.Valves()
        self.transcriber: Transcriber | None = None

    async def on_startup(self):
        self.transcriber = Transcriber(self.valves.WHISPER_MODEL, self.valves.WHISPER_LANGUAGE)

    async def on_shutdown(self):
        self.transcriber = None

    def _extract_audio_file_id(self, messages: list) -> str | None:
        """Достаёт id аудиофайла из тега <file .../>, встроенного в текст ПОСЛЕДНЕГО
        сообщения пользователя (более ранние сообщения — это уже отвеченные вложения)."""
        for message in reversed(messages):
            if message.get("role") != "user":
                continue
            content = message.get("content", "")
            if not isinstance(content, str):
                continue
            for match in FILE_TAG_RE.finditer(content):
                if match.group("content_type").startswith("audio/"):
                    return match.group("id")
            return None
        return None

    def _download_audio(self, file_id: str) -> str:
        if not self.valves.OPENWEBUI_API_KEY:
            raise RuntimeError(
                "OPENWEBUI_API_KEY не задан — создайте API-ключ в OpenWebUI "
                "(Settings → Account → API Keys) и пропишите его в .env"
            )
        url = f"{self.valves.OPENWEBUI_BASE_URL}/api/v1/files/{file_id}/content"
        resp = requests.get(
            url,
            headers={"Authorization": f"Bearer {self.valves.OPENWEBUI_API_KEY}"},
            timeout=30,
        )
        resp.raise_for_status()
        suffix = os.path.splitext(file_id)[1] or ".wav"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(resp.content)
            return tmp.name

    def _format_response(self, transcript: str, segments: list[dict], speakers: list[str],
                          analysis: dict) -> str:
        lines = ["## 📞 Анализ звонка\n"]

        lines.append("### Транскрипт по репликам")
        for seg, spk in zip(segments, speakers):
            label = {"operator": "🧑‍💼 Оператор", "client": "🙋 Клиент"}.get(spk, "❔ ?")
            lines.append(f"- `{seg['start']:.1f}–{seg['end']:.1f}с` **{label}:** {seg['text']}")

        q = analysis["quality_score"]
        lines.append(f"\n### ⭐ Оценка качества: {q['total']}/100")
        for key, val in q["checklist"].items():
            lines.append(f"- {'✅' if val else '❌'} {key}")

        c = analysis["classification"]
        lines.append(f"\n### 🏷️ Классификация: {c['topic']} (приоритет: {c['priority']})")

        comp = analysis["compliance"]
        status = "✅ пройдена" if comp["passed"] else "⚠️ найдены нарушения"
        lines.append(f"\n### 🛡️ Compliance: {status}")
        for issue in comp["issues"]:
            lines.append(f"- {issue}")

        lines.append(f"\n### 📝 Резюме\n{analysis['summary']}")
        if analysis["action_items"]:
            lines.append("\n### ✅ Action items")
            for item in analysis["action_items"]:
                lines.append(f"- {item}")

        return "\n".join(lines)

    def pipe(self, user_message: str, model_id: str, messages: list, body: dict) -> str:
        # OpenWebUI гоняет ту же модель на свои служебные промпты (генерация
        # поисковых запросов, follow-up вопросы) — их видно по маркеру "### Task:"
        # в начале контента. Для них нужно вернуть валидную заглушку, а не пытаться
        # разобрать аудио, иначе сломаются соответствующие фичи UI.
        last_content = messages[-1]["content"] if messages else ""
        if isinstance(last_content, str) and last_content.startswith("### Task:"):
            if '"queries"' in last_content:
                return '{"queries": []}'
            if '"follow_ups"' in last_content:
                return '{"follow_ups": []}'
            return "{}"

        file_id = self._extract_audio_file_id(messages)
        if not file_id:
            return "Не найден аудиофайл в сообщении. Прикрепите WAV/MP3/OGG к чату."

        audio_path = self._download_audio(file_id)
        try:
            transcriber = self.transcriber or Transcriber(
                self.valves.WHISPER_MODEL, self.valves.WHISPER_LANGUAGE
            )
            result = transcriber.run(audio_path)
            speakers = diarize(audio_path, result["segments"])
            result["operator_talk_ratio"] = operator_talk_ratio(result["segments"], speakers)

            analysis = asyncio.run(analyze(result["transcript_text"]))
            return self._format_response(
                result["transcript_text"], result["segments"], speakers, analysis
            )
        finally:
            os.unlink(audio_path)


if __name__ == "__main__":
    # Локальная проверка без OpenWebUI: python webui_pipeline.py <путь_к_wav>
    # (эмулирует тег <file>, но без реального скачивания — только для asr/agents smoke-теста)
    import sys

    async def _main():
        p = Pipeline()
        await p.on_startup()
        result = p.transcriber.run(sys.argv[1])
        speakers = diarize(sys.argv[1], result["segments"])
        analysis = await analyze(result["transcript_text"])
        print(p._format_response(result["transcript_text"], result["segments"], speakers, analysis))

    asyncio.run(_main())
