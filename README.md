# 📞 Call Center Analytics Dashboard

Система аналитики звонков колл-центра банка на основе локальной транскрипции и LLM-анализа с визуализацией в Streamlit.

## Стек технологий

| Компонент | Технология |
|-----------|-----------|
| Транскрипция | faster-whisper (medium, CPU) |
| LLM-анализ | ollama · qwen2.5-coder:7b |
| Хранилище | Snowflake (CALL_CENTER_DB) |
| Дашборд | Streamlit + Plotly |
| Деплой | Railway |

## Архитектура pipeline

```
WAV-файлы (локально)
      ↓  faster-whisper medium
Транскрипты (русский текст)
      ↓  ollama / qwen2.5-coder:7b
Анализ: тип, намерение, срочность, оценки, резюме
      ↓  snowflake-connector-python
Snowflake: AI_TRANSCRIBED_CALLS + CALL_ANALYSIS
      ↓
Streamlit Dashboard (Railway)
```

## Структура проекта

```
call_center_dashboard/
├── audio_original_data/       # Исходные WAV-файлы
│   ├── ОО/                    # Отдел обслуживания (5 звонков)
│   └── ОРККиП/                # Отдел РКК и П (5 звонков)
├── dashboard.py               # Streamlit-дашборд
├── pipeline.py                # Pipeline: транскрипция → анализ → Snowflake
├── requirements.txt           # Зависимости для Railway
├── railway.toml               # Конфигурация деплоя
└── .streamlit/
    └── config.toml            # Настройки Streamlit
```

## Snowflake-объекты

- **Database:** `CALL_CENTER_DB`
- **Schema:** `ANALYTICS`
- **Warehouse:** `CCA_WH` (X-Small, auto-suspend 120s)
- **Stage:** `@AUDIO_FILES` — WAV-файлы (10 шт.)
- **Tables:**
  - `AI_TRANSCRIBED_CALLS` — транскрипты, язык, длительность
  - `CALL_ANALYSIS` — полная аналитика: тип, намерение, срочность, оценки, резюме, топики

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

## Переменные окружения (Railway)

| Переменная | Описание |
|-----------|---------|
| `SF_ACCOUNT` | Snowflake account identifier |
| `SF_USER` | Имя пользователя |
| `SF_PASSWORD` | Пароль |
| `SF_ROLE` | Роль (ACCOUNTADMIN) |
| `SF_WAREHOUSE` | Warehouse (CCA_WH) |
| `SF_DATABASE` | Database (CALL_CENTER_DB) |
| `SF_SCHEMA` | Schema (ANALYTICS) |

## Команда

**ЦАР · ds-team, sandbox — МТБанк, Беларусь**

- 👩‍🏫 Воспитатель: Пилипенко Светлана
- 🤱 Нянечка: Гуринович Анастасия
- 🔬 Data Scientist: Масловская Ксения
- 🔬 Data Scientist: Дымков Алексей
- 🔬 Data Scientist: Шилкин Андрей
