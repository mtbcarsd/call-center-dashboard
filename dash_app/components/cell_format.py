"""Общие ag-grid форматтеры для %-метрик и оценок 0-10: цветной индикатор
(кружок) вместо покраски текста — единая пороговая логика вместо дублирования
по страницам (rating.py/operators.py/compliance.py/analytics.py держали
почти одинаковый _PCT_STYLE/_SCORE_STYLE каждый со своими порогами)."""
import pandas as pd


def pct_cell(good: float = 75, warn: float = 50) -> dict:
    """Колонка columnDef для % (выше — лучше): 🟢/🟠/🔴 + число."""
    return {
        "valueFormatter": {
            "function": (
                "params.value == null ? '—' : "
                f"(params.value >= {good} ? '🟢' : params.value >= {warn} ? '🟠' : '🔴') "
                "+ ' ' + params.value.toFixed(0) + '%'"
            )
        },
    }


def score_cell(good: float = 7, warn: float = 5) -> dict:
    """Колонка columnDef для оценок 0-10 (выше — лучше): 🟢/🟠/🔴 + число."""
    return {
        "valueFormatter": {
            "function": (
                "params.value == null ? '—' : "
                f"(params.value >= {good} ? '🟢' : params.value >= {warn} ? '🟠' : '🔴') "
                "+ ' ' + Number(params.value).toFixed(1) + '/10'"
            )
        },
    }


def score_dot(value, good: float = 7, warn: float = 5) -> str:
    """Тот же 🟢/🟠/🔴, но как чистая Python-функция — для карточек вне ag-grid
    (например, галерея звонков), где нет JS-рантайма для valueFormatter."""
    if value is None:
        return "⚪"
    try:
        if pd.isna(value):
            return "⚪"
    except TypeError:
        pass
    if value >= good:
        return "🟢"
    if value >= warn:
        return "🟠"
    return "🔴"
