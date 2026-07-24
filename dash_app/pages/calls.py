"""Страница «Звонки» (D4.1 + D4.2) — галерея карточек + деталка с плеером.

Эквивалент вкладки «📁 Звонки» в dashboard.py:393-660, но пока без инлайн-
редакторов (D4.3) и тегов/коллекций/комментариев (D4.4) — эти слои
добавляются отдельными шагами поверх этой страницы.

Паттерн выбора карточки: клик по «Открыть» (id — pattern-matching dict) →
callback А определяет file_name через ctx.triggered_id и кладёт в dcc.Store →
callback Б перечитывает эту строку из БД (с тем же department-скоупом, что и
галерея) и рендерит деталку. Два отдельных callback'а вместо одного — тот же
dcc.Store потом переиспользуют инлайн-редакторы (D4.3), не трогая колбэк А.

Перемотка плеера по клику на реплику (D4.2) — единственное место в Dash-части
проекта, где нужен clientside_callback: currentTime у <audio> нельзя выставить
обычным Python Output (Dash-компонент html.Audio не даёт controllable-проп для
этого), поэтому JS напрямую находит элемент по id и двигает playhead.
"""
import dash
from dash import ALL, Input, Output, State, callback, ctx, dcc, html

from dash_app.auth import get_current_department
from dash_app.calls_logic import AUDIO_PLAYER_ID, render_call_card, render_call_detail
from dash_app.colors import COLORS
from dash_app.data import load_calls, load_segments
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


@callback(
    Output("calls-detail-container", "children"),
    Input("calls-selected-file", "data"),
    prevent_initial_call=True,
)
def show_call_detail(file_name):
    if not file_name:
        return dash.no_update

    # Перечитываем с тем же department-скоупом, что и галерея — сотрудник со
    # стороны manager не откроет чужой звонок, даже подменив id в dcc.Store.
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
