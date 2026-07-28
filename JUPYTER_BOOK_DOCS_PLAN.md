# Подробная документация на Jupyter Book

Составлено 2026-07-28 по запросу пользователя — план на несколько будущих сессий,
пока не начатый. Источник правды по общему бэклогу — README.md → «Куда развиваться»
(там будет короткая ссылка на этот файл); здесь — детальный план именно этой задачи.

## Контекст

README.md сейчас — единственный документ проекта (~380 строк), покрывающий всё
сразу: архитектуру, стек, запуск, API, БД, статус деплоя, бэклог. Пользователь
хочет **подробную документацию через Jupyter Book** — многостраничную книгу с
навигацией, а не один длинный файл.

**Подтверждённые пользователем решения:**
- **Хостинг:** пока без публикации — собирать локально (`jupyter-book build`) и
  просматривать HTML на своей машине. Решение о GitHub Pages/Railway — отдельно,
  после того как книга будет готова.
- **Роль относительно README.md:** документация **дополняет** README, не заменяет.
  README.md остаётся кратким обзором «что это и как запустить» с быстрым стартом;
  Jupyter Book — подробное референс-руководство (архитектура, паттерны, API, БД).
  Дублирование текста избегаем — README ссылается на книгу, книга не повторяет
  README дословно.

## Что уже проверено в коде (не гадаем, а исходим из фактов)

Структура репозитория, актуальная на 2026-07-28:
- **Пайплайн:** `asr/` (`transcriber.py`, `diarizer.py`), `agents/` (`base.py`,
  `classifier.py`, `quality.py`, `compliance.py`, `summarizer.py`, `trends.py`,
  `coaching.py`), `orchestrator.py`, `checklist.py`
- **Три фасада:** `pipeline.py` (batch → Postgres), `webui_pipeline.py`
  (OpenWebUI-чат, сейчас не работает), `api/main.py` (FastAPI)
- **Данные:** `db.py` (схема Postgres), `storage.py` (Railway Bucket/S3)
- **Dash-дашборд:** `dash_app/pages/` (`analytics.py`, `calls.py`, `operators.py`,
  `rating.py`, `compliance.py`, `trends.py`, `team.py`, `me.py`, `help.py`),
  `dash_app/components/` (`gauge_tile.py`, `stat_tile.py`, `delta_badge.py`,
  `page_header.py`, `cell_format.py`)
- **Streamlit-легаси:** `dashboard.py`
- **Скрипты:** `scripts/` (`seed_users.py`, `generate_synthetic_calls.py`,
  `generate_synthetic_metrics_calls.py`, `add_new_calls.py`,
  `fix_new_calls_analysis.py`, `compute_wer.py`)
- **Тесты:** `tests/` (`test_agents.py`, `test_dash_auth.py`,
  `test_dash_callbacks.py`, `test_pipeline.py`, `conftest.py`) — 122 теста, 1 skip
  для Dash-части + отдельный набор для пайплайна

`jupyter-book` не установлен в окружении — первая сессия начинается с нуля
(установка, скелет, конфиг), не с правки существующей книги.

## Структура книги (черновой `_toc.yml`)

```
Введение (index.md — что это, для кого, как читать)
├── Архитектура и обзор системы
├── Пайплайн анализа звонков (ASR + агенты + orchestrator)
├── База данных и хранилище
├── REST API
├── Dash-дашборд (страницы, компоненты, паттерны)
├── Скрипты и вспомогательные утилиты
├── Деплой и инфраструктура (Railway/Docker)
├── Тестирование
└── История проекта и куда развиваться
```

Формат — MyST Markdown (`.md`, не `.ipynb`): контент по большей части
описательный/справочный, а не исполняемый код с выводом ячеек — нет причины
тащить формат ноутбука туда, где не нужен реальный execution. Diagram'ы —
через Mermaid (поддерживается MyST из коробки), не через отдельный рендерер.

**Уточнение по ходу J1:** `jupyter-book` в PyPI сейчас — версия 2.x, это
обёртка над `mystmd`, а не старый Sphinx-based Jupyter Book 1.x. Конфиг —
один файл `myst.yml` (`project.toc`), а не пара `_config.yml`/`_toc.yml`.
CLI: `jupyter-book build` (контент), `jupyter-book build --html` (статический
сайт в `docs/_build/html/`), `jupyter-book start` (dev-сервер с live-reload).
На суть плана (разделы/сессии) это не влияет, влияет только на конкретные
файлы конфигурации.

