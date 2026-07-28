# Деплой и инфраструктура

## Сервисы на Railway

| Сервис | Образ/старт | Статус | Роль |
|---|---|---|---|
| `dash-director` | `dash_app/Dockerfile` → `gunicorn dash_app.app:server` | ✅ работает | **Основной публичный дашборд** |
| `call-center-dashboard` | Nixpacks + ручная start-команда (легаси) | ✅ работает | Streamlit, доступен для отката, дальше не развивается |
| `api` | `api/Dockerfile` → `uvicorn api.main:app` | ✅ работает | FastAPI: `/analyze`, `/trends`, `/coaching/{op}`, WS |
| `pipelines` | `pipelines/Dockerfile` (базовый образ `ghcr.io/open-webui/pipelines:main`) | ❌ не работает | OpenWebUI-чат — см. «Известные грабли» ниже |
| `openwebui` | `ghcr.io/open-webui/open-webui:main` | ⚠️ жив, но без LLM | Настроен на `pipelines`, который не отвечает |
| `Postgres` | managed Railway Postgres | ✅ работает | Общая БД для всех сервисов |
| `call-audio` (Bucket) | Railway Bucket (S3-совместимо) | ✅ работает | Аудио для плеера (`storage.py`) |

`dash-director`/`api`/`pipelines` — каждый со своим `Dockerfile` в
соответствующей директории (`dash_app/Dockerfile`, `api/Dockerfile`,
`pipelines/Dockerfile`), сборка ведётся с контекстом = корень репозитория
(`docker build -f <path>/Dockerfile .`) — так общие модули (`checklist.py`,
`db.py`, `asr/`, `agents/`) можно скопировать в образ без дублирования кода
между сервисами.

Плана Hobby (с 2026-07-18, до 48 vCPU/48GB RAM на сервис) достаточно для
`api` — реальный пик потребления Whisper-medium + pyannote ~2-4GB, а старый
Trial-лимит 1GB был заведомо мал (см. «Известные грабли»).

## Docker Compose (локальная разработка)

`docker-compose.yml` поднимает полный стек: `postgres` (порт `5433` на
хосте — не конфликтует с локально запущенным Postgres), `ollama` (`11435`),
`api`, `pipelines`+`openwebui` (чат), `grafana` (бонус, `3001`). Порты внутри
docker-сети — стандартные (`5432`/`11434`/…), проброс на хост сдвинут только
чтобы не конфликтовать с нативными процессами на машине разработки.

```bash
docker compose up -d
```

## Переменные окружения

Из `.env.example`:

