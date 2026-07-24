"""Страница «Звонки» (D4.1-D4.3) — галерея карточек + деталка с плеером и
инлайн-редакторами. Эквивалент вкладки «📁 Звонки» в dashboard.py:393-660, но
пока без тегов/коллекций/комментариев (D4.4) — следующий шаг поверх этого.

Паттерн выбора карточки: клик по «Открыть» (id — pattern-matching dict) →
callback А определяет file_name через ctx.triggered_id и кладёт в dcc.Store →
callback Б перечитывает эту строку из БД (с тем же department-скоупом, что и
галерея) и рендерит деталку. Два отдельных callback'а вместо одного — тот же
dcc.Store переиспользуют инлайн-редакторы (D4.3): после сохранения они не
трогают select_call, а просто заново вызывают ту же _load_and_render_detail().

Перемотка плеера по клику на реплику (D4.2) — единственное место в Dash-части
проекта, где нужен clientside_callback: currentTime у <audio> нельзя выставить
обычным Python Output (Dash-компонент html.Audio не даёт controllable-проп для
этого), поэтому JS напрямую находит элемент по id и двигает playhead.

Редакторы (D4.3) используют фиксированные id (не pattern-matching) — в любой
момент на странице существует ровно одна деталка, поэтому MATCH/ALL не нужен;
он остаётся только там, где реально бывает много одинаковых компонентов
одновременно (карточки галереи, кнопки перемотки по репликам).
"""
import dash
from dash import ALL, Input, Output, State, callback, ctx, dcc, html

from dash_app.auth import get_current_department
from dash_app.calls_logic import AUDIO_PLAYER_ID, render_call_card, render_call_detail
from dash_app.colors import COLORS
from dash_app.data import (
    load_calls,
    load_segments,
    set_call_type_override,
    set_operator_name,
    set_qa_score,
)
from storage import presigned_url

dash.register_page(__name__, path="/calls", name="Звонки", order=1)

# Галерея без пагинации при 300+ звонках превращается в страницу на 18000px
# (та же проблема, что была у analytics.py/compliance.py на прошлой сессии) —
# показываем порциями с кнопкой «Показать ещё» вместо рендера всего сразу.
_PAGE_SIZE = 24

_SHOW_MORE_BTN_STYLE = {
    "background": "white",
    "color": COLORS["primary_bright"],
    "border": f"1.5px solid {COLORS['primary_bright']}",
    "borderRadius": "0.5rem",
    "padding": "0.5rem 1.25rem",
    "fontWeight": "600",
    "fontSize": "0.875rem",
    "cursor": "pointer",
    "fontFamily": "inherit",
}


def layout():
    df = load_calls(department=get_current_department())

    return html.Div([
        html.H2(
            "📁 Звонки",
            style={"color": COLORS["text_primary"], "margin": "0 0 0.25rem 0", "fontWeight": "700"},
        ),
        html.P(
            f"{len(df)} звонков",
            style={"color": COLORS["text_secondary"], "margin": "0 0 1.5rem 0", "fontSize": "0.875rem"},
        ),
        html.Div(id="calls-gallery-container"),
        html.Div(
            html.Button(
                "Показать ещё", id="calls-show-more-btn", n_clicks=0, style=_SHOW_MORE_BTN_STYLE,
            ),
            style={"textAlign": "center", "marginBottom": "1.5rem"},
        ),
        dcc.Store(id="calls-gallery-limit", data=_PAGE_SIZE),
        dcc.Store(id="calls-selected-file"),
        dcc.Store(id="calls-seek-dummy"),  # обязательный Output для clientside-перемотки, значение не используется
        html.Div(
            html.P(
                "Выберите звонок в галерее выше, чтобы открыть деталку.",
                style={"color": COLORS["text_secondary"]},
            ),
            id="calls-detail-container",
        ),
    ])


@callback(
    Output("calls-gallery-limit", "data"),
    Input("calls-show-more-btn", "n_clicks"),
    State("calls-gallery-limit", "data"),
    prevent_initial_call=True,
)
def increase_gallery_limit(_n_clicks, current_limit):
    return (current_limit or _PAGE_SIZE) + _PAGE_SIZE


@callback(
    Output("calls-gallery-container", "children"),
    Output("calls-show-more-btn", "style"),
    Input("calls-gallery-limit", "data"),
)
def render_gallery(limit):
    df = load_calls(department=get_current_department())
    limit = limit or _PAGE_SIZE
    visible = df.iloc[:limit]

    cards = [
        render_call_card(row.to_dict(), {"type": "open-call-btn", "index": row["file_name"]})
        for _, row in visible.iterrows()
    ]
    gallery = html.Div(
        cards if cards else [html.P(
            "Нет звонков по текущим данным.", style={"color": COLORS["text_secondary"]},
        )],
        style={"display": "flex", "gap": "1rem", "flexWrap": "wrap", "marginBottom": "1rem"},
    )

    btn_style = dict(_SHOW_MORE_BTN_STYLE)
    if limit >= len(df):
        btn_style["display"] = "none"
    return gallery, btn_style


