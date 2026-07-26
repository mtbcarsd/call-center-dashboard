"""Страница «Compliance» (D1.2, расширена в G1/G2).

Стиль вдохновлён dash-clinical-analytics (один из эталонных демо-дашбордов
Plotly): https://github.com/plotly/dash-sample-apps/tree/main/apps/dash-clinical-analytics
Там — annotated heatmap (день недели × час дня) объёма пациентов, клик по
ячейке подсвечивает её рамкой и фильтрует нижнюю панель (wait time/care
score) именно за этот день+час; сверху — dropdown клиники, multi-select
источника поступления, DatePickerRange.

Прямая параллель: heatmap здесь — нарушения по дням недели × неделям
периода (не «час дня» — при 57 нарушениях за весь период часовая
грануляция размазала бы данные почти до пустоты, недельная даёт
содержательную картину: пятница/понедельник заметно выше воскресенья).
Клик по ячейке фильтрует таблицу «Звонки с нарушениями» на конкретный
день. Multi-select «источника поступления» → multi-select «тип нарушения»
(в данных ровно 2 устойчивые категории). Dropdown «клиника» не переносим —
это уже отдел, и он либо жёстко задан ролью (manager), либо не сужается
специально (executive и так видит сводку «По отделам» в других разделах).
"""
from datetime import date, timedelta
from urllib.parse import quote_plus

import dash
import pandas as pd
import plotly.graph_objects as go
import dash_ag_grid as dag
from dash import Input, Output, callback, dcc, html

from dash_app.auth import get_current_department
from dash_app.colors import COLORS, CHART_FONT
from dash_app.components.cell_format import pct_cell
from dash_app.components.gauge_tile import gauge_tile
from dash_app.components.page_header import page_header, section_header
from dash_app.components.stat_tile import stat_tile
from dash_app.data import load_calls, parse_compliance

dash.register_page(__name__, path="/compliance", name="Compliance", order=3)

_TYPE_LABELS = {"warnings": "Не упомянуты предупреждения", "promises": "Некорректные обещания"}
_WEEKDAYS_RU = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
_MONTHS_RU = ["янв", "фев", "мар", "апр", "май", "июн", "июл", "авг", "сен", "окт", "ноя", "дек"]


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


def _ru_short_date(d: date) -> str:
    return f"{d.day} {_MONTHS_RU[d.month - 1]}"


def _categorize(issues: list) -> set:
    text = " ".join(issues)
    cats = set()
    if "предупрежд" in text:
        cats.add("warnings")
    if "обещан" in text:
        cats.add("promises")
    return cats or {"other"}


def _load_compliance(department) -> pd.DataFrame:
    """Одна строка на звонок с compliance-разбором + effective_dt.
    Возвращает только звонки, где compliance-проверка вообще проводилась."""
    df = load_calls(department=department)
    records = []
    for _, row in df.iterrows():
        parsed = parse_compliance(row["compliance_json"])
        if parsed is None:
            continue
        eff = row["call_datetime"] if pd.notna(row["call_datetime"]) else row["analyzed_at"]
        records.append({
            "file_name": row["file_name"],
            "topic": row["call_topic"],
            "operator": row["operator_name"],
            "passed": parsed["passed"],
            "issues": parsed["issues"],
            "categories": _categorize(parsed["issues"]) if not parsed["passed"] else set(),
            "effective_dt": pd.to_datetime(eff),
        })
    return pd.DataFrame(records)


