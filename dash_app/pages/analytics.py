"""Страница «Аналитика» — директорский обзор (D1.1).

Эквивалент вкладки «📊 Аналитика» в dashboard.py:295-388.
go.Figure-объекты переносятся «почти бесплатно»: те же вызовы, только
st.plotly_chart(fig) → dcc.Graph(figure=fig).
"""
import dash
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import dash_ag_grid as dag
from dash import html, dcc

from dash_app.auth import get_current_department
from dash_app.colors import COLORS, CHART_FONT
from dash_app.components.cell_format import score_cell
from dash_app.components.gauge_tile import gauge_tile
from dash_app.components.page_header import page_header, section_header
from dash_app.components.stat_tile import stat_tile
from dash_app.data import load_calls

dash.register_page(__name__, path="/", name="Аналитика", order=0)

# ── Стили ag-grid ────────────────────────────────────────────────────────────

_URGENCY_CELL_STYLE = {
    "styleConditions": [
        {"condition": "params.value === 'high'", "style": {"color": "#B91C1C", "fontWeight": "600"}},
        {"condition": "params.value === 'medium'", "style": {"color": "#D97706", "fontWeight": "600"}},
        {"condition": "params.value === 'low'", "style": {"color": "#15803D", "fontWeight": "600"}},
    ]
}


# ── Вспомогательные компоненты ───────────────────────────────────────────────

def _card(children, extra_style=None):
    style = {
        "background": "white",
        "borderRadius": "0.625rem",
        "padding": "1.25rem",
        "boxShadow": "0 1px 3px rgba(0,0,0,0.07), 0 4px 16px rgba(0,0,0,0.04)",
    }
    if extra_style:
        style.update(extra_style)
    return html.Div(children, style=style)


# ── layout() — вызывается Dash'ем при каждом переходе на страницу ────────────