| Переменная | Назначение |
|---|---|
| `DATABASE_URL` | Строка подключения PostgreSQL |
| `HF_TOKEN` | HuggingFace-токен для `pyannote` (диаризация) — нужно принять условия доступа на странице модели на HF |
| `LLM_BASE_URL`/`LLM_MODEL`/`LLM_API_KEY` | OpenAI-совместимый LLM-эндпоинт — по умолчанию локальный Ollama, для Groq/OpenRouter/Together меняются только эти переменные (см. [Архитектура](architecture.md#ollama-openai-client)) |
| `WHISPER_MODEL`/`WHISPER_LANGUAGE` | Модель и язык транскрипции |
| `PIPELINES_API_KEY`/`WEBUI_SECRET_KEY`/`OPENWEBUI_API_KEY` | Связь `openwebui` ↔ `pipelines` (чат, сейчас не работает) |
| `AWS_ENDPOINT_URL`/`AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY`/`AWS_S3_BUCKET_NAME`/`AWS_DEFAULT_REGION` | Railway Bucket (`storage.py`) — без них модуль работает в отключённом режиме, см. [База данных и хранилище](database.md) |
| `RAILWAY_DATABASE_PUBLIC_URL` | Публичный (proxy) connection string Postgres на Railway — только для локальных скриптов синхронизации (`scripts/add_new_calls.py`, `scripts/fix_new_calls_analysis.py`), не хардкодится |
| `DASH_SECRET_KEY` | Ключ Flask-сессии Dash-дашборда — без него генерируется случайный на каждый рестарт (сессии не переживают передеплой) |
| `API_BASE_URL` | Публичный URL сервиса `api`, который дёргает Dash-дашборд (`trends.py`, `me.py`) |

## Известные грабли

### Непинованные версии → сегфолт в проде

`pyarrow` не был запинён в `requirements.txt` — Railway поставил более новую
версию, чем локально, и `st.dataframe()` в Streamlit-легаси крашил **весь**
Python-процесс (`Segmentation fault`), выкидывая разом все активные сессии
(выглядело как случайный логаут). Это уже третий сегфолт такого типа в
истории проекта (были и с `pandas`/`psycopg2`). **Правило проекта**: любая
новая зависимость в `requirements*.txt` должна быть явно запинена версией,
не оставлена на резолвер.

### Несовместимость torch/torchvision/torchaudio в `pipelines`

Базовый образ `ghcr.io/open-webui/pipelines:main` несёт свой, заранее
собранный набор `torch`+`torchvision`+`torchaudio` (протестированный автором
образа как единое целое). Если поверх поставить `requirements-ml.txt` с
пином `torch==2.12.1`, pip обновляет только `torch`, оставляя
`torchvision`/`torchaudio` от старого набора — они собраны под другой ABI и
дают то циклический `AttributeError` при импорте `pyannote → lightning →
torchmetrics → torchvision`, то `undefined symbol` при загрузке `.so`
`torchaudio`. Подтверждено вживую через `railway ssh`: ошибка одна и та же
при любой комбинации версий, если доустанавливать поверх остатков базового
набора, а не разрешать заново.

**Фикс, уже в `pipelines/Dockerfile`**: `pip uninstall -y torch torchaudio
torchvision` перед установкой `requirements-ml.txt` — даёт pip пересобрать
зависимости `pyannote.audio` (включая `torchaudio`) с нуля в одном проходе.
Плюс два build-time смоук-теста: (1) assert, что `torchvision` не протащился
обратно транзитивной зависимостью, (2) импорт `webui_pipeline.py` тем же
способом, что и загрузчик фреймворка (`spec_from_file_location`, не `import
pyannote` изолированно) — чтобы поломанный импорт ронял **сборку** понятным
traceback'ом, а не тихо всплывал рантайм-warning'ом «No Pipeline class
found» в логах уже запущенного контейнера.

**Несмотря на это, сервис всё ещё не работает** — после передеплоя с этим
фиксом осталось необъяснённое расхождение build vs runtime: build-логи
показывают чистую установку без `torchvision`, а в реальном задеплоенном
контейнере `torchvision` всё равно на месте (сиротой, без `Required-by`).
Гипотезы про frontmatter-триггер автоустановки зависимостей фреймворка и про
`start.sh` проверены и отклонены. Диагностика сознательно остановлена —
чат не в приоритете, дальнейшие попытки дают всё меньше отдачи. Хочешь
вернуться — начинать с `railway ssh` в контейнер (см. ниже), не с новой
гипотезы вслепую.

### Отдельный `Dockerfile`/старт-команда на сервис из одного репозитория

Исторически `railway.toml` в корне репозитория (от Streamlit-сервиса)
перезаписывал `startCommand` **всем** сервисам, создаваемым из этого же
репо, на каждый `railway up` — три новых сервиса (`api`/`pipelines`/
`openwebui`) неожиданно пытались стартовать Streamlit-командой. Фикс — явно
закрепить конфиг Streamlit-сервиса через Railway UI (Settings → Deploy) и
удалить `railway.toml` из репозитория: каждый сервис получает
старт-команду/Dockerfile через свою настройку в Railway, не через файл в
репо, который расшаривается на все сервисы разом.

### `railway ssh` — только через heredoc-скрипт

Для живой диагностики контейнера: `railway ssh --service <name>
--environment production -- bash -c "..."` работает, но **надёжно только
через heredoc**, не однострочные команды с кавычками/спецсимволами — те
регулярно дают неверный вывод из-за многослойного экранирования (`railway
ssh` → remote bash → python/etc):

```bash
railway ssh --service <name> --environment production -- bash -c "cat > /tmp/x.sh << 'EOF'
#!/bin/bash
<любые команды здесь, без экранирования>
EOF
bash /tmp/x.sh"
```

Первое подключение: принять host key (`ssh -o StrictHostKeyChecking=
accept-new ssh.railway.com true`) и зарегистрировать SSH-ключ (`railway ssh
keys add`, можно из уже существующего `ssh-agent`).
