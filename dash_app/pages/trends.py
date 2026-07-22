"""Страница «Тренды» — LLM-агент через GET /trends (D1.2).

Эквивалент вкладки «📈 Тренды» (dashboard.py:845-881).
Кнопка «Получить тренды» + изменение url-pathname — оба вызывают callback.
"""
import os

import dash
import requests
from dash import html, dcc, callback, Input, Output, State

from dash_app.colors import COLORS
from dash_app.data import load_calls
from dash_app.trends_logic import render_trends_result

dash.register_page(__name__, path="/trends", name="Тренды", order=4)

_API_BASE = os.environ.get("API_BASE_URL", "https://api-production-95c7e.up.railway.app")


# ── Layout ────────────────────────────────────────────────────────────────────

def layout():
    df = load_calls()
    max_limit = max(len(df), 1)

    return html.Div([
        html.H2(
            "📈 Тренды",
            style={"color": COLORS["text_primary"], "margin": "0 0 0.25rem 0", "fontWeight": "700"},
        ),
        html.P(
            "LLM-агент анализирует резюме и темы последних звонков, ищет повторяющиеся паттерны "
            "и узкие места. Запрос идёт к сервису api (LLM — Groq).",
            style={"color": COLORS["text_secondary"], "margin": "0 0 1.5rem 0", "fontSize": "0.875rem"},
        ),
        html.Div(
            [
                html.Div(
                    [
                        html.Label(
                            "Сколько последних звонков анализировать:",
                            style={
                                "fontWeight": "600",
                                "color": COLORS["text_primary"],
                                "display": "block",
                                "marginBottom": "0.5rem",
                                "fontSize": "0.875rem",
                            },
                        ),
                        dcc.Slider(
                            id="trends-limit-slider",
                            min=1,
                            max=max_limit,
                            value=min(10, max_limit),
                            step=1,
                            marks={
                                i: str(i)
                                for i in range(1, max_limit + 1, max(1, max_limit // 5))
                            },
                            tooltip={"placement": "bottom", "always_visible": True},
                        ),
                    ],
                    style={"flex": "1"},
                ),
                html.Button(
                    "🔄 Получить тренды",
                    id="trends-refresh-btn",
                    n_clicks=0,
                    style={
                        "background": COLORS["primary_bright"],
                        "color": "white",
                        "border": "none",
                        "borderRadius": "0.5rem",
                        "padding": "0.625rem 1.25rem",
                        "fontWeight": "600",
                        "cursor": "pointer",
                        "fontSize": "0.875rem",
                        "alignSelf": "flex-end",
                        "minWidth": "160px",
                        "fontFamily": "inherit",
                    },
                ),
            ],
            style={
                "display": "flex",
                "gap": "1.5rem",
                "alignItems": "flex-end",
                "marginBottom": "1.5rem",
                "background": "white",
                "padding": "1.25rem",
                "borderRadius": "0.625rem",
                "boxShadow": "0 1px 3px rgba(0,0,0,0.07)",
            },
        ),
        dcc.Loading(
            html.Div(id="trends-result-container"),
            type="dot",
            color=COLORS["primary_bright"],
        ),
    ])


# ── Callback ──────────────────────────────────────────────────────────────────

@callback(
    Output("trends-result-container", "children"),
    Input("url", "pathname"),
    Input("trends-refresh-btn", "n_clicks"),
    State("trends-limit-slider", "value"),
    prevent_initial_call=False,
)
def fetch_and_display_trends(pathname, n_clicks, limit):
    if (pathname or "/") != "/trends":
        return dash.no_update
    limit = limit or 10
    try:
        resp = requests.get(f"{_API_BASE}/trends", params={"limit": limit}, timeout=30)
        resp.raise_for_status()
        result = resp.json()
    except requests.RequestException as e:
        return render_trends_result(None, str(e))
    return render_trends_result(result, None)