## Сессии

### J1 — Скелет книги ✅ (2026-07-28)
- Установить `jupyter-book==2.1.6` (`requirements-docs.txt`, отдельно от
  прод-зависимостей — книга не нужна в рантайме сервисов)
- Создать `docs/` (`myst.yml` с `project.toc`, `index.md`) со структурой выше
  + страницы-заглушки для всех остальных разделов (каждая помечена, в какой
  сессии заполняется)
- Проверить, что `jupyter-book build` и `jupyter-book build --html` собираются
  локально без ошибок — собрано 10 страниц, статический HTML в
  `docs/_build/html/index.html`
- `docs/_build/` → `.gitignore` (сгенерирован автоматически при `jupyter-book
  init`, артефакты сборки не коммитим)
- Одна строка-ссылка на книгу в README.md (сделано ранее, в этой же сессии)

### J2 — Архитектура и обзор системы ✅ (2026-07-28)
- `docs/architecture.md`: компонентная диаграмма (Mermaid, проверена — MyST
  распознаёт узел как `type: mermaid`, не как обычный код-блок) — ASR → агенты →
  orchestrator → 3 фасада (pipeline.py/webui_pipeline.py/api) → Postgres/Bucket
  → Dash/Streamlit/Grafana
- Обоснования архитектурных решений из README («Почему Supervisor, а не LangGraph»,
  «Почему Ollama + OpenAI-совместимый клиент») — перенесены и расширены (со ссылками
  на конкретные файлы/докстринги), не скопированы дословно
- Дополнительно (не было в исходном пункте плана, но напрашивалось по ходу
  чтения кода): отдельный разбор каждого из 3 фасадов (специфичные особенности
  из их докстрингов — multipart-форма в `/analyze`, автообнаружение отделов в
  `pipeline.py`, протокол OpenWebUI file-тегов в `webui_pipeline.py`) и раздел
  «Dash-дашборд как потребитель» (роли/route guard) — четвёртый потребитель
  общего слоя, не производитель анализа
- Карта репозитория — сверена с реальной файловой структурой на 2026-07-28
  (README-шная версия была устаревшей: не хватало `dash_app/`, `docs/`,
  `requirements-dash.txt`, `agents/coaching.py`)
- Добавлены явные MyST-якоря (`(supervisor-vs-langgraph)=` и т.п.) перед
  ключевыми заголовками — автогенерируемые слаги для кириллических заголовков
  оказались нестабильными (MyST выкидывает кириллицу из слага; заголовок без
  латинских слов вообще получает generic `id`/`id-1`/`id-2`), без явных якорей
  кросс-ссылки между страницами книги были бы хрупкими

### J3 — Пайплайн анализа звонков ✅ (2026-07-28)
- `docs/pipeline.md`: ASR (`asr/transcriber.py` — faster-whisper + метрики пауз,
  `asr/diarizer.py` — pyannote + эвристика приветствия для определения
  оператора), 4 агента (classifier/quality/compliance/summarizer) + два
  бонусных (coaching/trends, работают с агрегатом, а не транскриптом),
  общий `BaseAgent` (контракт `build_prompt`/`fallback`, обработка ошибок LLM)
- `checklist.py` — как устроен чек-лист сейчас (6 пунктов, веса суммой 100,
  захардкожен в коде) и куда он используется (Dash-дашборд, quality-агент,
  coaching-агент)
- Сквозной пример: один звонок от аудиофайла до записи в `call_analysis` —
  по шагам `pipeline.py` (`transcribe_all` → `analyze_all` → `upload_to_db`)
- Обнаружено по ходу чтения кода (важно для J5/J8): `pipeline.py::upload_to_db()`
  делает `DELETE FROM ...` перед вставкой — полный прогон стирает все
  накопленные ручные правки; явно отмечено в тексте со ссылкой вперёд на
  `scripts.md` (J5)

### J4 — База данных и хранилище ✅ (2026-07-28)
- `docs/database.md`: полная схема `db.py` (все таблицы — `ai_transcribed_calls`,
  `call_analysis` с разбивкой на базовые/миграционные колонки, `call_segments`,
  `tags`/`call_tags`, `collections`/`call_collections`, `comments`, `users` с
  реальными значениями ролей `executive`/`manager`/`employee`), какие поля
  nullable, где сознательно нет FK (`operator_name`) и почему — со ссылкой на
  то, как `operator_match_name` в `users` используется route guard'ом
