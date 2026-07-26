"""Страница «Аналитика» — директорский обзор (D1.1, расширена в E1/E2).

E1 — тренды по дням (оценки, % решено, объём звонков), E2 — фильтр периода
(DatePickerRange + пресеты) со сравнением к предыдущему периоду той же
длины на KPI-плитках. Раньше страница показывала только статичный агрегат
«за всё время» — без временной динамики директор не мог увидеть, что
метрика просела за последнюю неделю, только общий срез.

Паттерн: layout() рендерит статичную оболочку (шапка, фильтр периода,
пустой контейнер), @callback перерисовывает контейнер при смене диапазона
дат — тот же приём, что и в pages/calls.py (galleries/render_gallery).
"""
from datetime import date, timedelta

import dash
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import dash_ag_grid as dag
from dash import Input, Output, callback, ctx, dcc, html

from dash_app.auth import get_current_department
from dash_app.colors import COLORS, CHART_FONT
from dash_app.components.cell_format import score_cell
from dash_app.components.delta_badge import delta_badge
from dash_app.components.gauge_tile import gauge_tile
from dash_app.components.page_header import page_header, section_header
from dash_app.components.stat_tile import stat_tile
from dash_app.data import load_calls, parse_checklist, checklist_pass_rates

dash.register_page(__name__, path="/", name="Аналитика", order=0)

_RESOLVED_GOOD, _RESOLVED_WARN = 70, 50

# ── Стили ag-grid ────────────────────────────────────────────────────────────

_URGENCY_CELL_STYLE = {
    "styleConditions": [
        {"condition": "params.value === 'high'", "style": {"color": "#B91C1C", "fontWeight": "600"}},
        {"condition": "params.value === 'medium'", "style": {"color": "#D97706", "fontWeight": "600"}},
        {"condition": "params.value === 'low'", "style": {"color": "#15803D", "fontWeight": "600"}},
    ]
}

_PRESET_BTN_STYLE = {
    "background": COLORS["card_bg"],
    "color": COLORS["text_secondary"],
    "border": f"1.5px solid {COLORS['border']}",
    "borderRadius": "0.5rem",
    "padding": "0.4rem 0.9rem",
    "fontWeight": "600",
    "fontSize": "0.8rem",
    "cursor": "pointer",
    "fontFamily": "inherit",
}


# ── Вспомогательные компоненты ───────────────────────────────────────────────

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


def _with_effective_date(df: pd.DataFrame) -> pd.DataFrame:
    """call_datetime появился не с первого дня проекта — часть старых звонков
    имеет только analyzed_at. COALESCE на уровне SQL уже используется для
    сортировки в load_calls(); здесь та же логика нужна как отдельная
    колонка, чтобы фильтровать/группировать по дате в Pandas."""
    df = df.copy()
    df["effective_dt"] = pd.to_datetime(df["call_datetime"]).fillna(pd.to_datetime(df["analyzed_at"]))
    return df


def _period_kpis(df: pd.DataFrame) -> dict:
    if df.empty:
        return {"count": 0, "agent": float("nan"), "client": float("nan"),
                "resolved_pct": float("nan"), "escalated": 0, "silence": float("nan")}
    return {
        "count": len(df),
        "agent": df["agent_performance_score"].mean(),
        "client": df["customer_satisfaction"].mean(),
        "resolved_pct": (df["resolution_status"] == "resolved").mean() * 100,
        "escalated": int(df["escalation_flag"].sum()),
        "silence": df["silence_pct"].mean(),
    }


def _delta(now: float, prev: float) -> float | None:
    if pd.isna(now) or pd.isna(prev):
        return None
    return now - prev


_ALERT_ICON = {"danger": "🔴", "warning": "🟠"}


