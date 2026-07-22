"""Страница «Рейтинг» — разбивка чек-листа по пунктам (D1.2).

Эквивалент вкладки «🏆 Рейтинг» (dashboard.py:700-767).
"""
import dash
import pandas as pd
import dash_ag_grid as dag
from dash import html

from checklist import CHECKLIST
from dash_app.auth import get_current_department
from dash_app.colors import COLORS
from dash_app.data import load_calls, parse_checklist, checklist_pass_rates

dash.register_page(__name__, path="/rating", name="Рейтинг", order=2)

_PCT_STYLE = {
    "styleConditions": [
        {"condition": "params.value >= 75", "style": {"color": "#15803D", "fontWeight": "600"}},
        {"condition": "params.value >= 50 && params.value < 75", "style": {"color": "#D97706", "fontWeight": "500"}},
        {"condition": "params.value < 50", "style": {"color": "#B91C1C", "fontWeight": "600"}},
    ]
}
_PCT_FMT = {"function": "params.value != null ? params.value.toFixed(0) + '%' : '—'"}


def layout():
    df = load_calls(department=get_current_department())
    all_checklists = [c for c in df["checklist_json"].apply(parse_checklist) if c]

    if not all_checklists:
        return html.Div([
            html.H2("🏆 Рейтинг", style={"color": COLORS["text_primary"], "fontWeight": "700"}),
            html.P("Нет данных чек-листа ни по одному звонку.", style={"color": COLORS["text_secondary"]}),
        ])

    overall_rates = checklist_pass_rates(all_checklists)
    rating_rows = [
        {
            "Пункт чек-листа": item["label"],
            "Вес (%)": item["weight"],
            "Прохождение (%)": round(overall_rates.get(item["label"]) or 0, 1),
        }
        for item in CHECKLIST
    ]
    rating_df = pd.DataFrame(rating_rows).sort_values("Прохождение (%)", ascending=True)

    worst = rating_df.iloc[0]
    warning_block = None
    if pd.notna(worst["Прохождение (%)"]) and worst["Прохождение (%)"] < 50:
        warning_block = html.Div(
            f"⚠️ Худший пункт — «{worst['Пункт чек-листа']}»: "
            f"проходит только {worst['Прохождение (%)']:.0f}% звонков. Стоит обратить внимание.",
            style={
                "background": COLORS["warning_light"],
                "borderLeft": f"4px solid {COLORS['warning']}",
                "padding": "0.75rem 1rem",
                "borderRadius": "0.375rem",
                "color": "#92400E",
                "fontWeight": "500",
                "marginBottom": "1rem",
                "fontSize": "0.9rem",
            },
        )

    main_grid = dag.AgGrid(
        rowData=rating_df.to_dict("records"),
        columnDefs=[
            {"headerName": "Пункт чек-листа", "field": "Пункт чек-листа", "flex": 3},
            {"headerName": "Вес (%)", "field": "Вес (%)", "flex": 1},
            {"headerName": "Прохождение (%)", "field": "Прохождение (%)", "flex": 1.5,
             "valueFormatter": _PCT_FMT, "cellStyle": _PCT_STYLE},
        ],
        defaultColDef={"sortable": True, "resizable": True},
        style={"height": "290px"},
        className="ag-theme-alpine",
    )

    # ── По операторам ─────────────────────────────────────────────────────────
    named_df = df[df["operator_name"].notna() & (df["operator_name"] != "")]
    op_section = []
    if not named_df.empty:
        op_rows = []
        for operator, group in named_df.groupby("operator_name"):
            op_checklists = [c for c in group["checklist_json"].apply(parse_checklist) if c]
            if not op_checklists:
                continue
            rates = checklist_pass_rates(op_checklists)
            row = {"Оператор": operator, "Звонков": len(group)}
            row.update({k: round(v or 0, 1) for k, v in rates.items()})
            op_rows.append(row)

        if op_rows:
            rate_labels = [item["label"] for item in CHECKLIST]
            op_col_defs = [
                {"headerName": "Оператор", "field": "Оператор", "flex": 2},
                {"headerName": "Звонков", "field": "Звонков", "flex": 1},
            ]
            for label in rate_labels:
                short = label[:14] + "…" if len(label) > 14 else label
                op_col_defs.append({
                    "headerName": short, "field": label, "flex": 1.2,
                    "headerTooltip": label,
                    "valueFormatter": _PCT_FMT,
                    "cellStyle": _PCT_STYLE,
                })
            op_grid = dag.AgGrid(
                rowData=op_rows,
                columnDefs=op_col_defs,
                defaultColDef={"sortable": True, "resizable": True},
                style={"height": "320px"},
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

    card_children = []
    if warning_block:
        card_children.append(warning_block)
    card_children.append(main_grid)
    card_children.extend(op_section)

    return html.Div([
        html.H2(
            "🏆 Рейтинг по чек-листу",
            style={"color": COLORS["text_primary"], "margin": "0 0 0.25rem 0", "fontWeight": "700"},
        ),
        html.P(
            f"Разбивка по {len(CHECKLIST)} пунктам · {len(df)} звонков",
            style={"color": COLORS["text_secondary"], "margin": "0 0 1.5rem 0", "fontSize": "0.875rem"},
        ),
        html.Div(
            card_children,
            style={
                "background": "white",
                "borderRadius": "0.625rem",
                "padding": "1.25rem",
                "boxShadow": "0 1px 3px rgba(0,0,0,0.07), 0 4px 16px rgba(0,0,0,0.04)",
            },
        ),
    ])
