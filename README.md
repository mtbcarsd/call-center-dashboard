# 📞 Call Center Analytics Dashboard

Система аналитики звонков колл-центра банка на основе локальной транскрипции и LLM-анализа с визуализацией в Streamlit.

## Стек технологий

| Компонент | Технология |
|-----------|-----------|
| Транскрипция | faster-whisper (medium, CPU) |
| LLM-анализ | ollama · qwen2.5-coder:7b |
| Хранилище | локальная SQLite-база (`call_center.db`) |
| Дашборд | Streamlit + Plotly |
| Деплой | Railway |

## Архитектура pipeline

```
WAV-файлы (локально)
      ↓  faster-whisper medium
Транскрипты (русский текст)
      ↓  ollama / qwen2.5-coder:7b
Анализ: тип, намерение, срочность, оценки, резюме
      ↓  sqlite3 (db.py)
call_center.db: ai_transcribed_calls + call_analysis
      ↓
Streamlit Dashboard
```

Ранее хранилищем был облачный Snowflake — отказались от него в пользу локальной SQLite-базы (без внешних зависимостей, паролей и облачных лимитов).

## Структура проекта

```
call_center_dashboard/
├── audio_original_data/       # Исходные WAV-файлы
│   ├── ОО/                    # Отдел обслуживания (5 звонков)
│   └── ОРККиП/                # Отдел РКК и П (5 звонков)
├── db.py                      # Схема и подключение к локальной SQLite-базе
├── dashboard.py               # Streamlit-дашборд
├── pipeline.py                # Pipeline: транскрипция → анализ → call_center.db
├── upload_from_cache.py       # Догрузка results_cache.json в базу без пересчёта
├── call_center.db             # Локальная SQLite-база (не в git)
├── requirements.txt           # Зависимости для Railway
├── railway.toml               # Конфигурация деплоя
└── .streamlit/
    └── config.toml            # Настройки Streamlit
```

## База данных (SQLite)

Файл `call_center.db` создаётся и заполняется схемой автоматически при первом подключении (см. `db.py`). Таблицы:
- `ai_transcribed_calls` — транскрипты, язык, длительность
- `call_analysis` — полная аналитика: тип, намерение, срочность, оценки, резюме, топики

## Дашборд

**URL:** https://call-center-dashboard-production-6a6b.up.railway.app

**Логин:** Julia / Julia

### Функциональность

- **Аналитика** — KPI-карточки, графики оценок, диаграмма срочности, сравнение отделов
- **Таблица звонков** — фильтры по отделу, срочности, статусу; прогресс-бары оценок
- **Детали звонка** — параметры, резюме, полный транскрипт
- **Команда** — карточка проекта и участники команды

## Запуск pipeline локально

```bash
# Активировать окружение
source .venv/bin/activate

# Убедиться что ollama запущен с моделью qwen2.5-coder:7b
ollama serve &
ollama pull qwen2.5-coder:7b

# Запустить pipeline
python pipeline.py
```

## Запуск дашборда локально

```bash
source .venv/bin/activate
streamlit run dashboard.py
# → http://localhost:8501
```

## Переменные окружения

Не требуются — локальная SQLite-база не нуждается в credentials.

⚠️ Если дашборд деплоится на Railway (эфемерная файловая система), `call_center.db` нужно либо подключать через Railway Volume, либо заново прогонять `python pipeline.py` / `python upload_from_cache.py` при каждом деплое — иначе база будет пустой после рестарта контейнера.

## Команда

**ЦАР · ds-team, sandbox — МТБанк, Беларусь**

- 👩‍🏫 Воспитатель: Пилипенко Светлана
- 🤱 Нянечка: Гуринович Анастасия
- 🔬 Data Scientist: Масловская Ксения
- 🔬 Data Scientist: Дымков Алексей
- 🔬 Data Scientist: Шилкин Андрей
