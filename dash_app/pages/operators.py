"""Страница «Операторы» (D1.2, расширена в F1-F4).

Стиль вдохновлён dash-manufacture-spc-dashboard (Shewhart control charts):
https://github.com/plotly/dash-sample-apps/tree/main/apps/dash-manufacture-spc-dashboard
Прямая параллель: их "OOC%" (доля измерений вне контрольных пределов датчика)
— это наш "% ниже нормы" (доля звонков оператора с низкой оценкой); их
UCL/LCL (±3σ вокруг среднего процесса) — здесь «норма команды» (среднее ±1.5σ
по всем именованным звонкам), но по качеству разговора, а не показанию
датчика. dash_daq как зависимость не добавляли — GraduatedBar/Indicator/
LEDDisplay собраны на своих html.Div и уже существующих компонентах под
общую CSS-переменную темизацию (у dash_daq своя палитра, не подхватывающая
наш data-theme).

F1 — построчный обзор с мини-трендом оценки (спарклайн) и градиентной шкалой
позиции "% ниже нормы", вместо плоской ag-grid таблицы.
F2 — клик по оператору раскрывает control chart: оценка каждого звонка по
времени на фоне закрашенной полосы «норма команды», точки раскрашены по тем
же порогам 7/5, что и everywhere else в проекте (score_dot).
F3 — донат «% проблемных звонков по оператору» рядом со списком (аналог их
"% OOC per Parameter").
F4 — quick-stats шапка (операторов, средняя оценка команды, время
обновления) + автообновление раз в 90 сек (тот же паттерн dcc.Interval, что
и на странице Аналитика, E6) — выбранный оператор для drill-down не
сбрасывается при обновлении, т.к. хранится в dcc.Store, а не в состоянии
конкретных кнопок.

Drill-in по имени оператора из других страниц: любая таблица с колонкой
«Оператор» (rating.py, compliance.py «По операторам») рендерит имя как
markdown-ссылку на `/operators?op=<имя>`. show_operator_detail() читает
query-параметр из глобального dcc.Location(id="url") (объявлен один раз в
app.py, общий для всех страниц) в дополнение к клику по строке — так один
и тот же control chart открывается что по клику на этой странице, что по
ссылке с другой, без дублирования рендер-логики.
"""
from datetime import datetime
from urllib.parse import parse_qs

import dash
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from dash import ALL, Input, Output, callback, ctx, dcc, html

from dash_app.auth import get_current_department
from dash_app.colors import COLORS, CHART_FONT
from dash_app.components.cell_format import score_dot
from dash_app.components.gauge_tile import gauge_tile
from dash_app.components.page_header import page_header, section_header
from dash_app.components.stat_tile import stat_tile
from dash_app.data import load_calls

dash.register_page(__name__, path="/operators", name="Операторы", order=1)

_LOW_SCORE_THRESHOLD = 5  # тот же порог, что у score_dot(warn=5)
_BAND_SIGMA = 1.5


def _card(children, extra_style=None):
    style = {
        "background": COLORS["card_bg"],
        "borderRadius": "0.625rem",
        "padding": "1.25rem",
        "boxShadow": "0 1px 3px rgba(0,0,0,0.07), 0 4px 16px rgba(0,0,0,0.04)",
    }
    if extra_style:
        style.update(extra_style)
    return html.Div(children, style=style)


def _effective_dt(df: pd.DataFrame) -> pd.Series:
    return pd.to_datetime(df["call_datetime"]).fillna(pd.to_datetime(df["analyzed_at"]))


def _team_band(named_df: pd.DataFrame) -> tuple[float, float]:
    mean = named_df["agent_performance_score"].mean()
    std = named_df["agent_performance_score"].std() or 0.0
    return max(0.0, mean - _BAND_SIGMA * std), min(10.0, mean + _BAND_SIGMA * std)


