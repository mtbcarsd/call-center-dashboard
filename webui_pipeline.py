"""OpenWebUI Pipeline: загрузка аудио в чат → транскрипт + диаризация + анализ 4 агентами.

Переиспользует общий ASR-слой (asr/) и оркестратор агентов (orchestrator.py) — тот же
код, что и batch-пайплайн (pipeline.py → Postgres) и REST API (api/main.py). Сигнатура
Pipeline/Valves/on_startup/pipe соответствует конвенции пакета `pipelines`
(https://github.com/open-webui/pipelines); при обновлении версии пакета в контейнере
сверить сигнатуру pipe() с реально установленной.
"""
import asyncio
import os
import tempfile

from pydantic import BaseModel

from asr.diarizer import diarize, operator_talk_ratio
from asr.transcriber import Transcriber
from orchestrator import analyze


class Pipeline:
    class Valves(BaseModel):
        WHISPER_MODEL: str = os.environ.get("WHISPER_MODEL", "medium")
        WHISPER_LANGUAGE: str = os.environ.get("WHISPER_LANGUAGE", "ru")

    def __init__(self):
        self.valves = self.Valves()
        self.transcriber: Transcriber | None = None

    async def on_startup(self):
        self.transcriber = Transcriber(self.valves.WHISPER_MODEL, self.valves.WHISPER_LANGUAGE)

    async def on_shutdown(self):
        self.transcriber = None

    def _extract_audio_path(self, body: dict) -> str | None:
        """Достаёт путь к загруженному в чат аудиофайлу из тела запроса OpenWebUI.

        Формат body["files"] зависит от версии пакета pipelines — при интеграции
        с реальным контейнером сверить с фактическим payload (см. документацию
        open-webui/pipelines) и при необходимости адаптировать эту функцию.
        """
        for f in body.get("files", []):
            path = f.get("file", {}).get("path") or f.get("path")
            if path and os.path.exists(path):
                return path
        return None

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

    async def pipe(self, body: dict, __user__: dict | None = None) -> str:
        audio_path = self._extract_audio_path(body)
        if not audio_path:
            return "Не найден аудиофайл в сообщении. Прикрепите WAV/MP3/OGG к чату."

        transcriber = self.transcriber or Transcriber(
            self.valves.WHISPER_MODEL, self.valves.WHISPER_LANGUAGE
        )
        result = await asyncio.to_thread(transcriber.run, audio_path)
        speakers = await asyncio.to_thread(diarize, audio_path, result["segments"])
        result["operator_talk_ratio"] = operator_talk_ratio(result["segments"], speakers)

        analysis = await analyze(result["transcript_text"])
        return self._format_response(result["transcript_text"], result["segments"], speakers, analysis)


if __name__ == "__main__":
    # Локальная проверка без OpenWebUI: python webui_pipeline.py <путь_к_wav>
    import sys

    async def _main():
        p = Pipeline()
        await p.on_startup()
        with tempfile.TemporaryDirectory():
            body = {"files": [{"path": sys.argv[1]}]}
            print(await p.pipe(body))

    asyncio.run(_main())