@callback(
    Output("calls-selected-file", "data"),
    Input({"type": "open-call-btn", "index": ALL}, "n_clicks"),
    prevent_initial_call=True,
)
def select_call(_n_clicks_all):
    triggered = ctx.triggered_id
    if not triggered or not any(_n_clicks_all):
        return dash.no_update
    return triggered["index"]


def _load_and_render_detail(file_name):
    """Общая логика для show_call_detail и всех save-колбэков редакторов
    (D4.3): перечитать строку с department-скоупом и собрать деталку."""
    # Перечитываем с тем же department-скоупом, что и галерея — сотрудник со
    # стороны manager не откроет (и не отредактирует) чужой звонок, даже
    # подменив id в dcc.Store/послав запрос к чужому callback напрямую.
    df = load_calls(department=get_current_department())
    match = df[df["file_name"] == file_name]
    if match.empty:
        return html.P(
            "Этот звонок недоступен (не проходит по фильтрам роли).",
            style={"color": COLORS["danger"]},
        )

    row = match.iloc[0].to_dict()
    segments_df = load_segments(file_name)
    if not segments_df.empty:
        row["segments"] = segments_df.to_dict("records")

    audio_url = presigned_url(row.get("audio_key"))
    return render_call_detail(row, audio_url=audio_url)


@callback(
    Output("calls-detail-container", "children"),
    Input("calls-selected-file", "data"),
    prevent_initial_call=True,
)
def show_call_detail(file_name):
    if not file_name:
        return dash.no_update
    return _load_and_render_detail(file_name)


# ── Инлайн-редакторы: тип/оператор/QA-оценка (D4.3) ──────────────────────────
# Каждый save-колбэк: проверяет, что file_name всё ещё в скоупе роли (защита от
# прямого вызова с чужим file_name), пишет в БД, затем заново рендерит деталку
# тем же _load_and_render_detail() — тот же Output, что у show_call_detail,
# поэтому нужен allow_duplicate=True.

def _file_in_scope(file_name: str) -> bool:
    df = load_calls(department=get_current_department())
    return file_name in df["file_name"].values


@callback(
    Output("calls-detail-container", "children", allow_duplicate=True),
    Input("calls-type-confirm-btn", "n_clicks"),
    State("calls-selected-file", "data"),
    prevent_initial_call=True,
)
def confirm_call_type(_n_clicks, file_name):
    if not file_name or not _file_in_scope(file_name):
        return dash.no_update
    df = load_calls(department=get_current_department())
    ai_type = df.loc[df["file_name"] == file_name, "call_type"].iloc[0]
    set_call_type_override(file_name, ai_type)
    return _load_and_render_detail(file_name)


@callback(
    Output("calls-detail-container", "children", allow_duplicate=True),
    Input("calls-type-save-btn", "n_clicks"),
    State("calls-selected-file", "data"),
    State("calls-type-input", "value"),
    prevent_initial_call=True,
)
def save_call_type(_n_clicks, file_name, new_value):
    if not file_name or not _file_in_scope(file_name) or not (new_value or "").strip():
        return dash.no_update
    set_call_type_override(file_name, new_value.strip())
    return _load_and_render_detail(file_name)


@callback(
    Output("calls-detail-container", "children", allow_duplicate=True),
    Input("calls-operator-save-btn", "n_clicks"),
    State("calls-selected-file", "data"),
    State("calls-operator-input", "value"),
    prevent_initial_call=True,
)
def save_operator_name(_n_clicks, file_name, new_value):
    if not file_name or not _file_in_scope(file_name):
        return dash.no_update
    set_operator_name(file_name, (new_value or "").strip() or None)
    return _load_and_render_detail(file_name)


@callback(
    Output("calls-detail-container", "children", allow_duplicate=True),
    Input("calls-qa-save-btn", "n_clicks"),
    State("calls-selected-file", "data"),
    State("calls-qa-input", "value"),
    prevent_initial_call=True,
)
def save_qa_score(_n_clicks, file_name, new_value):
    if not file_name or not _file_in_scope(file_name) or new_value is None:
        return dash.no_update
    try:
        score = max(0.0, min(10.0, float(new_value)))
    except (TypeError, ValueError):
        return dash.no_update
    set_qa_score(file_name, score)
    return _load_and_render_detail(file_name)


# ── Перемотка плеера по клику на реплику (D4.2) ───────────────────────────────

dash.clientside_callback(
    f"""
    function(n_clicks_list) {{
        const trig = window.dash_clientside.callback_context.triggered_id;
        if (!trig) {{ return window.dash_clientside.no_update; }}
        const audio = document.getElementById('{AUDIO_PLAYER_ID}');
        if (audio) {{
            audio.currentTime = trig.time_cs / 100;
            audio.play();
        }}
        return window.dash_clientside.no_update;
    }}
    """,
    Output("calls-seek-dummy", "data"),
    Input({"type": "seek-btn", "time_cs": ALL}, "n_clicks"),
    prevent_initial_call=True,
)