def _render_alerts(cur_df: pd.DataFrame, cur: dict, prev: dict):
    """E5 — проактивные алерты без LLM: дешёвые пороговые эвристики поверх
    уже посчитанных cur/prev агрегатов, чтобы директор видел «что не так» на
    самом видном месте, а не только когда сам полезет смотреть графики.
    Отдельно от agents/trends.py (LLM-анализ паттернов по кнопке на
    странице «Тренды») — это разные уровни: здесь просто пороги на
    цифрах, там — содержательный разбор текста разговоров."""
    alerts = []

    resolved_delta = _delta(cur["resolved_pct"], prev["resolved_pct"])
    if resolved_delta is not None and resolved_delta <= -10:
        alerts.append(("danger", (
            f"% решено упал на {abs(resolved_delta):.0f} п.п. к предыдущему периоду "
            f"({prev['resolved_pct']:.0f}% → {cur['resolved_pct']:.0f}%)."
        )))

    agent_delta = _delta(cur["agent"], prev["agent"])
    if agent_delta is not None and prev["agent"] > 0 and (agent_delta / prev["agent"]) <= -0.15:
        alerts.append(("danger", (
            f"Оценка оператора просела на {abs(agent_delta):.1f} балла к предыдущему периоду "
            f"({prev['agent']:.1f}/10 → {cur['agent']:.1f}/10)."
        )))

    cur_esc_rate = (cur["escalated"] / cur["count"] * 100) if cur["count"] else None
    prev_esc_rate = (prev["escalated"] / prev["count"] * 100) if prev["count"] else None
    if cur_esc_rate is not None and prev_esc_rate is not None and (cur_esc_rate - prev_esc_rate) >= 5:
        alerts.append(("warning", (
            f"Доля эскалаций выросла с {prev_esc_rate:.0f}% до {cur_esc_rate:.0f}% звонков "
            f"к предыдущему периоду."
        )))

    all_checklists = [c for c in cur_df["checklist_json"].apply(parse_checklist) if c]
    if all_checklists:
        rates = {k: v for k, v in checklist_pass_rates(all_checklists).items() if v is not None}
        if rates:
            worst_label, worst_rate = min(rates.items(), key=lambda kv: kv[1])
            if worst_rate < 50:
                alerts.append(("warning", (
                    f"Худший пункт чек-листа за период — «{worst_label}»: "
                    f"проходит только {worst_rate:.0f}% звонков."
                )))

    if not alerts:
        return _card(
            html.P(
                "✅ Явных проблем за выбранный период не обнаружено.",
                style={"color": COLORS["success"], "fontWeight": "500", "margin": "0"},
            ),
            {"marginBottom": "1.5rem"},
        )

    rows = [
        html.Div(
            [html.Span(_ALERT_ICON[level], style={"marginRight": "0.6rem"}), text],
            style={
                "padding": "0.5rem 0", "color": COLORS["text_primary"],
                "borderBottom": f"1px solid {COLORS['border']}",
            },
        )
        for level, text in alerts
    ]
    return _card(
        [section_header("Что требует внимания"), *rows],
        {"marginBottom": "1.5rem"},
    )


_MIN_CALLS_FOR_LEADERBOARD = 3


def _medal(rank: int) -> str:
    return {0: "🥇", 1: "🥈", 2: "🥉"}.get(rank, "▪️")


