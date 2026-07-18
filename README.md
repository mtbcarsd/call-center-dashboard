# 📞 Call Center Analytics

Прототип системы речевой аналитики контакт-центра банка: транскрибация звонков (ASR),
диаризация оператор/клиент, анализ через 4 независимых LLM-агента (классификация,
контроль качества, compliance, суммаризация), OpenWebUI-чат и REST API поверх общего
пайплайна.

Архитектура ориентируется на критерии тестового задания «AI Engineer — речевая
аналитика контакт-центра» ([ZubikIT/mtbank-ai-hiring](https://github.com/ZubikIT/mtbank-ai-hiring)),
но развивается как личный проект — без публикации отдельного репозитория/заявки.

## Архитектура

Один общий слой ASR + агентов переиспользуется тремя разными фасадами:

```
                    ┌───────────────────────────────┐
                    │  asr/transcriber.py             │  faster-whisper (medium, CPU)
                    │  asr/diarizer.py                 │  pyannote/speaker-diarization-3.1
                    └───────────────┬───────────────────┘
                                    │ transcript + segments + speakers
                    ┌───────────────▼───────────────────┐
                    │  orchestrator.py (Supervisor)       │  asyncio.gather — 4 агента параллельно
                    └───────────────┬───────────────────┘
              ┌─────────────────────┼─────────────────────┐
    agents/classifier.py  agents/quality.py  agents/compliance.py  agents/summarizer.py
              └─────────────────────┼─────────────────────┘
                                    │ единый JSON-контракт
        ┌───────────────────────────┼───────────────────────────┐
        │                           │                            │
 pipeline.py (batch,          webui_pipeline.py            api/main.py
 → Postgres, питает           (OpenWebUI Pipeline,          (FastAPI: POST /analyze,
 Streamlit + Grafana)         чат-интерфейс)                GET /trends, WS realtime)
```

### Почему Supervisor, а не LangGraph

Все 4 агента независимы друг от друга — каждому нужен только транскрипт, без обмена
промежуточными результатами. Граф зависимостей (LangGraph) здесь избыточен: свой
`asyncio.gather`-Supervisor (`orchestrator.py`) проще, быстрее в demo (все агенты
уходят в LLM параллельно) и тривиально unit-тестируется без дополнительного фреймворка.

### Почему Ollama + OpenAI-совместимый клиент

`agents/base.py` использует `openai` Python SDK с настраиваемым `base_url` —
по умолчанию локальный Ollama (`http://localhost:11434/v1`, сам Ollama отдаёт
OpenAI-совместимый `/v1/chat/completions`). Переключение на Groq/OpenRouter/Together
делается только через `.env` (`LLM_BASE_URL`, `LLM_MODEL`, `LLM_API_KEY`), без
изменений кода — важно для демо без GPU.

## Стек технологий

| Компонент | Технология |
|---|---|
| ASR | faster-whisper (medium, CPU) |
| Диаризация | pyannote/speaker-diarization-3.1 (pretrained) |
| LLM-агенты | Ollama (qwen2.5-coder:7b) через OpenAI-совместимый клиент |
| Оркестрация | собственный async Supervisor (`orchestrator.py`) |
| Чат-интерфейс | OpenWebUI + Pipelines (`webui_pipeline.py`) |
| REST API | FastAPI (`api/main.py`) |
| Хранилище | PostgreSQL |
| Batch-аналитика | Streamlit + Plotly (`dashboard.py`, доп. к OpenWebUI) |
| Мониторинг (бонус) | Grafana поверх той же Postgres-базы |
| Тесты | pytest + pytest-asyncio, LLM-вызовы замоканы |
| Контейнеризация | Docker Compose |
| Object storage | Railway Bucket (S3-совместимо, `storage.py`) — аудио для плеера в дашборде |
| Деплой | Railway (см. «Статус деплоя» ниже) |

## Компоненты анализа (4 агента)

| Агент | Файл | Задача |
|---|---|---|
| 🏷️ Классификатор | `agents/classifier.py` | Тематика (кредиты/карты/переводы/жалобы/другое), приоритет, намерение клиента |
| ⭐ Качество | `agents/quality.py` | Чек-лист оператора (переиспользует `checklist.py`): приветствие, выявление потребности, решение, отработка возражений, вежливость, прощание |
| 🛡️ Compliance | `agents/compliance.py` | Regex-детектор запрещённых фраз + LLM-проверка обязательных дисклеймеров |
| 📝 Суммаризатор | `agents/summarizer.py` | Резюме звонка + action items + статус разрешения обращения |
| 📈 Тренды (бонус) | `agents/trends.py` | Паттерны/проблемы по нескольким последним звонкам (`GET /trends`) |

Каждый вызов агента логируется JSON-строкой в stdout (`agents/base.py`):
`{"agent": ..., "input_chars": ..., "output": ..., "elapsed_ms": ..., "parse_failed": ..., "error": ...}`.

⚠️ Список запрещённых фраз в `agents/compliance.py` — иллюстративный стартовый набор,
для боевого использования нужно согласовать с реальным compliance-отделом банка.

## Как запустить

### Docker Compose (полный стек)

```bash
cp .env.example .env   # заполнить HF_TOKEN (см. ниже), остальное можно оставить по умолчанию
docker compose up --build
docker compose exec ollama ollama pull qwen2.5-coder:7b   # один раз, модель ~5GB
```

- OpenWebUI: http://localhost:3000 — Admin Panel → Settings → Connections → добавить
  `http://pipelines:9099` (или прописан автоматически через `OPENAI_API_BASE_URL`)
- REST API: http://localhost:8000/docs (Swagger)
- Grafana: http://localhost:3001 (admin / значение `GRAFANA_ADMIN_PASSWORD`)
- Postgres: localhost:5432

### HF_TOKEN (обязателен для диаризации)

Диаризация использует pyannote (гейтед-модели на HuggingFace). Нужно:
1. Создать токен: https://hf.co/settings/tokens
2. Принять условия доступа (залогинившись тем же аккаунтом):
   - https://hf.co/pyannote/speaker-diarization-3.1
   - https://hf.co/pyannote/segmentation-3.0
   - https://hf.co/pyannote/speaker-diarization-community-1
3. Вписать токен в `.env` → `HF_TOKEN`

### Локально без Docker

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-ml.txt
cp .env.example .env   # заполнить DATABASE_URL (локальный Postgres) и HF_TOKEN

ollama serve &
ollama pull qwen2.5-coder:7b

uvicorn api.main:app --reload --port 8000        # REST API
python pipeline.py                                # batch-прогон → Postgres → Streamlit/Grafana
streamlit run dashboard.py                         # доп. аналитика (не обязательна для ТЗ)
```

## REST API

```bash
# Файл
curl -X POST http://localhost:8000/analyze -F "file=@test_data/kredit_nalichnymi.wav"

# URL
curl -X POST http://localhost:8000/analyze -F "url=https://example.com/call.wav"

# Тренды по последним звонкам (бонус)
curl "http://localhost:8000/trends?limit=20"
```

Ответ `/analyze` — JSON: `transcript` (по репликам, спикер+таймкоды), `classification`,
`quality_score`, `compliance`, `summary`, `action_items`.

### Realtime WebSocket (бонус, `/transcribe/stream`)

Клиент шлёт WAV-чанки ~2-3с бинарными сообщениями, сервер транскрибирует **каждый чанк
независимо** (без склейки контекста между чанками) и возвращает partial-текст —
осознанный trade-off ради задержки < 3с. Для точного результата на весь файл
используйте `POST /analyze`.

## Тестовые данные и WER

Реальные записи (`audio_original_data/`) — настоящие звонки клиентов банка, остаются
**только локально** (`.gitignore`) и не публикуются. В репозиторий вместо них включены
**синтетические** звонки (`test_data/`, сгенерированы `edge-tts`: оператор —
`ru-RU-SvetlanaNeural`, клиент — `ru-RU-DmitryNeural`) — 6 файлов, суммарно 5.4 минуты,
покрывают темы кредиты/карты/переводы/жалобы/другое, один файл — в телефонном качестве
8kHz (`kredit_nalichnymi_8khz.wav`).

```bash
python scripts/generate_synthetic_calls.py   # → test_data/*.wav + *.txt (эталон)
python scripts/compute_wer.py                # → test_data/wer_report.md
```

**Средний WER (faster-whisper medium): 23.7%** — полная таблица в
[`test_data/wer_report.md`](test_data/wer_report.md). WER выше на TTS-синтетике, чем
обычно ожидается на реальной речи (интонации/паузы TTS отличаются от живой речи);
8kHz-версия ожидаемо даёт WER на ~3.5 п.п. выше полнополосной (34.8% vs 31.3%).

## Тесты

```bash
pytest tests/ -v                    # 12 unit + integration тестов, LLM замокан, <1с
RUN_SLOW_TESTS=1 pytest tests/ -v   # + smoke-тест на живом Ollama
```

- `tests/test_agents.py` — по каждому агенту: корректный JSON, невалидный JSON → fallback, сбой LLM → fallback
- `tests/test_pipeline.py` — `orchestrator.analyze()`: агенты мержатся в контракт, частичный отказ агента не роняет весь анализ

## Переменные окружения

См. [`.env.example`](.env.example): `DATABASE_URL`, `HF_TOKEN`, `LLM_BASE_URL`/`LLM_MODEL`/`LLM_API_KEY`,
`WHISPER_MODEL`, `PIPELINES_API_KEY`, `GRAFANA_ADMIN_PASSWORD`, `OPENWEBUI_API_KEY`,
`AWS_ENDPOINT_URL`/`AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY`/`AWS_S3_BUCKET_NAME` (аудио-бакет,
опционально — без них `storage.py` тихо отключает загрузку и плеер, остальной функционал не страдает).

## Бонусы (+15)

- **Grafana (+5)** — провижининг в `grafana/provisioning/`: датасорс на ту же Postgres-базу
  + дашборд (звонки по дням, средняя оценка оператора, срочность, топ тем, compliance).
  Переиспользует SQL из `dashboard.py::load_data()`.
- **Агент трендов (+5)** — `agents/trends.py` + `GET /trends`, ищет паттерны по последним N звонкам.
- **Realtime WebSocket (+5)** — `WS /transcribe/stream` в `api/main.py`, см. выше про trade-off по точности.

## Структура проекта

```
call_center_dashboard/
├── asr/
│   ├── transcriber.py          # faster-whisper обёртка
│   └── diarizer.py             # pyannote-диаризация оператор/клиент
├── agents/
│   ├── base.py                 # LLM-клиент (OpenAI-совместимый) + JSON-логи
│   ├── classifier.py           # тема + приоритет + intent
│   ├── quality.py               # чек-лист (checklist.py)
│   ├── compliance.py            # запрещённые фразы + LLM-проверка
│   ├── summarizer.py            # резюме + action items
│   └── trends.py                # паттерны по нескольким звонкам (бонус)
├── orchestrator.py              # Supervisor — 4 агента параллельно
├── webui_pipeline.py            # OpenWebUI Pipeline (чат)
├── api/
│   ├── main.py                  # FastAPI: /analyze, /trends, /transcribe/stream
│   └── Dockerfile
├── pipelines/Dockerfile         # образ для сервиса pipelines (webui_pipeline.py + деп.)
├── pipeline.py                  # batch: audio_original_data/ → Postgres
├── db.py                        # схема + подключение PostgreSQL
├── checklist.py                 # чек-лист качества оператора
├── dashboard.py                 # Streamlit — доп. аналитика (Railway-деплой)
├── scripts/
│   ├── generate_synthetic_calls.py
│   └── compute_wer.py
├── test_data/                   # синтетические звонки + эталоны + WER-отчёт
├── tests/                       # pytest: агенты + оркестратор
├── grafana/provisioning/        # датасорс + дашборд (бонус)
├── docker-compose.yml
├── requirements.txt             # лёгкий набор — только для Streamlit/Railway
├── requirements-ml.txt          # тяжёлые ML/API-зависимости
└── .env.example
```

## База данных (PostgreSQL)

Таблицы (см. `db.py`): `ai_transcribed_calls` (транскрипты), `call_analysis` (полная
аналитика: классификация, чек-лист, compliance, action items, метрики пауз/диаризации),
`call_segments` (реплики по спикерам). Новые колонки добавляются миграцией
(`ALTER TABLE ... ADD COLUMN IF NOT EXISTS`) при подключении — без ручных миграций.

## Streamlit-дашборд (доп. аналитика)

Исходный Streamlit-дашборд оставлен как дополнительная панель поверх той же
Postgres-базы (ТЗ не запрещает доп. интерфейсы, требует лишь чтобы OpenWebUI был
основным). Задеплоен на Railway и активно развивается отдельно от миграции на
сервисную архитектуру.

**URL:** https://call-center-dashboard-production-6a6b.up.railway.app
**Логин:** Julia / см. пароль в `dashboard.py::USERS`

Вкладки: 📊 Аналитика (KPI, графики, сводная таблица) · 📁 Звонки (карточная
галерея + аудиоплеер, клик по реплике перематывает на её таймкод) · 👥 Команда.

## Статус деплоя

| Сервис (Railway) | Статус | Комментарий |
|---|---|---|
| `call-center-dashboard` (Streamlit) | ✅ работает | Основной публичный дашборд, Phase 1-3 задеплоены |
| `openwebui` | ⚠️ работает, но без LLM | Сам сервис жив, но настроен на `pipelines` (см. ниже), который не отвечает — чат нефункционален |
| `Postgres` | ✅ работает | Общая база для Streamlit и сервисной архитектуры |
| `call-audio` (Bucket) | ✅ работает | Аудио для плеера, S3-совместимо |
| `api` (FastAPI) | ✅ работает | После апгрейда на Hobby-план (2026-07-18) — деплоится чисто, без OOM. `GET /trends` проверен end-to-end (Groq) |
| `pipelines` (webui_pipeline) | ❌ не работает | НЕ из-за RAM — `ghcr.io/open-webui/pipelines:main` несёт несовместимый набор torch/torchvision/torchaudio. Частично почищено (см. `pipelines/Dockerfile`), но осталось необъяснённое расхождение build/runtime — см. NEXT_SESSION.md |

Апгрейд на Railway Hobby-план (2026-07-18) снял RAM-ограничение — `api` и `GET
/trends` полностью рабочие в облаке. Оставшийся блокер чата — отдельная проблема
пакетирования в базовом Docker-образе `pipelines`, не RAM.

## Куда развиваться

📋 Конкретный план на следующую сессию (по шагам, с готовым промтом для старта) —
[NEXT_SESSION.md](NEXT_SESSION.md). Исходный анализ конкурентов —
[SPEECH_ANALYTICS_IMPROVEMENT_PLAN.md](SPEECH_ANALYTICS_IMPROVEMENT_PLAN.md) и
[COMPETITOR_VIDEOS_ANALYSIS.md](COMPETITOR_VIDEOS_ANALYSIS.md).

Streamlit-дашборд эволюционирует поэтапно в сторону возможностей уровня
специализированных инструментов транскрибации (типа OpenTranscribe), плюс то,
чего в таких инструментах обычно нет — потому что у нас уже посчитаны 4 независимых
агента, просто не всё выведено в UI.

**Готово (Phase 1):** карточная галерея звонков, аудиоплеер, переход по клику на
реплику, S3-хранилище аудио (Railway Bucket).

**Готово (Phase 2 — организация данных):**
- ✅ Ручная валидация AI-категорий — подтвердить/исправить категорию звонка прямо в деталке
- 🎙 Дикторы — имя оператора на звонке, вкладка «Операторы» со статистикой
- 🏷️ Теги и коллекции — ручная разметка звонков (напр. "спорные кейсы"), с фильтрами в сайдбаре
- 📝 Комментарии под транскриптом (автор + дата + текст)

**Готово (Phase 3 — то, что уже посчитано, но не показано):**
- 🛡️ Compliance-вкладка — общий % прохождения, список звонков с нарушениями, разбивка по оператору
  (без графика «по времени» — все звонки пока из одного batch-прогона пайплайна, см. ниже)
- 🏆 Рейтинг операторов по чек-листу с разбивкой по пунктам (не только итоговым баллом)
- 🧑‍⚖️ Ручная QA-оценка отдельно от AI-оценки — колонка `qa_score` рядом с
  `agent_performance_score`, с расхождением (Δ) между ними

**Отложено:**
- 📈 Вкладка Тренды — `agents/trends.py` и `GET /trends` существуют и рабочие, но подключать их к
  Streamlit сейчас нет смысла: на Railway нет рабочего LLM-бэкенда (`api`/`pipelines` оба упавшие,
  `openwebui` тоже настроен на упавший `pipelines`). Вернуться к этому, когда решится вопрос с
  апгрейдом Railway-плана.

**Phase 4 — интеграции:**
- 💬 Встроенный AI-чат (iframe на OpenWebUI или прямая ссылка) вместо двух разрозненных интерфейсов
- ⚡ Live-режим — `WS /transcribe/stream` в `api/main.py` уже есть, не используется в UI
- 📤 Экспорт отчётов (PDF/CSV) по фильтрам для менеджера отдела

**Phase 5 — из анализа конкурента (MeliSSA, «Единый ассистент контакт-центра»):**

Посмотрел демо-запись продукта конкурента — вот что у них есть, а у нас нет, по
убыванию применимости к нашему масштабу:

- 🔁 **Повторные обращения** — отчёт/метка "клиент уже звонил по этой теме за последние N дней".
  У них отдельный отчёт "Повторные звонки AI"; у нас для этого не хватает номера клиента в схеме
  (`call_analysis` его не хранит) — нужно сначала добавить.
- 🎲 **Выборка для ручного QA** — инструмент формирования случайной/стратифицированной подборки
  звонков на ручную проверку (не все 100% прослушивать, но и не выбирать вручную "на глаз")
- ⚙️ **Конфигурируемый чек-лист без правки кода** — у них каждый пункт чек-листа редактируется
  через UI: свой LLM-промпт с бизнес-правилами, вес, направление (вх/исх), привязка к категориям.
  У нас чек-лист захардкожен в `checklist.py`. Самая трудоёмкая, но самая ценная идея из
  всего списка — снимает зависимость от разработчика при любой правке критериев оценки.
- 🔄 **Жизненный цикл AI-правил** — новое правило категоризации сначала "Черновик" → "Тестируется"
  → только потом "Опубликован". У нас любое изменение промпта агента сразу летит в прод.
- 👤 **Персональный кабинет оператора** — оператор видит только свои звонки и KPI, не общий дашборд
  админа. У нас уже есть роли в `USERS` (сейчас только `admin`) — расширить ролью `operator` с
  урезанной вкладкой.
- 🔎 **RAG-поиск** по звонкам/базе знаний — у них отдельный отчёт "RAG поиск". Пересекается с нашим
  пунктом полнотекстового поиска ниже, но на LLM-эмбеддингах, а не `ILIKE`.
- 📚 **База знаний с трекингом прочтения** — кто из операторов открыл/не открыл важную статью,
  с датой и счётчиком. Больше про L&D-комплаенс, чем про звонки — низкий приоритет для нас.

**Инфраструктурное:**
- ~~Апгрейд Railway на Hobby-план~~ — сделано 2026-07-18, `api` разблокирован в облаке
- Починить `pipelines` (OpenWebUI-чат) — не RAM, а несовместимость torch/torchvision/torchaudio
  в базовом образе `ghcr.io/open-webui/pipelines:main`. Частично исправлено, есть необъяснённое
  расхождение build/runtime — см. NEXT_SESSION.md
- Полнотекстовый поиск по `transcript_text`/резюме (`ILIKE` хватит на текущий объём, `tsvector`+GIN — при росте)
- Sentry/error-tracking на Streamlit-сервисе — сегфолт pyarrow (см. коммит `9bc92ad`) нашли только по логам постфактум, автоалерт сэкономил бы время
- Настоящие named-спикеры вместо эвристики "оператор = говорит первым/дольше"

## Команда

**ЦАР · ds-team, sandbox — МТБанк, Беларусь**

- 👩‍🏫 Воспитатель: Пилипенко Светлана
- 🤱 Нянечка: Гуринович Анастасия
- 🔬 Data Scientist: Масловская Ксения
- 🔬 Data Scientist: Дымков Алексей
- 🔬 Data Scientist: Шилкин Андрей
