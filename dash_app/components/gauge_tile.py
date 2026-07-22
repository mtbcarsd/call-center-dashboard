"""Гейдж-тайл — KPI-карточка с полукруглым индикатором для %-метрик с целевым
порогом (аналог «mierniki» из референсного Power BI дашборда). Для остальных
KPI (счётчики, оценки X/10) — обычный текстовый dash_app/components/stat_tile.py.
"""
import pandas as pd
import plotly.graph_objects as go
from dash import dcc, html

from dash_app.colors import COLORS, CHART_FONT


def gauge_tile(label: str, value_pct: float, good: float = 75, warn: float = 50) -> html.Div:
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

    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=value,
        number={
            "suffix": "%" if has_value else "",
            "valueformat": ".0f",
            "font": {"size": 26, "color": COLORS["text_primary"] if has_value else COLORS["neutral"]},
        },
        gauge={
            "axis": {"range": [0, 100], "tickfont": {"size": 8}, "tickcolor": COLORS["border"]},
            "bar": {"color": color},
            "bgcolor": "#F1F5F9",
            "borderwidth": 0,
        },
    ))
    fig.update_layout(
        height=130,
        margin=dict(t=5, b=0, l=25, r=25),
        paper_bgcolor="rgba(0,0,0,0)",
        font=CHART_FONT,
    )
    if not has_value:
        fig.update_traces(number_font_color=COLORS["neutral"])

    return html.Div(
        [
            html.P(
                label,
                style={
                    "fontSize": "0.7rem",
                    "fontWeight": "700",
                    "color": COLORS["text_secondary"],
                    "textTransform": "uppercase",
                    "letterSpacing": "0.08em",
                    "margin": "0",
                },
            ),
            dcc.Graph(
                figure=fig,
                config={"displayModeBar": False},
                style={"height": "130px"},
            ),
        ],
        style={
            "background": "white",
            "borderRadius": "0.625rem",
            "padding": "0.75rem 1rem 0",
            "borderLeft": f"4px solid {color}",
            "boxShadow": "0 1px 3px rgba(0,0,0,0.07), 0 4px 16px rgba(0,0,0,0.04)",
            # flex: 0 (не растягивать) — при малом числе тайлов в ряду (напр.
            # 2 на Compliance) flex:1 растягивал карточку на пол-экрана, и
            # полукруглый go.Indicator при таком aspect ratio съезжал за рамки.
            "flex": "0 0 220px",
            "minWidth": "160px",
            "maxWidth": "260px",
        },
    )