- `storage.py` — Railway Bucket, presigned URL, явно описан режим graceful
  degradation без `AWS_*` переменных (не падает, просто нет плеера)
- Краткая историческая справка (Snowflake → SQLite → Postgres) одним абзацем со
  ссылкой на git log/память — не пересказывать инцидент подробно, это не архитектура,
  а история

### J5 — REST API и скрипты ✅ (2026-07-28)
- `docs/api.md`: все 5 эндпоинтов `api/main.py` (`GET /health`, `POST
  /analyze`, `GET /trends`, `GET /coaching/{operator_name}`, `WS
  /transcribe/stream`) — запрос/ответ с примерами, где используется каждый
- `docs/scripts.md`: все 6 скриптов `scripts/*.py` разобраны по отдельности
  (`seed_users`, `generate_synthetic_calls`, `compute_wer`, `add_new_calls`,
  `fix_new_calls_analysis`, `generate_synthetic_metrics_calls`) — когда каким
  пользоваться, зафиксирован паттерн «новые звонки — отдельный INSERT-only
  скрипт, не `pipeline.py`» вынесен отдельным разделом в начало страницы
- Добавлен ещё один явный MyST-якорь (`users-table` в `database.md`) для
  ссылки из `scripts.md` — та же нестабильность автослагов, что в J3

### J6 — Dash-дашборд ✅ (2026-07-28)
- `docs/dashboard.md`: все 9 страниц `dash_app/pages/` в таблице — путь, кому
  видна, что показывает; аутентификация через Flask session (не встроенный
  механизм Dash), route guard (`_require_login`, `_EMPLOYEE_ALLOWED_PATHS`) и
  явное предупреждение, что guard защищает доступ к странице, но не сами
  данные — это отдельный department/operator_match_name-скоуп на уровне
  `load_calls()`
- Компоненты `dash_app/components/` — все 5 разобраны (`gauge_tile` с
  `max_value`/`unit`/`size="lg"` для hero-ряда, `stat_tile`, `delta_badge` с
  явным `up_is_good`, `page_header`/`section_header`, `cell_format` —
  `pct_cell`/`score_cell`/`score_dot`)
- 8 паттернов разработки вынесены отдельными подразделами (не одним общим
  абзацем): `layout()`+`@callback`, `dcc.Store` вместо состояния кнопок,
  pattern-matching id (строка, не float — реальный пойманный баг
  `calls_logic.py`/`time_cs`), `layout(**_query_params)` для query-string
  страниц, markdown-ссылки для drill-in между страницами,
  `clientside_callback` (только 2 места в проекте — аудиоплеер и тема),
  промежуточный `dcc.Store` вместо прямого `clickData` того же графика
  (реальный Plotly.js-баг на Compliance-heatmap), явный `type="category"` на
  датоподобных строковых осях, защита данных внутри каждого save-колбэка
  (`_file_in_scope()`), не только на входе в страницу

### J7 — Деплой и инфраструктура
- `docs/deployment.md`: сервисы Railway (`dash-director`, легаси
  `call-center-dashboard`, `api`, `pipelines`, `openwebui`, Postgres, Bucket) —
  что за что отвечает, статус каждого
- Docker Compose локально, переменные окружения (свести таблицу из README + то,
  чего там нет)
- Известные грабли: непинованные версии → сегфолт (`pyarrow`), несовместимость
  torch/torchvision в `pipelines`, `railway ssh` только через heredoc-скрипт

### J8 — Тестирование, история и финал
- `docs/testing.md`: структура `tests/`, подход к тестированию Dash-callback'ов,
  WER-тестирование (`scripts/compute_wer.py`)
- `docs/history.md`: сжатая хронология ключевых решений (не построчный пересказ
  журнала памяти, а то, что важно понять читателю документации — почему Postgres,
  почему Dash, почему Groq) со ссылкой на git log за подробностями
- Финальная сборка всей книги, проверка кросс-ссылок между страницами,
  причесать `_toc.yml`
- Обновить README.md (финальная формулировка ссылки на книгу) и NEXT_SESSION.md

## Что не делаем (сознательно, если не попросят отдельно)

- Не переносим содержимое README дословно — это создаёт две правды, которые
  разойдутся при первой же правке одной из них
- Не собираем `.ipynb` с исполняемым кодом — документация описательная, реальный
  запуск кода уже покрыт `tests/` и `scripts/`
- Не настраиваем публикацию (GitHub Pages/Railway) в рамках этого плана — решили
  собирать локально, публикацию обсудим отдельно, когда книга будет готова
