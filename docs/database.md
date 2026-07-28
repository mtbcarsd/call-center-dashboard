# База данных и хранилище

## PostgreSQL: схема и миграции без ручных файлов миграций

`db.py::get_connection()` — единственная точка входа к БД. При каждом
подключении выполняется `CREATE TABLE IF NOT EXISTS` для всей схемы, затем
`_migrate()` — `ALTER TABLE call_analysis ADD COLUMN IF NOT EXISTS` для
колонок, добавленных после первого релиза. `CREATE TABLE IF NOT EXISTS` не
расширяет уже существующую таблицу новыми столбцами — поэтому для эволюции
`call_analysis` (самая часто меняющаяся таблица проекта) используется
отдельный список `_NEW_CALL_ANALYSIS_COLUMNS`, а не Alembic/классические
файлы миграций. При текущем масштабе проекта (один разработчик, одна прод-БД)
это осознанно проще: новая колонка — одна строка в словаре, без файла
миграции и версионирования схемы.

## Таблицы

### `ai_transcribed_calls` — сырой транскрипт

`file_name`, `department`, `call_topic`, `transcript_text`,
`detected_language`, `duration_sec`. Исторически первая таблица проекта —
то, что выдаёт ASR-слой до какого-либо LLM-анализа.

### `call_analysis` — вся аналитика по звонку

Основная таблица, к которой обращаются и Dash-дашборд, и Streamlit-легаси, и
REST API. Базовые колонки (заданы в `SCHEMA`):

| Колонка | Тип | Смысл |
|---|---|---|
| `file_name`, `department`, `call_topic`, `transcript_text` | TEXT | те же, что в `ai_transcribed_calls` |
| `call_summary` | TEXT | резюме от `agents/summarizer.py` |
| `sentiment_score`/`sentiment_label` | REAL/TEXT | зарезервировано, локальными моделями не считается |
| `call_type` | TEXT | тема звонка от `agents/classifier.py` (AI-значение) |
| `customer_intent`, `urgency` | TEXT | от классификатора |
| `resolution_status` | TEXT | resolved / unresolved / escalated — от суммаризатора |
| `agent_performance_score` | REAL | взвешенный итог чек-листа (0-10), `agents/quality.py` |
| `customer_satisfaction` | INTEGER | 1-10, от суммаризатора |
| `escalation_flag` | INTEGER (0/1) | от суммаризатора |
| `key_topics` | TEXT (JSON-массив) | от суммаризатора |
| `analyzed_at` | TIMESTAMP | момент прогона пайплайна (не путать с `call_datetime` ниже) |

Колонки, добавленные миграцией (`_NEW_CALL_ANALYSIS_COLUMNS`) по мере
развития проекта — каждая с обоснованием прямо в коде:

| Колонка | Тип | Смысл |
|---|---|---|
| `silence_sec`, `silence_pct`, `pause_count` | REAL/REAL/INTEGER | метрики пауз, `asr/transcriber.py::compute_pause_metrics` |
| `operator_talk_ratio` | REAL | доля времени разговора, `asr/diarizer.py` |
| `checklist_json` | TEXT (JSON) | результат чек-листа по звонку, парсится `checklist.parse_checklist()` |
| `compliance_json` | TEXT (JSON) | `{"passed": bool, "issues": [...]}`, `checklist.parse_compliance()` |
| `action_items_json` | TEXT (JSON) | от суммаризатора |
| `audio_key` | TEXT, nullable | ключ объекта в Railway Bucket; `NULL` — аудио не заливалось (см. `storage.py` ниже) |
| `call_type_override` | TEXT, nullable | ручная валидация AI-категории — если не пусто, имеет приоритет над `call_type` везде в UI |
| `operator_name` | TEXT, nullable | **свободный текст, без FK** на отдельную таблицу операторов — см. ниже |
| `qa_score` | REAL, nullable | ручная QA-оценка (0-10), отдельно от `agent_performance_score` |
| `call_datetime` | TIMESTAMP, nullable | реальное время звонка; `NULL` для старых записей, где оно неизвестно |

