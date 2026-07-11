# Базовый образ open-webui/pipelines + наши ML-зависимости (Whisper/pyannote/openai)
# и наш Pipeline-класс. Сборка ведётся с контекстом = корень репозитория:
#   docker build -f pipelines/Dockerfile .
FROM ghcr.io/open-webui/pipelines:main

WORKDIR /app

COPY requirements-ml.txt /app/requirements-ml.txt
RUN pip install --no-cache-dir -r /app/requirements-ml.txt

# webui_pipeline.py импортирует asr/agents/orchestrator/checklist/db как top-level
# модули — кладём их рядом с самим pipeline-файлом внутри /app/pipelines, откуда
# фреймворк pipelines их автозагружает.
COPY asr/ /app/pipelines/asr/
COPY agents/ /app/pipelines/agents/
COPY checklist.py orchestrator.py db.py /app/pipelines/
COPY webui_pipeline.py /app/pipelines/
