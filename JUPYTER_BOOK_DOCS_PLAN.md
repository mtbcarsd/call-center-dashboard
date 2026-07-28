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

### J2 — Архитектура и обзор системы
- `docs/architecture.md`: компонентная диаграмма (Mermaid) — ASR → агенты →
  orchestrator → 3 фасада (pipeline.py/webui_pipeline.py/api) → Postgres/Bucket
- Обоснования архитектурных решений из README («Почему Supervisor, а не LangGraph»,
  «Почему Ollama + OpenAI-совместимый клиент») — перенести и расширить, не копировать
  один в один
- Карта репозитория: что за директория, куда смотреть за какой задачей

### J3 — Пайплайн анализа звонков
- `docs/pipeline.md`: ASR (`asr/transcriber.py`, `asr/diarizer.py` — pyannote),
  4 агента + coaching/trends (`agents/*.py`, общий `BaseAgent`), `orchestrator.py`
  (`asyncio.gather`, независимость агентов)
- `checklist.py` — как устроен чек-лист сейчас (захардкожен) и куда он используется
  (Dash-дашборд, coaching-агент)
- Сквозной пример: один звонок от аудиофайла до записи в `call_analysis`

### J4 — База данных и хранилище
- `docs/database.md`: полная схема `db.py` (все таблицы — `call_analysis`,
  `call_segments`, `users`, `tags`/`call_tags`, `collections`/`call_collections`,
  `comments`), какие поля nullable, где сознательно нет FK (`operator_name` —
  свободный текст) и почему
- `storage.py` — Railway Bucket, presigned URL для плеера
- Краткая историческая справка (Snowflake → SQLite → Postgres) одним абзацем со
  ссылкой на git log/память — не пересказывать инцидент подробно, это не архитектура,
  а история

### J5 — REST API и скрипты
- `docs/api.md`: эндпоинты `api/main.py` (`POST /analyze`, `GET /trends`,
  `GET /coaching/{operator_name}`, `WS /transcribe/stream`) — запрос/ответ,
  где используется каждый (Dash-дашборд, WS пока нигде)
- `docs/scripts.md`: `scripts/*.py` — когда каким пользоваться, явно зафиксировать
  паттерн «новые звонки — отдельный INSERT-only скрипт, не `pipeline.py`»
  (`pipeline.py` делает `DELETE FROM call_analysis` + пересчёт всего)

### J6 — Dash-дашборд
- `docs/dashboard.md`: все страницы `dash_app/pages/` — что показывают, кому видны
  (executive/manager/employee route guard), ссылки между страницами (drill-in
  `?op=<имя>`)
- Компоненты `dash_app/components/` — переиспользуемые строительные блоки
  (`gauge_tile`, `stat_tile`, `delta_badge`, `page_header`, `cell_format`)
- Паттерны разработки: `layout()` + `@callback` для перерисовки без потери
  состояния, `dcc.Store` вместо чтения состояния кнопок напрямую, осторожность с
  pattern-matching id (float vs строка), светлая/тёмная тема через CSS custom
  properties — это то, что нужно новому человеку/будущей сессии, чтобы не
  наступить на уже известные грабли

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
