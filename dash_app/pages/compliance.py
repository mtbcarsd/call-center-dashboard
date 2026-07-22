"""Страница «Compliance» (D1.2).

Эквивалент вкладки «🛡️ Compliance» (dashboard.py:769-843).
"""
import dash
import dash_ag_grid as dag
from dash import html

from dash_app.colors import COLORS
from dash_app.components.stat_tile import stat_tile
from dash_app.data import load_calls, parse_compliance

dash.register_page(__name__, path="/compliance", name="Compliance", order=3)


def layout():
    df = load_calls()

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
            html.H2("🛡️ Compliance", style={"color": COLORS["text_primary"], "fontWeight": "700"}),
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
            stat_tile(
                "Без нарушений",
                f"{pass_rate:.0f}%",
                subtitle=f"{len(violations)} с нарушениями" if violations else "Всё в порядке",
                accent=COLORS["success"] if not violations else COLORS["danger"],
            ),
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
                "color": "#166534",
                "fontWeight": "500",
            },
        )
    else:
        cards = []
        for fn, comp in violations.items():
            cards.append(html.Div(
                [
                    html.Div(
                        comp["topic"],
                        style={"fontWeight": "600", "color": COLORS["text_primary"],
                               "marginBottom": "0.35rem"},
                    ),
                    html.Ul(
                        [html.Li(issue, style={"marginBottom": "0.2rem"}) for issue in comp["issues"]],
                        style={"margin": "0", "paddingLeft": "1.25rem",
                               "color": COLORS["danger"], "fontSize": "0.875rem"},
                    ),
                ],
                style={
                    "background": "#FFF5F5",
                    "borderLeft": f"4px solid {COLORS['danger']}",
                    "padding": "0.875rem 1rem",
                    "borderRadius": "0.375rem",
                    "marginBottom": "0.75rem",
                },
            ))
        violations_block = html.Div(cards)

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
            pct_style = {
                "styleConditions": [
                    {"condition": "params.value >= 80", "style": {"color": "#15803D", "fontWeight": "600"}},
                    {"condition": "params.value >= 60 && params.value < 80",
                     "style": {"color": "#D97706", "fontWeight": "500"}},
                    {"condition": "params.value < 60", "style": {"color": "#B91C1C", "fontWeight": "600"}},
                ]
            }
            op_grid = dag.AgGrid(
                rowData=op_rows,
                columnDefs=[
                    {"headerName": "Оператор", "field": "Оператор", "flex": 2},
                    {"headerName": "Звонков", "field": "Звонков", "flex": 1},
                    {"headerName": "Без нарушений (%)", "field": "Без нарушений (%)", "flex": 1.5,
                     "valueFormatter": {"function": "params.value.toFixed(0) + '%'"},
                     "cellStyle": pct_style},
                ],
                defaultColDef={"sortable": True},
                style={"height": "280px"},
                className="ag-theme-alpine",
            )
            op_section = [
                html.H4(
                    "По операторам",
                    style={"color": COLORS["text_primary"], "fontWeight": "600",
                           "marginTop": "1.5rem", "marginBottom": "0.75rem"},
                ),
                op_grid,
            ]

    return html.Div([
        html.H2(
            "🛡️ Compliance",
            style={"color": COLORS["text_primary"], "margin": "0 0 0.25rem 0", "fontWeight": "700"},
        ),
        html.P(
            f"{total} звонков проверено",
            style={"color": COLORS["text_secondary"], "margin": "0 0 1.5rem 0", "fontSize": "0.875rem"},
        ),
        kpi_row,
        html.Div(
            [
                html.H4(
                    "Звонки с нарушениями",
                    style={"color": COLORS["text_primary"], "fontWeight": "600",
                           "marginBottom": "1rem", "margin": "0 0 1rem 0"},
                ),
                violations_block,
                *op_section,
            ],
            style={
                "background": "white",
                "borderRadius": "0.625rem",
                "padding": "1.25rem",
                "boxShadow": "0 1px 3px rgba(0,0,0,0.07), 0 4px 16px rgba(0,0,0,0.04)",
            },
        ),
    ])