def layout():
    comp_df = _load_compliance(get_current_department())
    if comp_df.empty:
        return html.Div([
            page_header("🛡️", "Compliance"),
            html.P(
                "Нет данных compliance-проверки ни по одному звонку.",
                style={"color": COLORS["text_secondary"]},
            ),
        ])

    min_allowed = comp_df["effective_dt"].min().date()
    max_allowed = comp_df["effective_dt"].max().date()

    filter_bar = html.Div(
        [
            dcc.Checklist(
                id="compliance-type-filter",
                options=[{"label": f" {label}", "value": key} for key, label in _TYPE_LABELS.items()],
                value=list(_TYPE_LABELS.keys()),
                labelStyle={
                    "display": "flex", "alignItems": "center", "gap": "0.3rem", "marginRight": "1.25rem",
                    "fontSize": "0.875rem", "color": COLORS["text_secondary"], "cursor": "pointer",
                },
                style={"display": "flex", "flexWrap": "wrap"},
            ),
            dcc.DatePickerRange(
                id="compliance-date-range",
                min_date_allowed=min_allowed, max_date_allowed=max_allowed,
                start_date=min_allowed, end_date=max_allowed,
                display_format="DD.MM.YYYY",
            ),
        ],
        style={"display": "flex", "alignItems": "center", "gap": "1.5rem", "flexWrap": "wrap", "marginBottom": "1.5rem"},
    )

    return html.Div([
        page_header("🛡️", "Compliance", f"{len(comp_df)} звонков проверено"),
        filter_bar,
        html.Div(id="compliance-kpi-container", style={"marginBottom": "1.5rem"}),
        _card(
            [
                section_header("Нарушения по дням"),
                dcc.Graph(id="compliance-heatmap", figure=go.Figure(), config={"displayModeBar": False}),
            ],
            {"marginBottom": "1.5rem"},
        ),
        _card([
            html.Div(
                [
                    section_header("Звонки с нарушениями"),
                    html.Button(
                        "Показать все дни", id="compliance-reset-btn", n_clicks=0,
                        style={
                            "background": "none", "border": f"1px solid {COLORS['border']}",
                            "borderRadius": "0.4rem", "padding": "0.3rem 0.75rem", "fontSize": "0.8rem",
                            "color": COLORS["text_secondary"], "cursor": "pointer", "fontFamily": "inherit",
                        },
                    ),
                ],
                style={"display": "flex", "justifyContent": "space-between", "alignItems": "center"},
            ),
            html.Div(id="compliance-table-container"),
        ]),
        html.Div(id="compliance-byop-container", style={"marginTop": "1.5rem"}),
        dcc.Store(id="compliance-selected-cell"),
    ])


def _date_filtered(department, start_date, end_date) -> pd.DataFrame:
    """Только по диапазону дат — это основа для KPI и «По операторам»: тип
    нарушения там сознательно не учитывается (см. docstring модуля/план G2)
    — иначе снятие галочки с одной категории искусственно завышало бы
    «% без нарушений», выкидывая из знаменателя часть проверенных звонков."""
    comp_df = _load_compliance(department)
    if comp_df.empty or not start_date or not end_date:
        return comp_df
    start = pd.Timestamp(start_date)
    end = pd.Timestamp(end_date) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
    return comp_df[(comp_df["effective_dt"] >= start) & (comp_df["effective_dt"] <= end)]


def _type_filtered_violations(df: pd.DataFrame, types) -> pd.DataFrame:
    """Только нарушения (passed=False), сузенные до выбранных категорий —
    используется исключительно heatmap'ом и таблицей нарушений (drill-down
    лупа), не влияет на общие KPI."""
    violations = df[~df["passed"]]
    types = set(types or [])
    if not types:
        return violations.iloc[0:0]
    return violations[violations["categories"].apply(lambda c: bool(c & types))]


@callback(
    Output("compliance-kpi-container", "children"),
    Input("compliance-date-range", "start_date"),
    Input("compliance-date-range", "end_date"),
)
def render_kpis(start_date, end_date):
    df = _date_filtered(get_current_department(), start_date, end_date)
    total = len(df)
    violations = int((~df["passed"]).sum())
    pass_rate = (total - violations) / total * 100 if total else None
    return html.Div(
        [
            stat_tile("Проверено звонков", str(total), accent=COLORS["primary_bright"]),
            gauge_tile("Без нарушений", pass_rate, good=80, warn=60),
        ],
        style={"display": "flex", "gap": "1rem", "flexWrap": "wrap"},
    )