def _load_named(department) -> tuple[pd.DataFrame, int]:
    df = load_calls(department=department)
    named_df = df[df["operator_name"].notna() & (df["operator_name"] != "")].copy()
    if not named_df.empty:
        named_df["effective_dt"] = _effective_dt(named_df)
    return named_df, len(df) - len(named_df)


# ── F1: построчный список операторов со спарклайном и шкалой ─────────────────

def _sparkline(scores: list) -> dcc.Graph:
    fig = go.Figure(go.Scatter(y=scores, mode="lines", line=dict(color=COLORS["operator"], width=2)))
    fig.update_layout(
        margin=dict(l=0, r=0, t=2, b=2), height=40,
        xaxis=dict(visible=False),
        yaxis=dict(visible=False, range=[0, 10]),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
    )
    return dcc.Graph(figure=fig, config={"displayModeBar": False, "staticPlot": True}, style={"height": "40px"})


def _graduated_bar(pct: float) -> html.Div:
    marker_left = max(0.0, min(100.0, pct))
    return html.Div(
        [
            html.Div(
                style={"display": "flex", "height": "10px", "borderRadius": "5px", "overflow": "hidden"},
                children=[
                    html.Div(style={"width": "15%", "background": COLORS["success"]}),
                    html.Div(style={"width": "15%", "background": COLORS["warning"]}),
                    html.Div(style={"width": "70%", "background": COLORS["danger"]}),
                ],
            ),
            html.Div(style={
                "position": "absolute", "left": f"{marker_left}%", "top": "-3px",
                "width": "2px", "height": "16px", "background": COLORS["text_primary"],
                "transform": "translateX(-1px)",
            }),
        ],
        style={"position": "relative", "width": "100%", "marginTop": "0.3rem"},
    )


def _row_header() -> html.Div:
    cols = [("Оператор", 2), ("Звонков", 1), ("Тренд оценки", 2), ("% ниже нормы", 2), ("Оценка", 1.3)]
    return html.Div(
        [
            html.Div(label, style={
                "flex": str(w), "fontFamily": CHART_FONT["family"], "fontSize": "0.72rem",
                "color": COLORS["text_secondary"], "textTransform": "uppercase",
                "letterSpacing": "0.06em", "fontWeight": "600",
            })
            for label, w in cols
        ],
        style={
            "display": "flex", "gap": "1rem", "alignItems": "center",
            "padding": "0 0.75rem 0.6rem", "borderBottom": f"2px solid {COLORS['border']}",
        },
    )


def _operator_row(name: str, group: pd.DataFrame) -> html.Div:
    scores_sorted = group.sort_values("effective_dt")["agent_performance_score"].tolist()
    count = len(group)
    avg_score = group["agent_performance_score"].mean()
    low_pct = (group["agent_performance_score"] < _LOW_SCORE_THRESHOLD).mean() * 100

    return html.Div(
        [
            html.Div(
                html.Button(
                    name, id={"type": "operator-row-btn", "name": name}, n_clicks=0,
                    title="Клик — детальный график по звонкам этого оператора",
                    style={
                        "background": "none", "border": "none", "padding": "0",
                        "color": COLORS["primary_bright"], "fontWeight": "600",
                        "cursor": "pointer", "fontSize": "0.9rem", "textAlign": "left",
                        "fontFamily": "inherit", "textDecoration": "underline",
                    },
                ),
                style={"flex": "2"},
            ),
            html.Div(str(count), style={"flex": "1", "color": COLORS["text_secondary"]}),
            html.Div(_sparkline(scores_sorted), style={"flex": "2"}),
            html.Div(
                [
                    html.Span(f"{low_pct:.0f}%", style={"fontVariantNumeric": "tabular-nums", "color": COLORS["text_primary"]}),
                    _graduated_bar(low_pct),
                ],
                style={"flex": "2"},
            ),
            html.Div(
                f"{score_dot(avg_score)} {avg_score:.1f}/10",
                style={"flex": "1.3", "fontWeight": "600", "fontVariantNumeric": "tabular-nums"},
            ),
        ],
        style={
            "display": "flex", "gap": "1rem", "alignItems": "center",
            "padding": "0.6rem 0.75rem", "borderBottom": f"1px solid {COLORS['border']}",
        },
    )


