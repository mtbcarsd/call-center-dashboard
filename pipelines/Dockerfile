# Базовый образ open-webui/pipelines + наши ML-зависимости (Whisper/pyannote/openai)
# и наш Pipeline-класс. Сборка ведётся с контекстом = корень репозитория:
#   docker build -f pipelines/Dockerfile .
FROM ghcr.io/open-webui/pipelines:main

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Базовый образ несёт СВОЙ, заранее собранный набор torch+torchvision+torchaudio
# (тестировался как единое целое авторами образа). Если поверх него поставить
# наш requirements-ml.txt с пином torch==2.12.1, pip обновляет только torch,
# оставляя torchvision/torchaudio от старого набора — а они собраны под другой
# ABI torch'а. Итог — то циклический AttributeError на torchvision, то
# "undefined symbol" при загрузке .so torchaudio (проверено вживую через
# `railway ssh`: ошибка одна и та же при ЛЮБОЙ комбинации версий torch/torchaudio,
# если их доустанавливать поверх остатков базового набора, а не разрешать заново).
# Фикс — снести базовый набор ПОЛНОСТЬЮ и дать pip пересобрать зависимости
# pyannote.audio (в т.ч. torchaudio) с нуля в одном проходе вместе с torch==2.12.1,
# а не подгонять их постфактум.
RUN pip uninstall -y torch torchaudio torchvision

COPY requirements-ml.txt /app/requirements-ml.txt
RUN pip install --no-cache-dir -r /app/requirements-ml.txt \
    && python -c "import importlib.util; assert importlib.util.find_spec('torchvision') is None, 'torchvision снова протащился транзитивной зависимостью'"

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

# Смоук-тест: импортируем webui_pipeline.py ТОЧНО так же, как это делает загрузчик
# фреймворка (по пути файла, а не `import pyannote` изолированно) — чтобы поломанный
# импорт ронял СБОРКУ с понятным traceback-ом, а не тихо всплывал рантайм-warning'ом
# "No Pipeline class found" в логах контейнера, как это было раньше.
RUN python -c "\
import importlib.util; \
spec = importlib.util.spec_from_file_location('webui_pipeline', '/app/pipelines/webui_pipeline.py'); \
m = importlib.util.module_from_spec(spec); \
spec.loader.exec_module(m); \
print('webui_pipeline import OK:', m.Pipeline)"
