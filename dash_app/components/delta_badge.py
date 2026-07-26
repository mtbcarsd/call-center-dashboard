"""Бейдж изменения метрики к предыдущему периоду (E2 — сравнение периодов).

Используется в stat_tile/gauge_tile на странице Аналитика: показывает
дельту к предыдущему периоду той же длины. Отсутствие данных за предыдущий
период (например, выбрано «Всё время» или начало сбора данных) — не ошибка,
а обычный случай, поэтому просто ничего не рендерим (return None), а не
пишем «н/д».
"""
import pandas as pd
from dash import html

from dash_app.colors import COLORS


def delta_badge(
    delta: float | None,
    unit: str = "",
    up_is_good: bool | None = True,
    decimals: int = 1,
) -> html.Span | None:
    if delta is None or pd.isna(delta):
        return None

    threshold = 10 ** (-decimals) / 2
    if abs(delta) < threshold:
        # Округляется до нуля на выбранной точности — не показываем знак,
        # иначе крошечная отрицательная дельта рендерится как «-0.0».
        arrow, color = "→", COLORS["text_secondary"]
        text = f" {arrow} {abs(delta):.{decimals}f}{unit}"
    else:
        is_up = delta > 0
        arrow = "▲" if is_up else "▼"
        color = COLORS["text_secondary"] if up_is_good is None else (
            COLORS["success"] if (is_up == up_is_good) else COLORS["danger"]
        )
        sign = "+" if is_up else ""
        text = f" {arrow} {sign}{delta:.{decimals}f}{unit}"

    return html.Span(
        text,
        style={
            "color": color,
            "fontSize": "0.78rem",
            "fontWeight": "600",
            "marginLeft": "0.35rem",
            "whiteSpace": "nowrap",
        },
    )