### `call_segments` — реплики по спикерам

`file_name`, `seg_index`, `start_sec`, `end_sec`, `speaker`, `text`. Один ряд
на реплику Whisper-сегмента с меткой `operator`/`client`/`unknown` от
`asr/diarizer.py`. Используется плеером в Dash/Streamlit для перемотки по
клику на реплику.

### Теги, коллекции, комментарии

Обычные many-to-many таблицы: `tags`/`call_tags`, `collections`/
`call_collections` (составной PK `(file_name, tag_id)` / `(file_name,
collection_id)`, FK на справочник). `comments` — простая таблица
`id`/`file_name`/`author`/`text`/`created_at`, без промежуточной таблицы (один
звонок → много комментариев, не many-to-many).

(users-table)=
### `users` — роли и доступ

```sql
CREATE TABLE IF NOT EXISTS users (
    username TEXT PRIMARY KEY,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL,              -- 'executive' | 'manager' | 'employee'
    display_name TEXT,
    department TEXT,                 -- для role='manager' — какой отдел виден
    operator_match_name TEXT,        -- для role='employee' — сверяется с call_analysis.operator_name
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

Реальная таблица с `bcrypt`-хешем (`scripts/seed_users.py`), не dict в коде,
как было раньше в Streamlit-легаси (`dashboard.py::USERS`, единственный
хардкоженный админ). `department`/`operator_match_name` — это то, чем
route guard в `dash_app/app.py` и `dash_app/data.py::load_calls()`
server-side фильтрует данные по роли (manager видит только свой отдел,
employee — только звонки, где `operator_name` совпадает с его
`operator_match_name`).

## Осознанное отсутствие FK: `operator_name`

`operator_name` — свободный TEXT, не FK на отдельную таблицу `operators`.
Решение принято дважды (сессия внедрения именования операторов, затем
подтверждено при проектировании ролей) по одному и тому же аргументу
масштаба: на объёме в десятки-сотни звонков отдельная таблица с внешним
ключом ничего не даёт для целостности данных, но добавляет джойны и миграцию
там, где хватает `GROUP BY operator_name`. Сопоставление логина `employee` с
`operator_name` в `call_analysis` тоже сделано как сравнение строк
(`operator_match_name`), а не через FK.

## Хранилище аудио: Railway Bucket

`storage.py` — S3-совместимый клиент (`boto3`) поверх Railway Bucket.
`upload_audio(file_path, key)` заливает файл при прогоне `pipeline.py`,
`presigned_url(key)` отдаёт временную ссылку (по умолчанию на час) для
плеера в дашборде.

Важное свойство: **без `AWS_S3_BUCKET_NAME`/`AWS_*` в окружении модуль
работает в отключённом режиме** — `upload_audio()` тихо ничего не делает,
`presigned_url()` возвращает `None`. Дашборд в этом случае просто не
показывает плеер (`audio_key IS NULL` в БД) — ни pipeline, ни UI не падают.
Это то же самое поведение, что и у 320 облегчённых синтетических звонков
(`scripts/generate_synthetic_metrics_calls.py`) — они никогда не заливали
аудио, поэтому `audio_key` у них всегда `NULL`.

## Краткая история: Snowflake → SQLite → PostgreSQL

Хранилище сменилось дважды до текущего PostgreSQL:

1. **Snowflake** (первые сессии проекта) — облачное хранилище с Cortex
   LLM-функциями. Отказались после блокировки аккаунта при смене пароля и
   находки захардкоженного пароля в уже запушенном публичном репозитории.
2. **SQLite** (после инцидента) — временное решение без облачных
   credentials вообще, но не годилось для деплоя на Railway (эфемерная
   файловая система).
3. **PostgreSQL** (текущее) — персистентность на Railway, текущая схема
   выше.

Подробности инцидента и переходов — в истории коммитов и журнале сессий
проекта, не повторяются здесь построчно; сжатая версия — в
[История проекта и куда развиваться](history.md).
