"""Гейдж-тайл — KPI-карточка с полукруглым индикатором для %-метрик с целевым
порогом (аналог «mierniki» из референсного Power BI дашборда). Для остальных
KPI (счётчики, оценки X/10) — обычный текстовый dash_app/components/stat_tile.py.

max_value/unit/decimals (E3) позволяют использовать тот же гейдж для метрик
не в диапазоне 0-100% (например, оценка 0-10) — нужно для «hero»-плиток на
странице Аналитика, где вместо текстового stat_tile для самых важных метрик
используется тот же визуальный язык «полукруг + порог», что и у «Решено».
size="lg" — увеличенный вариант для hero-ряда (crupнее число и сам гейдж).
"""
import pandas as pd
import plotly.graph_objects as go
from dash import dcc, html

from dash_app.colors import COLORS, CHART_FONT, FONTS

_SIZES = {
    "md": {"height": 130, "number_font": 26, "label_font": "0.68rem", "flex": "0 0 220px", "min_w": "160px", "max_w": "260px", "border": "4px"},
    "lg": {"height": 190, "number_font": 40, "label_font": "0.78rem", "flex": "1 1 260px", "min_w": "240px", "max_w": "420px", "border": "6px"},
}


def gauge_tile(
    label: str,
    value_pct: float,
    good: float = 75,
    warn: float = 50,
    delta=None,
    max_value: float = 100,
    unit: str = "%",
    decimals: int = 0,
    size: str = "md",
) -> html.Div:
    dims = _SIZES[size]
    has_value = value_pct is not None and pd.notna(value_pct)
    value = float(value_pct) if has_value else 0.0

    if not has_value:
        color = COLORS["neutral"]
    elif value >= good:
        color = COLORS["success"]
    elif value >= warn:
        color = COLORS["warning"]
    else:
        color = COLORS["danger"]

    # Plotly не умеет резолвить CSS custom properties (var(--...)) — COLORS
    # теперь на них указывает для UI-хромы (см. dash_app/colors.py), поэтому
    # здесь красим число тем же статусным accent-цветом (реальный hex), а не
    # COLORS["text_primary"] — заодно число визуально совпадает по цвету со
    # статусом гейджа. tickcolor — фиксированный нейтральный серый, читаемый
    # что на светлой, что на тёмной поверхности карточки.
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=value,
        number={
            "suffix": unit if has_value else "",
            "valueformat": f".{decimals}f",
            "font": {"size": dims["number_font"], "color": color},
        },
        gauge={
            "axis": {"range": [0, max_value], "tickfont": {"size": 8}, "tickcolor": "#94A3B8"},
            "bar": {"color": color},
            "bgcolor": "#F1F5F9",
            "borderwidth": 0,
        },
    ))
    fig.update_layout(
        height=dims["height"],
        margin=dict(t=5, b=0, l=25, r=25),
        paper_bgcolor="rgba(0,0,0,0)",
        font=CHART_FONT,
    )
    if not has_value:
        fig.update_traces(number_font_color=COLORS["neutral"])

    return html.Div(
        [
            html.Div(
                [
                    html.P(
                        label,
                        style={
                            "fontFamily": FONTS["mono"],
                            "fontSize": dims["label_font"],
                            "color": COLORS["text_secondary"],
                            "textTransform": "uppercase",
                            "letterSpacing": "0.1em",
                            "margin": "0",
                        },
                    ),
                    *([delta] if delta is not None else []),
                ],
                style={"display": "flex", "alignItems": "baseline"},
            ),
            dcc.Graph(
                figure=fig,
                config={"displayModeBar": False},
                style={"height": f"{dims['height']}px"},
            ),
        ],
        style={
            "background": COLORS["card_bg"],
            "borderRadius": "0.625rem",
            "padding": "0.75rem 1rem 0",
            "borderLeft": f"{dims['border']} solid {color}",
            "boxShadow": "0 1px 3px rgba(0,0,0,0.07), 0 4px 16px rgba(0,0,0,0.04)",
            # flex: 0 (не растягивать) — при малом числе тайлов в ряду (напр.
            # 2 на Compliance) flex:1 растягивал карточку на пол-экрана, и
            # полукруглый go.Indicator при таком aspect ratio съезжал за рамки.
            # У size="lg" (hero-ряд из 2 плиток) наоборот — растягиваем.
            "flex": dims["flex"],
            "minWidth": dims["min_w"],
            "maxWidth": dims["max_w"],
        },
    )
