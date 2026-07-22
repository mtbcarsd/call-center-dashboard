"""Страница «Операторы» — статистика по именованным звонкам (D1.2).

Эквивалент вкладки «🧑‍💼 Операторы» (dashboard.py:661-698).
"""
import dash
import dash_ag_grid as dag
from dash import html

from dash_app.auth import get_current_department
from dash_app.colors import COLORS
from dash_app.components.cell_format import score_cell
from dash_app.data import load_calls

dash.register_page(__name__, path="/operators", name="Операторы", order=1)


def layout():
    df = load_calls(department=get_current_department())
    named_df = df[df["operator_name"].notna() & (df["operator_name"] != "")]
    unnamed_count = len(df) - len(named_df)

    if named_df.empty:
        return html.Div([
            html.H2("🧑‍💼 Операторы", style={"color": COLORS["text_primary"], "fontWeight": "700"}),
            html.P(
                "Пока ни один звонок не привязан к оператору. "
                "Укажите имя в деталке звонка (вкладка «Звонки»).",
                style={"color": COLORS["text_secondary"]},
            ),
        ])

    op_stats = named_df.groupby("operator_name").agg(
        Звонков=("file_name", "count"),
        Оценка=("agent_performance_score", "mean"),
        QA=("qa_score", "mean"),
        Клиент=("customer_satisfaction", "mean"),
    ).round(2).reset_index()
    op_stats.columns = ["Оператор", "Звонков", "Оценка (чек-лист)", "QA-оценка", "Удовл клиента"]
    op_stats = op_stats.sort_values("Звонков", ascending=False)

    grid = dag.AgGrid(
        rowData=op_stats.to_dict("records"),
        columnDefs=[
            {"headerName": "Оператор", "field": "Оператор", "flex": 2},
            {"headerName": "Звонков", "field": "Звонков", "flex": 1, "sort": "desc"},
            {"headerName": "Оценка (чек-лист)", "field": "Оценка (чек-лист)", "flex": 1.5, **score_cell()},
            {"headerName": "QA-оценка", "field": "QA-оценка", "flex": 1, **score_cell()},
            {"headerName": "Удовл клиента", "field": "Удовл клиента", "flex": 1.5, **score_cell()},
        ],
        defaultColDef={"sortable": True, "filter": True, "resizable": True},
        style={"height": "420px"},
        className="ag-theme-alpine",
    )

    subtitle = f"{len(named_df)} из {len(df)} звонков привязаны к оператору"
    if unnamed_count:
        subtitle += f" · {unnamed_count} ещё без имени"

    return html.Div([
        html.H2(
            "🧑‍💼 Статистика по операторам",
            style={"color": COLORS["text_primary"], "margin": "0 0 0.25rem 0", "fontWeight": "700"},
        ),
        html.P(
            subtitle,
            style={"color": COLORS["text_secondary"], "margin": "0 0 1.5rem 0", "fontSize": "0.875rem"},
        ),
        html.Div(
            grid,
            style={
                "background": "white",
                "borderRadius": "0.625rem",
                "padding": "1.25rem",
                "boxShadow": "0 1px 3px rgba(0,0,0,0.07), 0 4px 16px rgba(0,0,0,0.04)",
            },
        ),
    ])