def _leaderboard_card(df: pd.DataFrame):
    """E4 — топ/анти-топ операторов прямо на главном экране (за выбранный
    период), без перехода на отдельную страницу «Операторы». Минимум 3
    звонка за период — иначе один звонок выталкивает оператора в топ/антитоп
    без статистической значимости."""
    named = df[df["operator_name"].notna() & (df["operator_name"] != "")]
    stats = named.groupby("operator_name").agg(
        Звонков=("file_name", "count"),
        Оценка=("agent_performance_score", "mean"),
    ).reset_index()
    stats = stats[stats["Звонков"] >= _MIN_CALLS_FOR_LEADERBOARD]
    if stats.empty:
        return None

    top = stats.sort_values("Оценка", ascending=False).head(3)
    bottom = stats.sort_values("Оценка", ascending=True).head(3)

    def _rows(rows_df, medals):
        items = []
        for rank, (_, row) in enumerate(rows_df.iterrows()):
            items.append(html.Div(
                [
                    html.Span(_medal(rank) if medals else "⚠️", style={"marginRight": "0.5rem"}),
                    html.Span(row["operator_name"], style={"flex": "1", "color": COLORS["text_primary"]}),
                    html.Span(f"{row['Оценка']:.1f}/10", style={"fontWeight": "700", "fontVariantNumeric": "tabular-nums"}),
                    html.Span(f" · {int(row['Звонков'])} зв.", style={"color": COLORS["text_secondary"], "fontSize": "0.78rem", "marginLeft": "0.3rem"}),
                ],
                style={
                    "display": "flex", "alignItems": "center",
                    "padding": "0.4rem 0", "borderBottom": f"1px solid {COLORS['border']}",
                },
            ))
        return items

    return _card(
        [
            html.Div(
                [
                    section_header("Лидерборд за период"),
                    dcc.Link(
                        "Все операторы →", href="/operators",
                        style={"fontSize": "0.8rem", "color": COLORS["primary_bright"], "textDecoration": "none"},
                    ),
                ],
                style={"display": "flex", "justifyContent": "space-between", "alignItems": "baseline"},
            ),
            html.Div(
                [
                    html.Div(
                        [
                            html.P("Топ-3", style={"fontWeight": "700", "marginBottom": "0.5rem", "color": COLORS["success"]}),
                            *_rows(top, medals=True),
                        ],
                        style={"flex": "1", "minWidth": "260px"},
                    ),
                    html.Div(
                        [
                            html.P("Требует внимания", style={"fontWeight": "700", "marginBottom": "0.5rem", "color": COLORS["danger"]}),
                            *_rows(bottom, medals=False),
                        ],
                        style={"flex": "1", "minWidth": "260px"},
                    ),
                ],
                style={"display": "flex", "gap": "2rem", "flexWrap": "wrap", "marginTop": "0.5rem"},
            ),
        ],
        {"marginBottom": "1.5rem"},
    )


# ── layout() — статичная оболочка, содержимое приходит из callback'а ─────────

def layout():
    df = _with_effective_date(load_calls(department=get_current_department()))

    if not df.empty:
        min_allowed = df["effective_dt"].min().date()
        max_allowed = max(df["effective_dt"].max().date(), date.today())
    else:
        min_allowed = date.today() - timedelta(days=90)
        max_allowed = date.today()

    default_end = date.today()
    default_start = default_end - timedelta(days=29)

    filter_bar = html.Div(
        [
            dcc.DatePickerRange(
                id="analytics-date-range",
                min_date_allowed=min_allowed,
                max_date_allowed=max_allowed,
                start_date=default_start,
                end_date=default_end,
                display_format="DD.MM.YYYY",
            ),
            html.Div(
                [
                    html.Button("7 дней", id="analytics-preset-7", n_clicks=0, style=_PRESET_BTN_STYLE),
                    html.Button("30 дней", id="analytics-preset-30", n_clicks=0, style=_PRESET_BTN_STYLE),
                    html.Button("90 дней", id="analytics-preset-90", n_clicks=0, style=_PRESET_BTN_STYLE),
                    html.Button("Всё время", id="analytics-preset-all", n_clicks=0, style=_PRESET_BTN_STYLE),
                ],
                style={"display": "flex", "gap": "0.5rem", "flexWrap": "wrap"},
            ),
        ],
        style={
            "display": "flex", "alignItems": "center", "gap": "1rem",
            "flexWrap": "wrap", "marginBottom": "1.5rem",
        },
    )

    return html.Div([
        page_header("📊", "Аналитика колл-центра", f"{len(df)} звонков в базе всего"),
        filter_bar,
        html.Div(id="analytics-body"),
        dcc.Store(id="analytics-min-date", data=min_allowed.isoformat()),
        dcc.Store(id="analytics-max-date", data=max_allowed.isoformat()),
        # E6 — автообновление: директор может держать вкладку открытой часами,
        # цифры не должны застывать на моменте открытия страницы.
        dcc.Interval(id="analytics-refresh-interval", interval=90_000, n_intervals=0),
    ])