# ── F3: донат «% проблемных звонков по оператору» ─────────────────────────────

def _problem_donut(named_df: pd.DataFrame):
    problem_df = named_df[named_df["agent_performance_score"] < _LOW_SCORE_THRESHOLD]
    if problem_df.empty:
        return html.P(
            f"✅ Нет звонков с оценкой ниже {_LOW_SCORE_THRESHOLD}/10.",
            style={"color": COLORS["success"], "fontWeight": "500"},
        )
    counts = problem_df.groupby("operator_name").size().sort_values(ascending=False)
    fig = px.pie(values=counts.values, names=counts.index, hole=0.45)
    fig.update_traces(marker=dict(colors=px.colors.qualitative.Set2))
    fig.update_layout(
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=-0.3, font={**CHART_FONT, "size": 10}),
        margin=dict(t=10, b=10, l=0, r=0), height=280,
        paper_bgcolor="white", font=CHART_FONT,
    )
    return dcc.Graph(figure=fig, config={"displayModeBar": False})


# ── F4: quick-stats шапка ─────────────────────────────────────────────────────

def _quick_stats(named_df: pd.DataFrame) -> html.Div:
    op_count = named_df["operator_name"].nunique()
    team_avg = named_df["agent_performance_score"].mean()
    now_label = datetime.now().strftime("%H:%M")

    return html.Div(
        [
            stat_tile("Операторов", str(op_count), accent=COLORS["kpi_calls"]),
            gauge_tile("Средняя оценка команды", team_avg, good=7, warn=5, max_value=10, unit="/10", decimals=1),
            stat_tile("Обновлено", now_label, accent=COLORS["kpi_silence"]),
        ],
        style={"display": "flex", "gap": "1rem", "marginBottom": "1.5rem", "flexWrap": "wrap"},
    )


# ── F2: drill-down control chart ──────────────────────────────────────────────

def _render_detail(name: str, department: str | None):
    named_df, _ = _load_named(department)
    if named_df.empty:
        return html.P("Нет данных.", style={"color": COLORS["text_secondary"]})

    band_low, band_high = _team_band(named_df)
    op_df = named_df[named_df["operator_name"] == name].sort_values("effective_dt")
    if op_df.empty:
        return html.P(
            f"Нет звонков оператора «{name}» в текущей выборке.",
            style={"color": COLORS["text_secondary"]},
        )

    point_colors = [
        COLORS["success"] if s >= 7 else COLORS["warning"] if s >= 5 else COLORS["danger"]
        for s in op_df["agent_performance_score"]
    ]

    fig = go.Figure()
    fig.add_hrect(
        y0=band_low, y1=band_high, fillcolor="rgba(37,99,235,0.08)", line_width=0,
        annotation_text="норма команды", annotation_position="top left", annotation_font=CHART_FONT,
    )
    fig.add_trace(go.Scatter(
        x=op_df["effective_dt"], y=op_df["agent_performance_score"],
        mode="lines+markers", line=dict(color=COLORS["operator"], width=1.5),
        marker=dict(color=point_colors, size=9, line=dict(width=1, color="white")),
        name=name,
    ))
    fig.update_layout(
        yaxis=dict(range=[0, 10], title="Оценка", gridcolor="#E2E8F0"),
        xaxis=dict(gridcolor="#E2E8F0"),
        margin=dict(t=30, b=10, l=10, r=10), height=320,
        paper_bgcolor="white", plot_bgcolor="#F8FAFC", font=CHART_FONT, showlegend=False,
    )

    below_band = int((op_df["agent_performance_score"] < band_low).sum())
    note_color = COLORS["warning"] if below_band else COLORS["success"]
    note = (
        f"⚠️ {below_band} из {len(op_df)} звонков — ниже нормального диапазона команды "
        f"({band_low:.1f}–{band_high:.1f}/10)."
        if below_band else
        f"✅ Все {len(op_df)} звонков в пределах нормального диапазона команды ({band_low:.1f}–{band_high:.1f}/10)."
    )

    return _card([
        section_header(f"Динамика оценок — {name}"),
        dcc.Graph(figure=fig, config={"displayModeBar": False}),
        html.P(note, style={"color": note_color, "fontSize": "0.85rem", "marginTop": "0.5rem", "fontWeight": "500"}),
    ])