def layout():
    df = load_calls(department=get_current_department())

    avg_agent = df["agent_performance_score"].mean()
    avg_client = df["customer_satisfaction"].mean()
    resolved_pct = (df["resolution_status"] == "resolved").mean() * 100 if not df.empty else 0.0
    escalated = int(df["escalation_flag"].sum()) if not df.empty else 0
    avg_silence = df["silence_pct"].mean()

    # ── KPI tiles ────────────────────────────────────────────────────────────
    kpi_row = html.Div(
        [
            stat_tile("Звонков", str(len(df)), accent=COLORS["kpi_calls"]),
            stat_tile(
                "Оценка оператора",
                f"{avg_agent:.1f}/10" if pd.notna(avg_agent) else "—",
                accent=COLORS["kpi_agent"],
            ),
            stat_tile(
                "Удовл. клиента",
                f"{avg_client:.1f}/10" if pd.notna(avg_client) else "—",
                accent=COLORS["kpi_client"],
            ),
            gauge_tile("Решено", resolved_pct if not df.empty else None, good=70, warn=50),
            stat_tile("Эскалаций", str(escalated), accent=COLORS["kpi_escalated"]),
            stat_tile(
                "Тишина в диалоге",
                f"{avg_silence:.0f}%" if pd.notna(avg_silence) else "—",
                accent=COLORS["kpi_silence"],
            ),
        ],
        style={"display": "flex", "gap": "1rem", "marginBottom": "1.5rem", "flexWrap": "wrap"},
    )

    # ── График 1: средние оценки по темам ─────────────────────────────────────
    # Агрегируем по теме, а не рисуем по бару на звонок — при росте базы
    # (20 → 340+ звонков) сырой per-call bar chart превращается в нечитаемую
    # полосу из перекрывающихся баров.
    topic_stats = df.groupby("call_topic").agg(
        Оператор=("agent_performance_score", "mean"),
        Клиент=("customer_satisfaction", "mean"),
        Звонков=("call_topic", "count"),
    ).round(1).sort_values("Звонков", ascending=False)

    fig_scores = go.Figure()
    if not df.empty:
        fig_scores.add_trace(go.Bar(
            name="Оператор", x=topic_stats.index,
            y=topic_stats["Оператор"], marker_color=COLORS["operator"],
        ))
        fig_scores.add_trace(go.Bar(
            name="Клиент", x=topic_stats.index,
            y=topic_stats["Клиент"], marker_color=COLORS["client"],
        ))
    fig_scores.update_layout(
        barmode="group",
        yaxis=dict(range=[0, 10], title="Оценка", gridcolor="#E2E8F0"),
        xaxis=dict(tickangle=-30, gridcolor="#E2E8F0"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, font=CHART_FONT),
        margin=dict(t=10, b=0, l=10, r=10),
        height=300,
        paper_bgcolor="white",
        plot_bgcolor="#F8FAFC",
        font=CHART_FONT,
    )

    # ── График 2: срочность (donut) ───────────────────────────────────────────
    color_map = {
        "low": COLORS["urgency_low"],
        "medium": COLORS["urgency_medium"],
        "high": COLORS["urgency_high"],
    }
    if not df.empty:
        urgency_counts = df["urgency"].value_counts()
        fig_urg = px.pie(
            values=urgency_counts.values,
            names=urgency_counts.index,
            color=urgency_counts.index,
            color_discrete_map=color_map,
            hole=0.45,
        )
        fig_urg.update_layout(
            showlegend=True,
            legend=dict(orientation="h", yanchor="bottom", y=-0.2, font=CHART_FONT),
            margin=dict(t=10, b=10, l=0, r=0),
            height=300,
            paper_bgcolor="white",
            font=CHART_FONT,
        )
    else:
        fig_urg = go.Figure()

    # ── График 3: по отделам ──────────────────────────────────────────────────
    dept_stats = df.groupby("department").agg(
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
            dept_stats, x="Отдел", y=["Оператор", "Клиент"],
            barmode="group",
            color_discrete_sequence=[COLORS["operator"], COLORS["client"]],
        )
        fig_dept.update_layout(
            yaxis=dict(range=[0, 10], gridcolor="#E2E8F0"),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, font=CHART_FONT),
            margin=dict(t=10, b=0, l=10, r=10),
            height=200,
            paper_bgcolor="white",
            plot_bgcolor="#F8FAFC",
            font=CHART_FONT,
        )

    charts_row = html.Div(
        [
            _card(
                [section_header("Средние оценки по темам"),
                 dcc.Graph(figure=fig_scores, config={"displayModeBar": False})],
                {"flex": "2", "minWidth": "300px"},
            ),
            _card(
                [section_header("Срочность"),
                 dcc.Graph(figure=fig_urg, config={"displayModeBar": False})],
                {"flex": "1", "minWidth": "220px"},
            ),
            _card(
                [
                    section_header("По отделам"),
                    dept_grid,
                    dcc.Graph(figure=fig_dept, config={"displayModeBar": False})
                    if len(dept_stats) > 1 else html.Div(),
                ],
                {"flex": "1.5", "minWidth": "240px"},
            ),
        ],
        style={"display": "flex", "gap": "1rem", "marginBottom": "1.5rem", "flexWrap": "wrap"},
    )

    # ── Сводная таблица: все звонки (ag-grid) ─────────────────────────────────
    table_df = df[[
        "department", "call_topic", "call_type_effective", "urgency",
        "resolution_status", "agent_performance_score", "customer_satisfaction",
        "escalation_flag",
    ]].copy()
    table_df.columns = ["Отдел", "Тема", "Тип", "Срочность", "Статус", "Оператор", "Клиент", "Эскалация"]
    table_df["Эскалация"] = table_df["Эскалация"].map(
        {1: "⚠️ Да", 0: "—", True: "⚠️ Да", False: "—"}
    ).fillna("—")

    grid = dag.AgGrid(
        rowData=table_df.to_dict("records"),
        columnDefs=[
            {"headerName": "Отдел", "field": "Отдел", "flex": 1},
            {"headerName": "Тема", "field": "Тема", "flex": 2},
            {"headerName": "Тип", "field": "Тип", "flex": 1.2},
            {"headerName": "Срочность", "field": "Срочность", "flex": 1,
             "cellStyle": _URGENCY_CELL_STYLE},
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

    return html.Div([
        page_header("📊", "Аналитика колл-центра", f"{len(df)} звонков в базе"),
        kpi_row,
        charts_row,
        _card([section_header("Все звонки"), grid]),
    ])