# ── Пресеты периода ───────────────────────────────────────────────────────────

@callback(
    Output("analytics-date-range", "start_date"),
    Output("analytics-date-range", "end_date"),
    Input("analytics-preset-7", "n_clicks"),
    Input("analytics-preset-30", "n_clicks"),
    Input("analytics-preset-90", "n_clicks"),
    Input("analytics-preset-all", "n_clicks"),
    Input("analytics-min-date", "data"),
    Input("analytics-max-date", "data"),
    prevent_initial_call=True,
)
def apply_preset(_n7, _n30, _n90, _nall, min_date, max_date):
    triggered = ctx.triggered_id
    if triggered not in {"analytics-preset-7", "analytics-preset-30", "analytics-preset-90", "analytics-preset-all"}:
        return dash.no_update, dash.no_update

    today = date.today()
    if triggered == "analytics-preset-7":
        return today - timedelta(days=6), today
    if triggered == "analytics-preset-30":
        return today - timedelta(days=29), today
    if triggered == "analytics-preset-90":
        return today - timedelta(days=89), today
    # "Всё время"
    return date.fromisoformat(min_date), date.fromisoformat(max_date)


# ── Основной рендер, зависящий от выбранного периода ─────────────────────────

@callback(
    Output("analytics-body", "children"),
    Input("analytics-date-range", "start_date"),
    Input("analytics-date-range", "end_date"),
    Input("analytics-refresh-interval", "n_intervals"),
)
def render_body(start_date, end_date, _n_intervals):
    df = _with_effective_date(load_calls(department=get_current_department()))
    if not start_date or not end_date:
        return html.P("Выберите период.", style={"color": COLORS["text_secondary"]})

    start = pd.Timestamp(start_date)
    end = pd.Timestamp(end_date) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
    period_len = end - start

    cur_df = df[(df["effective_dt"] >= start) & (df["effective_dt"] <= end)]
    prev_start = start - period_len - pd.Timedelta(seconds=1)
    prev_end = start - pd.Timedelta(seconds=1)
    prev_df = df[(df["effective_dt"] >= prev_start) & (df["effective_dt"] <= prev_end)]

    cur = _period_kpis(cur_df)
    prev = _period_kpis(prev_df)

    if cur_df.empty:
        return html.Div([
            html.P(
                "Нет звонков за выбранный период.",
                style={"color": COLORS["text_secondary"], "marginBottom": "1.5rem"},
            ),
        ])

    # ── E3: hero-ряд — две метрики, которые директору важно увидеть первыми ──
    # (% решено и оценка оператора), крупнее и с тем же визуальным языком
    # «полукруг + цветовой порог», что и раньше был только у «Решено».
    # Остальные 4 KPI — вторым, более компактным рядом (как и раньше).
    hero_row = html.Div(
        [
            gauge_tile(
                "Оценка оператора", cur["agent"], good=7, warn=5,
                max_value=10, unit="/10", decimals=1, size="lg",
                delta=delta_badge(_delta(cur["agent"], prev["agent"]), up_is_good=True, decimals=1),
            ),
            gauge_tile(
                "Решено", cur["resolved_pct"] if cur_df.shape[0] else None,
                good=_RESOLVED_GOOD, warn=_RESOLVED_WARN, unit="%", size="lg",
                delta=delta_badge(_delta(cur["resolved_pct"], prev["resolved_pct"]), unit="%", up_is_good=True, decimals=1),
            ),
        ],
        style={"display": "flex", "gap": "1rem", "marginBottom": "1rem", "flexWrap": "wrap"},
    )

    kpi_row = html.Div(
        [
            stat_tile(
                "Звонков", str(cur["count"]), accent=COLORS["kpi_calls"],
                delta=delta_badge(_delta(cur["count"], prev["count"]), up_is_good=None, decimals=0),
            ),
            stat_tile(
                "Удовл. клиента",
                f"{cur['client']:.1f}/10" if pd.notna(cur["client"]) else "—",
                accent=COLORS["kpi_client"],
                delta=delta_badge(_delta(cur["client"], prev["client"]), up_is_good=True, decimals=1),
            ),
            stat_tile(
                "Эскалаций", str(cur["escalated"]), accent=COLORS["kpi_escalated"],
                delta=delta_badge(_delta(cur["escalated"], prev["escalated"]), up_is_good=False, decimals=0),
            ),
            stat_tile(
                "Тишина в диалоге",
                f"{cur['silence']:.0f}%" if pd.notna(cur["silence"]) else "—",
                accent=COLORS["kpi_silence"],
                delta=delta_badge(_delta(cur["silence"], prev["silence"]), unit="%", up_is_good=False, decimals=1),
            ),
        ],
        style={"display": "flex", "gap": "1rem", "marginBottom": "0.75rem", "flexWrap": "wrap"},
    )

    prev_label = None
    if not prev_df.empty:
        prev_label = html.P(
            f"Сравнение с предыдущим периодом ({prev_start.date()} — {prev_end.date()}, {len(prev_df)} звонков)",
            style={"color": COLORS["text_secondary"], "fontSize": "0.8rem", "marginBottom": "1.5rem"},
        )

    alerts_row = _render_alerts(cur_df, cur, prev)

    # ── E4: лидерборд за период — топ/анти-топ прямо на главном экране, ──────
    # без перехода на отдельную страницу «Операторы». Требуем минимум 3
    # звонка за период — иначе один удачный/неудачный звонок выталкивает
    # оператора в топ или анти-топ без статистической значимости.
    leaderboard_row = _leaderboard_card(cur_df)

    # ── E1: тренды по дням ────────────────────────────────────────────────────
    daily = cur_df.assign(day=cur_df["effective_dt"].dt.date).groupby("day").agg(
        Оператор=("agent_performance_score", "mean"),
        Клиент=("customer_satisfaction", "mean"),
        Решено=("resolution_status", lambda s: (s == "resolved").mean() * 100),
        Звонков=("file_name", "count"),
    ).reset_index().sort_values("day")
    daily["Оператор_roll"] = daily["Оператор"].rolling(7, min_periods=1).mean()
    daily["Клиент_roll"] = daily["Клиент"].rolling(7, min_periods=1).mean()
    daily["Решено_roll"] = daily["Решено"].rolling(7, min_periods=1).mean()

    fig_scores_trend = go.Figure()
    fig_scores_trend.add_trace(go.Scatter(
        x=daily["day"], y=daily["Оператор_roll"], name="Оператор", mode="lines",
        line=dict(color=COLORS["operator"], width=3),
    ))
    fig_scores_trend.add_trace(go.Scatter(
        x=daily["day"], y=daily["Клиент_roll"], name="Клиент", mode="lines",
        line=dict(color=COLORS["client"], width=3),
    ))
    fig_scores_trend.update_layout(
        yaxis=dict(range=[0, 10], title="Оценка (7-дн. среднее)", gridcolor="#E2E8F0"),
        xaxis=dict(gridcolor="#E2E8F0"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, font=CHART_FONT),
        margin=dict(t=10, b=0, l=10, r=10), height=260,
        paper_bgcolor="white", plot_bgcolor="#F8FAFC", font=CHART_FONT,
    )

    fig_resolved_trend = go.Figure()
    fig_resolved_trend.add_trace(go.Scatter(
        x=daily["day"], y=daily["Решено_roll"], name="Решено, %", mode="lines",
        line=dict(color=COLORS["success"], width=3), fill="tozeroy",
        fillcolor="rgba(21,128,61,0.08)",
    ))
    fig_resolved_trend.add_hline(
        y=_RESOLVED_GOOD, line_dash="dash", line_color=COLORS["neutral"],
        annotation_text="цель", annotation_font=CHART_FONT,
    )
    fig_resolved_trend.update_layout(
        yaxis=dict(range=[0, 100], title="% решено (7-дн. среднее)", gridcolor="#E2E8F0"),
        xaxis=dict(gridcolor="#E2E8F0"),
        margin=dict(t=10, b=0, l=10, r=10), height=260,
        paper_bgcolor="white", plot_bgcolor="#F8FAFC", font=CHART_FONT,
    )

    fig_volume_trend = go.Figure()
    fig_volume_trend.add_trace(go.Bar(
        x=daily["day"], y=daily["Звонков"], marker_color=COLORS["primary_bright"],
    ))
    fig_volume_trend.update_layout(
        yaxis=dict(title="Звонков", gridcolor="#E2E8F0"),
        xaxis=dict(gridcolor="#E2E8F0"),
        margin=dict(t=10, b=0, l=10, r=10), height=260,
        paper_bgcolor="white", plot_bgcolor="#F8FAFC", font=CHART_FONT,
    )

    trend_row = html.Div(
        [
            _card([section_header("Оценки — по дням"), dcc.Graph(figure=fig_scores_trend, config={"displayModeBar": False})], {"flex": "1", "minWidth": "280px"}),
            _card([section_header("% решено — по дням"), dcc.Graph(figure=fig_resolved_trend, config={"displayModeBar": False})], {"flex": "1", "minWidth": "280px"}),
            _card([section_header("Объём звонков — по дням"), dcc.Graph(figure=fig_volume_trend, config={"displayModeBar": False})], {"flex": "1", "minWidth": "280px"}),
        ],
        style={"display": "flex", "gap": "1rem", "marginBottom": "1.5rem", "flexWrap": "wrap"},
    )

    # ── Темы, срочность, отделы — на выбранном периоде ────────────────────────
    topic_stats = cur_df.groupby("call_topic").agg(
        Оператор=("agent_performance_score", "mean"),
        Клиент=("customer_satisfaction", "mean"),
        Звонков=("call_topic", "count"),
    ).round(1).sort_values("Звонков", ascending=False)

    fig_scores = go.Figure()
    fig_scores.add_trace(go.Bar(name="Оператор", x=topic_stats.index, y=topic_stats["Оператор"], marker_color=COLORS["operator"]))
    fig_scores.add_trace(go.Bar(name="Клиент", x=topic_stats.index, y=topic_stats["Клиент"], marker_color=COLORS["client"]))
    fig_scores.update_layout(
        barmode="group",
        yaxis=dict(range=[0, 10], title="Оценка", gridcolor="#E2E8F0"),
        xaxis=dict(tickangle=-30, gridcolor="#E2E8F0"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, font=CHART_FONT),
        margin=dict(t=10, b=0, l=10, r=10), height=300,
        paper_bgcolor="white", plot_bgcolor="#F8FAFC", font=CHART_FONT,
    )

    color_map = {"low": COLORS["urgency_low"], "medium": COLORS["urgency_medium"], "high": COLORS["urgency_high"]}
    urgency_counts = cur_df["urgency"].value_counts()
    fig_urg = px.pie(
        values=urgency_counts.values, names=urgency_counts.index,
        color=urgency_counts.index, color_discrete_map=color_map, hole=0.45,
    )
    fig_urg.update_layout(
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=-0.2, font=CHART_FONT),
        margin=dict(t=10, b=10, l=0, r=0), height=300,
        paper_bgcolor="white", font=CHART_FONT,
    )

    dept_stats = cur_df.groupby("department").agg(
        Звонков=("call_topic", "count"),
        Оператор=("agent_performance_score", "mean"),
        Клиент=("customer_satisfaction", "mean"),
    ).round(1).reset_index()
    dept_stats.columns = ["Отдел", "Звонков", "Оператор", "Клиент"]

    dept_grid = dag.AgGrid(
        rowData=dept_stats.to_dict("records"),
        columnDefs=[
            {"headerName": "Отдел", "field": "Отдел", "flex": 2},
            {"headerName": "Звонков", "field": "Звонков", "flex": 1},
            {"headerName": "Оператор", "field": "Оператор", "flex": 1, **score_cell()},
            {"headerName": "Клиент", "field": "Клиент", "flex": 1, **score_cell()},
        ],
        defaultColDef={"sortable": True},
        style={"height": f"{min(len(dept_stats) * 42 + 52, 180)}px"},
        className="ag-theme-alpine",
        dashGridOptions={"domLayout": "normal"},
    )

    fig_dept = go.Figure()
    if len(dept_stats) > 1:
        fig_dept = px.bar(
            dept_stats, x="Отдел", y=["Оператор", "Клиент"], barmode="group",
            color_discrete_sequence=[COLORS["operator"], COLORS["client"]],
        )
        fig_dept.update_layout(
            yaxis=dict(range=[0, 10], gridcolor="#E2E8F0"),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, font=CHART_FONT),
            margin=dict(t=10, b=0, l=10, r=10), height=200,
            paper_bgcolor="white", plot_bgcolor="#F8FAFC", font=CHART_FONT,
        )

    charts_row = html.Div(
        [
            _card([section_header("Средние оценки по темам"), dcc.Graph(figure=fig_scores, config={"displayModeBar": False})], {"flex": "2", "minWidth": "300px"}),
            _card([section_header("Срочность"), dcc.Graph(figure=fig_urg, config={"displayModeBar": False})], {"flex": "1", "minWidth": "220px"}),
            _card(
                [
                    section_header("По отделам"),
                    dept_grid,
                    dcc.Graph(figure=fig_dept, config={"displayModeBar": False}) if len(dept_stats) > 1 else html.Div(),
                ],
                {"flex": "1.5", "minWidth": "240px"},
            ),
        ],
        style={"display": "flex", "gap": "1rem", "marginBottom": "1.5rem", "flexWrap": "wrap"},
    )

    # ── Сводная таблица за период ──────────────────────────────────────────────
    table_df = cur_df[[
        "department", "call_topic", "call_type_effective", "urgency",
        "resolution_status", "agent_performance_score", "customer_satisfaction",
        "escalation_flag",
    ]].copy()
    table_df.columns = ["Отдел", "Тема", "Тип", "Срочность", "Статус", "Оператор", "Клиент", "Эскалация"]
    table_df["Эскалация"] = table_df["Эскалация"].map({1: "⚠️ Да", 0: "—", True: "⚠️ Да", False: "—"}).fillna("—")

    grid = dag.AgGrid(
        rowData=table_df.to_dict("records"),
        columnDefs=[
            {"headerName": "Отдел", "field": "Отдел", "flex": 1},
            {"headerName": "Тема", "field": "Тема", "flex": 2},
            {"headerName": "Тип", "field": "Тип", "flex": 1.2},
            {"headerName": "Срочность", "field": "Срочность", "flex": 1, "cellStyle": _URGENCY_CELL_STYLE},
            {"headerName": "Статус", "field": "Статус", "flex": 1},
            {"headerName": "Оператор", "field": "Оператор", "flex": 1, **score_cell()},
            {"headerName": "Клиент", "field": "Клиент", "flex": 1, **score_cell()},
            {"headerName": "Эскалация", "field": "Эскалация", "flex": 1},
        ],
        defaultColDef={"sortable": True, "filter": True, "resizable": True},
        dashGridOptions={"pagination": True, "paginationPageSize": 10},
        style={"height": "420px"},
        className="ag-theme-alpine",
    )

    body_children = [hero_row, kpi_row]
    if prev_label:
        body_children.append(prev_label)
    else:
        body_children.append(html.Div(style={"marginBottom": "1.5rem"}))
    body_children.append(alerts_row)
    if leaderboard_row is not None:
        body_children.append(leaderboard_row)
    body_children += [trend_row, charts_row, _card([section_header(f"Звонки за период ({len(cur_df)})"), grid])]

    return html.Div(body_children)
