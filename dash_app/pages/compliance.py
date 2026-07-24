"""Страница «Compliance» (D1.2).

Эквивалент вкладки «🛡️ Compliance» (dashboard.py:769-843).
"""
import dash
import dash_ag_grid as dag
from dash import html

from dash_app.auth import get_current_department
from dash_app.colors import COLORS
from dash_app.components.cell_format import pct_cell
from dash_app.components.gauge_tile import gauge_tile
from dash_app.components.page_header import page_header, section_header
from dash_app.components.stat_tile import stat_tile
from dash_app.data import load_calls, parse_compliance

dash.register_page(__name__, path="/compliance", name="Compliance", order=3)


def layout():
    df = load_calls(department=get_current_department())

    compliance_by_file = {}
    for _, row in df.iterrows():
        parsed = parse_compliance(row["compliance_json"])
        if parsed is not None:
            compliance_by_file[row["file_name"]] = {
                **parsed,
                "topic": row["call_topic"],
                "operator": row["operator_name"],
            }

    if not compliance_by_file:
        return html.Div([
            page_header("🛡️", "Compliance"),
            html.P(
                "Нет данных compliance-проверки ни по одному звонку.",
                style={"color": COLORS["text_secondary"]},
            ),
        ])

    total = len(compliance_by_file)
    violations = {fn: c for fn, c in compliance_by_file.items() if not c["passed"]}
    pass_rate = (total - len(violations)) / total * 100

    kpi_row = html.Div(
        [
            stat_tile("Проверено звонков", str(total), accent=COLORS["primary_bright"]),
            gauge_tile("Без нарушений", pass_rate, good=80, warn=60),
        ],
        style={"display": "flex", "gap": "1rem", "marginBottom": "1.5rem"},
    )

    # ── Список нарушений ──────────────────────────────────────────────────────
    if not violations:
        violations_block = html.Div(
            "✅ Нарушений не найдено ни в одном проверенном звонке.",
            style={
                "background": COLORS["success_light"],
                "padding": "1rem",
                "borderRadius": "0.5rem",
                "color": COLORS["success"],
                "fontWeight": "500",
            },
        )
    else:
        violation_rows = [
            {
                "Тема": comp["topic"],
                "Оператор": comp["operator"] or "—",
                "Нарушения": "; ".join(comp["issues"]),
            }
            for comp in violations.values()
        ]
        violations_block = dag.AgGrid(
            rowData=violation_rows,
            columnDefs=[
                {"headerName": "Тема", "field": "Тема", "flex": 1.5},
                {"headerName": "Оператор", "field": "Оператор", "flex": 1.5},
                {"headerName": "Нарушения", "field": "Нарушения", "flex": 4,
                 "cellStyle": {"color": COLORS["danger"]}, "wrapText": True, "autoHeight": True},
            ],
            defaultColDef={"sortable": True, "filter": True, "resizable": True},
            dashGridOptions={"pagination": True, "paginationPageSize": 10},
            style={"height": "420px"},
            className="ag-theme-alpine",
        )

    # ── По операторам ─────────────────────────────────────────────────────────
    named_df = df[df["operator_name"].notna() & (df["operator_name"] != "")]
    op_section = []
    if not named_df.empty:
        op_rows = []
        for operator, group in named_df.groupby("operator_name"):
            op_comp = [compliance_by_file[fn] for fn in group["file_name"] if fn in compliance_by_file]
            if not op_comp:
                continue
            op_total = len(op_comp)
            op_passed = sum(1 for c in op_comp if c["passed"])
            op_rows.append({
                "Оператор": operator,
                "Звонков": op_total,
                "Без нарушений (%)": round(op_passed / op_total * 100, 1),
            })

        if op_rows:
            op_grid = dag.AgGrid(
                rowData=op_rows,
                columnDefs=[
                    {"headerName": "Оператор", "field": "Оператор", "flex": 2},
                    {"headerName": "Звонков", "field": "Звонков", "flex": 1},
                    {"headerName": "Без нарушений (%)", "field": "Без нарушений (%)", "flex": 1.5,
                     **pct_cell(good=80, warn=60)},
                ],
                defaultColDef={"sortable": True},
                style={"height": "280px"},
                className="ag-theme-alpine",
            )
            op_section = [
                html.Div(section_header("По операторам"), style={"marginTop": "1.5rem"}),
                op_grid,
            ]

    return html.Div([
        page_header("🛡️", "Compliance", f"{total} звонков проверено"),
        kpi_row,
        html.Div(
            [
                section_header("Звонки с нарушениями"),
                violations_block,
                *op_section,
            ],
            style={
                "background": COLORS["card_bg"],
                "borderRadius": "0.625rem",
                "padding": "1.25rem",
                "boxShadow": "0 1px 3px rgba(0,0,0,0.07), 0 4px 16px rgba(0,0,0,0.04)",
            },
        ),
    ])
