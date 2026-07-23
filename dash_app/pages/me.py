"""Страница «Мой кабинет» — личный кабинет сотрудника (D3.1).

Единственная страница, доступная role=employee (см. route guard в app.py) —
показывает только звонки этого оператора: server-side фильтр по
operator_match_name из сессии (dash_app.data.load_calls), тот же паттерн,
что department-фильтр для manager (D2). Плюс кнопка «Получить рекомендации» —
запрос к GET /coaching/{operator_name} (api, agents/coaching.py).
"""
import os
from urllib.parse import quote

import dash
import pandas as pd
import dash_ag_grid as dag
import requests
from dash import html, dcc, callback, Input, Output

from checklist import CHECKLIST
from dash_app.auth import get_current_operator_match_name
from dash_app.coaching_logic import render_coaching_result
from dash_app.colors import COLORS
from dash_app.components.cell_format import pct_cell, score_cell
from dash_app.components.gauge_tile import gauge_tile
from dash_app.components.stat_tile import stat_tile
from dash_app.data import checklist_pass_rates, load_calls, parse_checklist

dash.register_page(__name__, path="/me", name="Мой кабинет", order=6)

_API_BASE = os.environ.get("API_BASE_URL", "https://api-production-95c7e.up.railway.app")


def _card(children):
    return html.Div(
        children,
        style={
            "background": "white",
            "borderRadius": "0.625rem",
            "padding": "1.25rem",
            "boxShadow": "0 1px 3px rgba(0,0,0,0.07), 0 4px 16px rgba(0,0,0,0.04)",
            "marginBottom": "1.5rem",
        },
    )


def _section_h(text: str):
    return html.H4(
        text,
        style={"color": COLORS["text_primary"], "fontWeight": "600", "marginBottom": "0.75rem"},
    )


def layout():
    operator = get_current_operator_match_name()
    if not operator:
        return html.Div([
            html.H2("🙋 Мой кабинет", style={"color": COLORS["text_primary"], "fontWeight": "700"}),
            html.P(
                "Ваша учётная запись не привязана к оператору. Обратитесь к администратору.",
                style={"color": COLORS["text_secondary"]},
            ),
        ])

    df = load_calls(operator_match_name=operator)

    header = html.Div([
        html.H2(
            f"🙋 Мой кабинет — {operator}",
            style={"color": COLORS["text_primary"], "margin": "0 0 0.25rem 0", "fontWeight": "700"},
        ),
        html.P(
            f"{len(df)} звонков",
            style={"color": COLORS["text_secondary"], "margin": "0 0 1.5rem 0", "fontSize": "0.875rem"},
        ),
    ])

    if df.empty:
        return html.Div([header, html.P("Звонков пока нет.", style={"color": COLORS["text_secondary"]})])

    avg_agent = df["agent_performance_score"].mean()
    avg_client = df["customer_satisfaction"].mean()
    resolved_pct = (df["resolution_status"] == "resolved").mean() * 100

    kpi_row = html.Div(
        [
            stat_tile("Звонков", str(len(df)), accent=COLORS["kpi_calls"]),
            stat_tile(
                "Оценка (чек-лист)",
                f"{avg_agent:.1f}/10" if pd.notna(avg_agent) else "—",
                accent=COLORS["kpi_agent"],
            ),
            stat_tile(
                "Удовл. клиента",
                f"{avg_client:.1f}/10" if pd.notna(avg_client) else "—",
                accent=COLORS["kpi_client"],
            ),
            gauge_tile("Решено", resolved_pct, good=70, warn=50),
        ],
        style={"display": "flex", "gap": "1rem", "marginBottom": "1.5rem", "flexWrap": "wrap"},
    )

    # ── Мой чек-лист ───────────────────────────────────────────────────────────
    checklists = [c for c in df["checklist_json"].apply(parse_checklist) if c]
    checklist_section = html.Div()
    if checklists:
        rates = checklist_pass_rates(checklists)
        rating_df = pd.DataFrame([
            {"Пункт чек-листа": item["label"], "Прохождение (%)": round(rates.get(item["label"]) or 0, 1)}
            for item in CHECKLIST
        ]).sort_values("Прохождение (%)", ascending=True)
        checklist_section = _card([
            _section_h("Мой чек-лист"),
            dag.AgGrid(
                rowData=rating_df.to_dict("records"),
                columnDefs=[
                    {"headerName": "Пункт чек-листа", "field": "Пункт чек-листа", "flex": 3},
                    {"headerName": "Прохождение (%)", "field": "Прохождение (%)", "flex": 1.5, **pct_cell()},
                ],
                defaultColDef={"sortable": True},
                style={"height": "260px"},
                className="ag-theme-alpine",
            ),
        ])

    # ── Мои звонки ─────────────────────────────────────────────────────────────
    table_df = df[[
        "call_topic", "call_type_effective", "urgency", "resolution_status",
        "agent_performance_score", "customer_satisfaction",
    ]].copy()
    table_df.columns = ["Тема", "Тип", "Срочность", "Статус", "Оценка", "Клиент"]

    calls_section = _card([
        _section_h("Мои звонки"),
        dag.AgGrid(
            rowData=table_df.to_dict("records"),
            columnDefs=[
                {"headerName": "Тема", "field": "Тема", "flex": 2},
                {"headerName": "Тип", "field": "Тип", "flex": 1},
                {"headerName": "Срочность", "field": "Срочность", "flex": 1},
                {"headerName": "Статус", "field": "Статус", "flex": 1},
                {"headerName": "Оценка", "field": "Оценка", "flex": 1, **score_cell()},
                {"headerName": "Клиент", "field": "Клиент", "flex": 1, **score_cell()},
            ],
            defaultColDef={"sortable": True, "filter": True, "resizable": True},
            dashGridOptions={"pagination": True, "paginationPageSize": 10},
            style={"height": "380px"},
            className="ag-theme-alpine",
        ),
    ])

    coaching_section = _card([
        _section_h("🎯 Рекомендации по обучению"),
        html.P(
            "LLM-агент анализирует ваш чек-лист и compliance-историю и даёт краткую обратную связь.",
            style={"color": COLORS["text_secondary"], "fontSize": "0.875rem", "marginBottom": "1rem"},
        ),
        html.Button(
            "🔄 Получить рекомендации",
            id="coaching-refresh-btn",
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
                "fontFamily": "inherit",
                "marginBottom": "1rem",
            },
        ),
        dcc.Loading(
            html.Div(id="coaching-result-container"),
            type="dot",
            color=COLORS["primary_bright"],
        ),
    ])

    return html.Div([header, kpi_row, checklist_section, calls_section, coaching_section])


@callback(
    Output("coaching-result-container", "children"),
    Input("url", "pathname"),
    Input("coaching-refresh-btn", "n_clicks"),
    prevent_initial_call=False,
)
def fetch_and_display_coaching(pathname, n_clicks):
    if (pathname or "/") != "/me":
        return dash.no_update
    operator = get_current_operator_match_name()
    if not operator:
        return dash.no_update
    try:
        resp = requests.get(f"{_API_BASE}/coaching/{quote(operator, safe='')}", timeout=30)
        resp.raise_for_status()
        result = resp.json()
    except requests.RequestException as e:
        return render_coaching_result(None, str(e))
    return render_coaching_result(result, None)