@callback(
    Output("compliance-selected-cell", "data"),
    Input("compliance-heatmap", "clickData"),
    prevent_initial_call=True,
)
def capture_click(click_data):
    # Промежуточный Store вместо прямого чтения clickData графика в
    # колбэке, который сам же перерисовывает figure этого графика — иначе
    # Plotly.js на клиенте иногда делает частичное (не полное) обновление
    # трейсов при одновременном срабатывании figure-Output и clickData-Input
    # одного графика, и heatmap рендерится сломанным (цвета/аннотации
    # съезжают в угол). Через Store колбэки ниже уже не трогают clickData
    # напрямую — тот же приём, что calls-selected-file в pages/calls.py.
    if not click_data:
        return dash.no_update
    pt = click_data["points"][0]
    return {"x": pt["x"], "y": pt["y"]}


@callback(
    Output("compliance-heatmap", "figure"),
    Input("compliance-type-filter", "value"),
    Input("compliance-date-range", "start_date"),
    Input("compliance-date-range", "end_date"),
    Input("compliance-selected-cell", "data"),
)
def render_heatmap(types, start_date, end_date, selected_cell):
    df = _date_filtered(get_current_department(), start_date, end_date)
    violations = _type_filtered_violations(df, types).copy()

    if violations.empty:
        fig = go.Figure()
        fig.update_layout(
            height=260, paper_bgcolor="white", font=CHART_FONT,
            xaxis={"visible": False}, yaxis={"visible": False},
            annotations=[{
                "text": "Нарушений нет по выбранным фильтрам", "showarrow": False,
                "font": CHART_FONT, "xref": "paper", "yref": "paper", "x": 0.5, "y": 0.5,
            }],
        )
        return fig

    violations["week_start"] = violations["effective_dt"].apply(
        lambda d: d.date() - timedelta(days=d.weekday())
    )
    violations["weekday_idx"] = violations["effective_dt"].apply(lambda d: d.weekday())

    weeks = sorted(violations["week_start"].unique())
    x_vals = [w.isoformat() for w in weeks]
    tick_text = [_ru_short_date(w) for w in weeks]

    z = [[0] * len(weeks) for _ in range(7)]
    counts = violations.groupby(["weekday_idx", "week_start"]).size()
    for (wd, wk), n in counts.items():
        z[wd][weeks.index(wk)] = int(n)

    fig = go.Figure(go.Heatmap(
        z=z, x=x_vals, y=_WEEKDAYS_RU,
        colorscale=[[0, "#F1F5F9"], [1, COLORS["danger"]]],
        showscale=False, xgap=3, ygap=3,
        hovertemplate="%{y}, неделя с %{x}<br>Нарушений: %{z}<extra></extra>",
    ))

    annotations = []
    for wd in range(7):
        for wi, wk in enumerate(weeks):
            val = z[wd][wi]
            if val:
                annotations.append({
                    "x": x_vals[wi], "y": _WEEKDAYS_RU[wd], "text": str(val),
                    "showarrow": False, "font": {"color": "white", "size": 11},
                })

    shapes = []
    if selected_cell:
        cx, cy = selected_cell.get("x"), selected_cell.get("y")
        if cx in x_vals and cy in _WEEKDAYS_RU:
            xi, yi = x_vals.index(cx), _WEEKDAYS_RU.index(cy)
            shapes.append({
                "type": "rect", "xref": "x", "yref": "y",
                "x0": xi - 0.5, "x1": xi + 0.5, "y0": yi - 0.5, "y1": yi + 0.5,
                "line": {"color": COLORS["primary_bright"], "width": 3},
            })

    fig.update_layout(
        height=280, margin=dict(t=10, b=10, l=10, r=10),
        paper_bgcolor="white", font=CHART_FONT,
        # type="category" — явно, иначе Plotly.js после клика по ячейке
        # иногда переопределяет тип оси на "date" (x_vals — строки вида
        # "2026-06-01", похожие на даты), из-за чего уже отрисованные
        # аннотации (привязанные к категориальным позициям) съезжают в
        # угол при следующем обновлении figure.
        xaxis=dict(tickvals=x_vals, ticktext=tick_text, side="bottom", type="category"),
        yaxis=dict(autorange="reversed", type="category"),
        annotations=annotations, shapes=shapes,
    )
    return fig