# ── layout() — статичная оболочка, содержимое приходит из callback'ов ────────

def layout(**_query_params):
    # dash.page_container передаёт query-параметры URL (?op=...) как kwargs
    # в layout() — op нам тут не нужен (читаем его позже через
    # Input("url", "search") в show_operator_detail), но сигнатура должна
    # их принимать, иначе TypeError на любой ссылке вида /operators?op=...
    named_df, unnamed_count = _load_named(get_current_department())
    if named_df.empty:
        return html.Div([
            page_header("🧑‍💼", "Операторы"),
            html.P(
                "Пока ни один звонок не привязан к оператору. "
                "Укажите имя в деталке звонка (вкладка «Звонки»).",
                style={"color": COLORS["text_secondary"]},
            ),
        ])

    return html.Div([
        page_header("🧑‍💼", "Статистика по операторам"),
        html.Div(id="operators-body"),
        dcc.Store(id="operators-selected-op"),
        html.Div(id="operators-detail-container", style={"marginTop": "1.5rem"}),
        dcc.Interval(id="operators-refresh-interval", interval=90_000, n_intervals=0),
    ])


@callback(
    Output("operators-body", "children"),
    Input("operators-refresh-interval", "n_intervals"),
)
def render_body(_n_intervals):
    named_df, unnamed_count = _load_named(get_current_department())
    if named_df.empty:
        return html.P(
            "Пока ни один звонок не привязан к оператору.",
            style={"color": COLORS["text_secondary"]},
        )

    groups = sorted(named_df.groupby("operator_name"), key=lambda kv: -len(kv[1]))
    rows = [_operator_row(name, group) for name, group in groups]

    subtitle = f"{len(named_df)} звонков привязаны к оператору"
    if unnamed_count:
        subtitle += f" · {unnamed_count} ещё без имени"

    return html.Div([
        _quick_stats(named_df),
        html.Div(
            [
                _card(
                    [_row_header(), html.Div(rows, id="operators-rows")],
                    {"flex": "2.2", "minWidth": "480px"},
                ),
                _card(
                    [section_header(f"% звонков с оценкой < {_LOW_SCORE_THRESHOLD}/10 — по операторам"), _problem_donut(named_df)],
                    {"flex": "1", "minWidth": "260px"},
                ),
            ],
            style={"display": "flex", "gap": "1rem", "flexWrap": "wrap", "alignItems": "flex-start"},
        ),
        html.P(subtitle, style={"color": COLORS["text_secondary"], "fontSize": "0.8rem", "marginTop": "0.75rem"}),
    ])


@callback(
    Output("operators-selected-op", "data"),
    Input({"type": "operator-row-btn", "name": ALL}, "n_clicks"),
    prevent_initial_call=True,
)
def select_operator(n_clicks_all):
    triggered = ctx.triggered_id
    if not triggered or not any(n_clicks_all):
        return dash.no_update
    return triggered["name"]


@callback(
    Output("operators-detail-container", "children"),
    Input("operators-selected-op", "data"),
    Input("url", "search"),
    Input("operators-refresh-interval", "n_intervals"),
)
def show_operator_detail(clicked_name, url_search, _n_intervals):
    name = clicked_name
    if not name and url_search:
        name = (parse_qs(url_search.lstrip("?")).get("op") or [None])[0]
    if not name:
        return dash.no_update
    return _render_detail(name, get_current_department())
