# Архитектура и обзор системы

Один общий слой (ASR + 4 LLM-агента + оркестратор) переиспользуется четырьмя
разными потребителями: batch-пайплайном в Postgres, чат-интеграцией OpenWebUI,
REST API и — надстройкой над всем этим — Dash-дашбордом, который читает уже
посчитанные Postgres-данные и дополнительно дёргает API за LLM-функциями
(тренды, коучинг).

(component-diagram)=
## Компонентная схема

```{mermaid}
flowchart TB
    subgraph ASR["ASR-слой"]
        T["asr/transcriber.py<br/>faster-whisper (medium, CPU)"]
        D["asr/diarizer.py<br/>pyannote/speaker-diarization-3.1"]
    end

    ASR -->|"transcript + segments + speakers"| O

    O["orchestrator.py (Supervisor)<br/>asyncio.gather — 4 агента параллельно"]

    subgraph Agents["agents/"]
        C1["classifier.py"]
        C2["quality.py"]
        C3["compliance.py"]
        C4["summarizer.py"]
    end

    O --> C1 & C2 & C3 & C4
    C1 & C2 & C3 & C4 -->|"единый JSON-контракт"| Facades

    subgraph Facades["Три фасада поверх общего слоя"]
        P["pipeline.py<br/>batch → Postgres"]
        W["webui_pipeline.py<br/>OpenWebUI Pipeline (чат)"]
        A["api/main.py<br/>FastAPI: /analyze, /trends,<br/>/coaching/{op}, WS /transcribe/stream"]
    end

    P --> DB[("PostgreSQL<br/>db.py")]
    P --> S3[("Railway Bucket<br/>storage.py")]

    subgraph Consumers["Потребители данных"]
        DASH["Dash-дашборд<br/>dash_app/ (основной)"]
        ST["Streamlit<br/>dashboard.py (легаси)"]
        GRAF["Grafana"]
    end

    DB --> DASH & ST & GRAF
    S3 --> DASH
    A -->|"GET /trends, GET /coaching/{op}"| DASH
    W -.->|"не работает,<br/>см. Деплой"| OWUI["OpenWebUI"]
```

(supervisor-vs-langgraph)=
## Почему Supervisor, а не LangGraph

Все 4 агента (`classifier`, `quality`, `compliance`, `summarizer`) независимы
друг от друга — каждому нужен только транскрипт целиком, без обмена
промежуточными результатами и без ветвления по условию. Граф зависимостей
(LangGraph) был бы избыточен для линейного «запустить всё параллельно, собрать
результат»: свой `asyncio.gather`-Supervisor (`orchestrator.py`, 46 строк)
проще, быстрее в демо (все 4 вызова LLM уходят параллельно, а не
последовательно по рёбрам графа) и тривиально unit-тестируется без
дополнительного фреймворка — достаточно замокать `Agent.run()`.

Тот же `orchestrator.analyze()` переиспользуется всеми тремя фасадами
(`pipeline.py`, `webui_pipeline.py`, `api/main.py`) — одна точка правды для
логики анализа звонка, а не три копии.

(ollama-openai-client)=
## Почему Ollama + OpenAI-совместимый клиент

`agents/base.py` — общая база агентов: вызов LLM через `openai` Python SDK
(`AsyncOpenAI`) с настраиваемым `base_url`, плюс JSON-логирование и
`extract_json()` — вытаскивает JSON из ответа модели, даже если она обернула
его в markdown-блок или добавила текст вокруг.

По умолчанию `base_url` указывает на локальный Ollama
(`http://localhost:11434/v1`) — сам Ollama отдаёт OpenAI-совместимый
`/v1/chat/completions`, так что код агентов не завязан на конкретного
провайдера. Переключение на Groq/OpenRouter/Together делается только через
`.env` (`LLM_BASE_URL`, `LLM_MODEL`, `LLM_API_KEY`), без изменений кода —
это и позволило перейти на облачный Groq для прод-деплоя на Railway (см.
[Деплой и инфраструктура](deployment.md)), когда локальный Ollama на CPU/RAM
Trial-плана оказался не вариантом.

(three-facades)=
## Три фасада поверх общего слоя

Каждый фасад решает свою задачу интеграции, но не дублирует логику анализа:

**`pipeline.py`** — batch-обработка: обходит `audio_original_data/<отдел>/`,
транскрибирует+диаризует+анализирует каждый новый файл, пишет в Postgres и
заливает аудио в Railway Bucket (`storage.py`). Отделы определяются
автоматически по имени подпапки (`_discover_departments()`) — новый отдел не
нужно прописывать в коде вручную, только положить файлы в новую подпапку.
Важно: полный прогон `pipeline.py` делает `DELETE FROM call_analysis` и
пересчитывает всё заново — для точечного добавления новых звонков без
пересчёта существующих используются отдельные INSERT-only скрипты (см.
[Скрипты и вспомогательные утилиты](scripts.md)).

**`webui_pipeline.py`** — интеграция с OpenWebUI как Pipeline-плагин для
чат-интерфейса. Особенности протокола, подтверждённые на реальном контейнере
`ghcr.io/open-webui/pipelines:main`: framework вызывает `pipe(...)`
синхронно (`async def` не работает — framework не умеет ждать корутины);
файл, приложенный в чате, не попадает в `body["files"]` при обращении к
внешней OpenAI-совместимой модели — вместо этого OpenWebUI встраивает тег
`<file type="file" url="<file_id>" .../>` прямо в текст сообщения
пользователя, а содержимое скачивается отдельным запросом с Bearer-токеном.
Сервис `pipelines` на Railway сейчас не работает по независящей от этого кода
причине (несовместимость версий torch) — см. [Деплой](deployment.md).

**`api/main.py`** — FastAPI: `POST /analyze` (файл или URL аудио, ответ —
JSON-анализ звонка), `GET /trends` и `GET /coaching/{operator_name}`
(LLM-агенты `agents/trends.py`/`agents/coaching.py`, вызываются
Dash-дашбордом), `WS /transcribe/stream` (реализован, в UI пока не
используется). `file`/`url` в `/analyze` — поля одной
`multipart/form-data`-формы, а не альтернативные Content-Type на одной ручке:
FastAPI не умеет смешивать JSON-body и `File` в одном эндпоинте.

(dash-as-consumer)=
## Dash-дашборд как потребитель

В отличие от трёх фасадов выше (которые производят анализ), `dash_app/`
только читает уже посчитанные данные из Postgres + Bucket и дополнительно
ходит в `api/main.py` за двумя LLM-функциями, которые нет смысла пересчитывать
на каждой загрузке страницы (тренды, коучинг). Ролевой доступ
(executive/manager/employee) реализован как route guard на уровне Flask
(`dash_app/app.py`) — сотруднику (`role=employee`) разрешены только
`/me`/`/help`/`/login`/`/logout`, остальные пути редиректят. Подробности
структуры страниц — в [Dash-дашборд](dashboard.md).

(repo-map)=
## Карта репозитория

```
call_center_dashboard/
├── asr/                    # транскрипция (faster-whisper) + диаризация (pyannote)
├── agents/                 # 4 основных LLM-агента + trends.py (бонус) + coaching.py
├── orchestrator.py         # Supervisor — 4 агента параллельно
├── checklist.py            # чек-лист качества оператора (общий для агентов и Dash)
├── db.py                   # схема Postgres + подключение
├── storage.py              # Railway Bucket (S3-совместимо)
│
├── pipeline.py             # facade: batch → Postgres
├── webui_pipeline.py       # facade: OpenWebUI Pipeline (чат)
├── api/                    # facade: FastAPI (main.py, Dockerfile)
│
├── dash_app/               # основной публичный дашборд (Plotly Dash)
│   ├── pages/              # analytics, calls, operators, rating, compliance,
│   │                       # trends, team, me, help
│   └── components/         # gauge_tile, stat_tile, delta_badge, page_header, cell_format
├── dashboard.py            # легаси Streamlit-дашборд (доступен для отката)
│
├── scripts/                # seed_users, генерация синтетики, INSERT-only добавление звонков, WER
├── tests/                  # pytest: агенты, оркестратор, Dash auth/callbacks, пайплайн
├── test_data/              # синтетические звонки + эталоны для WER
├── docs/                   # эта книга (Jupyter Book / MyST)
├── grafana/provisioning/   # датасорс + дашборд (бонус)
├── pipelines/Dockerfile    # образ сервиса pipelines (webui_pipeline.py + зависимости)
│
├── docker-compose.yml
├── requirements.txt            # Streamlit/Railway (лёгкий набор)
├── requirements-ml.txt         # тяжёлые ML/API-зависимости (torch, whisper, pyannote)
├── requirements-dash.txt       # Dash-дашборд
├── requirements-docs.txt       # jupyter-book (только для сборки документации)
└── .env.example
```

Подробности каждого слоя — в соответствующих разделах:
[Пайплайн анализа звонков](pipeline.md), [База данных и хранилище](database.md),
[REST API](api.md), [Dash-дашборд](dashboard.md).