@callback(
    Output("compliance-table-container", "children"),
    Input("compliance-type-filter", "value"),
    Input("compliance-date-range", "start_date"),
    Input("compliance-date-range", "end_date"),
    Input("compliance-selected-cell", "data"),
)
def render_table(types, start_date, end_date, selected_cell):
    df = _date_filtered(get_current_department(), start_date, end_date)
    violations = _type_filtered_violations(df, types).copy()

    week_iso, weekday_ru = (selected_cell.get("x"), selected_cell.get("y")) if selected_cell else (None, None)
    caption = None
    if week_iso and weekday_ru and not violations.empty:
        violations["week_start"] = violations["effective_dt"].apply(
            lambda d: (d.date() - timedelta(days=d.weekday())).isoformat()
        )
        violations["weekday_ru"] = violations["effective_dt"].apply(lambda d: _WEEKDAYS_RU[d.weekday()])
        violations = violations[(violations["week_start"] == week_iso) & (violations["weekday_ru"] == weekday_ru)]
        caption = html.P(
            f"Показаны только нарушения: {weekday_ru}, неделя с {_ru_short_date(date.fromisoformat(week_iso))} "
            "— нажмите «Показать все дни», чтобы сбросить.",
            style={"color": COLORS["text_secondary"], "fontSize": "0.8rem", "marginBottom": "0.75rem"},
        )

    if violations.empty:
        block = html.Div(
            "✅ Нарушений не найдено по выбранным фильтрам.",
            style={
                "background": COLORS["success_light"], "padding": "1rem", "borderRadius": "0.5rem",
                "color": COLORS["success"], "fontWeight": "500",
            },
        )
    else:
        rows = [
            {"Тема": r["topic"], "Оператор": r["operator"] or "—", "Нарушения": "; ".join(r["issues"])}
            for _, r in violations.iterrows()
        ]
        block = dag.AgGrid(
            rowData=rows,
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

    children = [block] if not caption else [caption, block]
    return html.Div(children)


@callback(
    Output("compliance-selected-cell", "data", allow_duplicate=True),
    Input("compliance-reset-btn", "n_clicks"),
    prevent_initial_call=True,
)
def reset_selection(_n_clicks):
    return None


@callback(
    Output("compliance-byop-container", "children"),
    Input("compliance-date-range", "start_date"),
    Input("compliance-date-range", "end_date"),
)
def render_by_operator(start_date, end_date):
    df = _date_filtered(get_current_department(), start_date, end_date)
    named_df = df[df["operator"].notna() & (df["operator"] != "")]
    if named_df.empty:
        return html.Div()

    op_rows = []
    for operator, group in named_df.groupby("operator"):
        total = len(group)
        passed = int(group["passed"].sum())
        # Markdown-ссылка на drill-down control chart (pages/operators.py, F2).
        op_link = f"[{operator}](/operators?op={quote_plus(operator)})"
        op_rows.append({"Оператор": op_link, "Звонков": total, "Без нарушений (%)": round(passed / total * 100, 1)})
    if not op_rows:
        return html.Div()

    grid = dag.AgGrid(
        rowData=op_rows,
        columnDefs=[
            {"headerName": "Оператор", "field": "Оператор", "flex": 2, "cellRenderer": "markdown"},
            {"headerName": "Звонков", "field": "Звонков", "flex": 1},
            {"headerName": "Без нарушений (%)", "field": "Без нарушений (%)", "flex": 1.5, **pct_cell(good=80, warn=60)},
        ],
        defaultColDef={"sortable": True},
        style={"height": "280px"},
        className="ag-theme-alpine",
    )
    return _card([section_header("По операторам"), grid])
