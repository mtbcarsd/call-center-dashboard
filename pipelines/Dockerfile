# Базовый образ open-webui/pipelines + наши ML-зависимости (Whisper/pyannote/openai)
# и наш Pipeline-класс. Сборка ведётся с контекстом = корень репозитория:
#   docker build -f pipelines/Dockerfile .
FROM ghcr.io/open-webui/pipelines:main

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-ml.txt /app/requirements-ml.txt
RUN pip install --no-cache-dir -r /app/requirements-ml.txt
# Базовый образ несёт свой torchvision, несовместимый с нашим torch==2.12.1
# (ломает импорт pyannote → lightning → torchmetrics → torchvision циклическим
# AttributeError). В коде torchvision не используется — просто убираем его.
RUN pip uninstall -y torchvision

# Фреймворк pipelines нерекурсивно сканирует PIPELINES_DIR (/app/pipelines) и
# каждый лежащий там .py без класса Pipeline перемещает в failed/ — поэтому общий
# код (asr/agents/orchestrator/checklist/db) кладём в подпапку lib/, которую
# сканер не трогает, и подключаем через PYTHONPATH. В PIPELINES_DIR остаётся
# только сам webui_pipeline.py.
COPY asr/ /app/pipelines/lib/asr/
COPY agents/ /app/pipelines/lib/agents/
COPY checklist.py orchestrator.py db.py /app/pipelines/lib/
COPY webui_pipeline.py /app/pipelines/
ENV PYTHONPATH=/app/pipelines/lib
