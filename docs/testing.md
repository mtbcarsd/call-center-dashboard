# Тестирование

## `tests/` — pytest, LLM-вызовы замоканы

123 теста (`pytest tests/ -v`), 1 из них — опциональный smoke-тест с живым
Ollama (`RUN_SLOW_TESTS=1 pytest tests/ -v`), по умолчанию пропускается —
отсюда «122 + 1 skip» в статусе проекта.

**`conftest.py`** — общие фикстуры: `FakeOpenAIClient` (детерминированно
возвращает заранее заданный JSON-ответ вместо реального вызова LLM,
подменяет `BaseAgent._client`), `BrokenOpenAIClient` (эмулирует сбой
сети/таймаут — проверяет, что срабатывает `fallback()`), `sample_transcript`.
Ни один тест не ходит в реальный Ollama/Groq — быстро (< 1с) и
детерминированно.

**`test_agents.py`** — по каждому из 4 основных агентов + coaching: парсинг
валидного JSON, откат на `fallback()` при невалидном JSON и при ошибке LLM
(`agent._client = fake_client(...)` / `broken_client`).

**`test_pipeline.py`** — интеграционный тест `orchestrator.analyze()`: все 4
клиента агентов подменены через `monkeypatch.setattr(orchestrator._classifier,
"_client", ...)` и т.д., проверяется итоговый собранный контракт (`
classification`/`quality_score`/`compliance`/`summary`/`action_items`), плюс
тест устойчивости к частичному отказу одного агента. `
test_analyze_real_ollama_smoke` — тот самый опциональный тест с реальным
Ollama.

**`test_dash_auth.py`** (Phase D2) — без Selenium/`dash.testing`: bcrypt
round-trip (`hash_password`/`verify_password`), чтение Flask-сессии (`
get_current_user`/`get_current_department`/`get_current_operator_match_name`
через `unittest.mock`), и что `load_calls(department=...)` действительно
применяет SQL-фильтр — то есть тестируется именно server-side скоуп по
роли, не просто наличие функции.

**`test_dash_callbacks.py`** — callback-логика Dash как обычные Python-функции:
парсинг `checklist_json`/`compliance_json`, генерация markdown/ag-grid
структур, CRUD-хелперы тегов/коллекций/комментариев (`set_call_labels`,
`add_comment` — проверяются собранные SQL-запросы, не реальная БД).

## Почему без Selenium/`dash.testing`

Ни один Dash-тест не поднимает браузер или реальный Dash-сервер — callback'и
в этом проекте написаны как чистые функции (принимают данные напрямую или
через несложные моки Flask-сессии/БД), поэтому их можно вызвать и
проверить результат так же, как обычную функцию. Такой подход быстрее,
детерминированнее и не требует браузерного драйвера в CI/локально — цена в
том, что реальный клиентский JS (в частности, оба `clientside_callback` —
перемотка плеера и тема, см. [Dash-дашборд](
dashboard.md#clientside-callback-pattern))
не покрыт автотестами вообще, только проверен вручную по ходу разработки.

Легаси Streamlit-дашборд (`dashboard.py`) тестировался иначе, вручную по
ходу разработки — через `streamlit.testing.v1.AppTest` (headless, реальные
клики по виджетам), но не как часть закоммиченного `tests/`-набора
проекта. Нюанс с тех сессий: `AppTest.from_file()` не добавляет корень
репозитория в `sys.path` сам по себе, если тестовый скрипт лежит вне
репозитория — нужно руками `sys.path.insert(0, <repo_root>)`, иначе
`ModuleNotFoundError`.

## WER-тестирование ASR

`scripts/compute_wer.py` — отдельный прогон вне `pytest`: транскрибирует
`test_data/*.wav` (синтетика из `generate_synthetic_calls.py`) и считает
Word Error Rate (`jiwer`) против эталонных `.txt`-транскриптов, пишет отчёт
в `test_data/wer_report.md`. Не юнит-тест в привычном смысле (не проверяет
`assert`, не падает на пороге) — измерительный инструмент качества ASR,
запускается вручную при подозрении на регрессию транскрипции (например,
смена модели Whisper). Подробнее — [Скрипты и вспомогательные утилиты](
scripts.md).
