"""Чистые функции сборки UI для страницы «Звонки» (D4.1-D4.4, полностью).

Вынесены из pages/calls.py по тому же принципу, что trends_logic.py/
coaching_logic.py — тестируются без Dash-app-instance. Галерея + деталка
(D4.1), плеер (D4.2), инлайн-редакторы типа/оператора/QA-оценки (D4.3),
теги/коллекции/комментарии (D4.4) — весь функционал вкладки «Звонки» готов.
"""
import json

import pandas as pd
from dash import dcc, html

from checklist import CHECKLIST
from dash_app.colors import COLORS
from dash_app.components.cell_format import score_dot

_URGENCY_BADGE = {"low": "🟢", "medium": "🟠", "high": "🔴"}
_STATUS_ICON = {"resolved": "✅", "unresolved": "⏳", "escalated": "🚨"}
_SPEAKER_LABEL = {"operator": "🧑‍💼 Оператор", "client": "🙋 Клиент", "unknown": "❔"}


def _is_missing(value) -> bool:
    if value is None:
        return True
    try:
        return bool(pd.isna(value))
    except TypeError:
        return False


def _text(value, default="—") -> str:
    return default if _is_missing(value) or value == "" else str(value)


CARD_STYLE = {
    "background": "white",
    "borderRadius": "0.625rem",
    "padding": "1rem 1.125rem",
    "boxShadow": "0 1px 3px rgba(0,0,0,0.07), 0 4px 16px rgba(0,0,0,0.04)",
    "display": "flex",
    "flexDirection": "column",
    "gap": "0.35rem",
    "flex": "1",
    "minWidth": "260px",
    "maxWidth": "360px",
}


def render_call_card(row: dict, open_btn_id: dict) -> html.Div:
    """Одна карточка галереи. open_btn_id — pattern-matching id кнопки «Открыть»
    (например {"type": "open-call-btn", "index": file_name})."""
    score = row.get("agent_performance_score")
    score_text = f"{score:.0f}/10" if not _is_missing(score) else "—"
    operator = row.get("operator_name")
    has_operator = not _is_missing(operator) and operator != ""
    has_override = not _is_missing(row.get("call_type_override")) and row.get("call_type_override") != ""
    type_label = row.get("call_type_effective") or row.get("call_type")

    children = [
        html.Div(
            _text(row.get("call_topic")),
            style={"fontWeight": "700", "color": COLORS["text_primary"], "fontSize": "0.95rem"},
        ),
        html.Div(
            f"{_text(row.get('department'))} · {_URGENCY_BADGE.get(row.get('urgency'), '⚪')} {_text(row.get('urgency'))}",
            style={"color": COLORS["text_secondary"], "fontSize": "0.8rem"},
        ),
        html.Div(
            f"{'🏷️ ' if has_override else ''}{_text(type_label)}",
            style={"color": COLORS["text_secondary"], "fontSize": "0.8rem"},
        ),
    ]
    if has_operator:
        children.append(html.Div(
            f"🧑‍💼 {operator}",
            style={"color": COLORS["text_secondary"], "fontSize": "0.8rem"},
        ))
    children.append(html.Div(
        f"{score_dot(score)} Оператор {score_text}",
        style={"color": COLORS["text_primary"], "fontSize": "0.85rem", "marginTop": "0.15rem"},
    ))
    children.append(html.Div(
        f"{_STATUS_ICON.get(row.get('resolution_status'), '❔')} {_text(row.get('resolution_status'))}",
        style={"color": COLORS["text_secondary"], "fontSize": "0.8rem"},
    ))
    children.append(html.Button(
        "Открыть",
        id=open_btn_id,
        n_clicks=0,
        style={
            "marginTop": "0.5rem",
            "background": COLORS["primary_bright"],
            "color": "white",
            "border": "none",
            "borderRadius": "0.4rem",
            "padding": "0.4rem 0.75rem",
            "fontWeight": "600",
            "fontSize": "0.8125rem",
            "cursor": "pointer",
            "fontFamily": "inherit",
        },
    ))

    return html.Div(children, style=CARD_STYLE)


def _detail_row(label: str, value: str) -> html.Div:
    return html.Div(
        [
            html.Span(f"{label}: ", style={"fontWeight": "600", "color": COLORS["text_primary"]}),
            html.Span(value, style={"color": COLORS["text_secondary"]}),
        ],
        style={"marginBottom": "0.4rem", "fontSize": "0.875rem"},
    )


AUDIO_PLAYER_ID = "call-audio-player"

_EDIT_INPUT_STYLE = {
    "border": f"1.5px solid {COLORS['border']}",
    "borderRadius": "0.375rem",
    "padding": "0.3rem 0.5rem",
    "fontSize": "0.8125rem",
    "fontFamily": "inherit",
    "flex": "1",
    "minWidth": "120px",
}
_EDIT_SAVE_BTN_STYLE = {
    "background": COLORS["primary_bright"],
    "color": "white",
    "border": "none",
    "borderRadius": "0.375rem",
    "padding": "0.3rem 0.75rem",
    "fontWeight": "600",
    "fontSize": "0.75rem",
    "cursor": "pointer",
    "fontFamily": "inherit",
    "whiteSpace": "nowrap",
}
_EDIT_CONFIRM_BTN_STYLE = {**_EDIT_SAVE_BTN_STYLE, "background": COLORS["success"]}


def _render_type_editor(row: dict) -> html.Div:
    """Тип звонка (D4.3): AI-категория, подтверждаемая или исправляемая вручную —
    id-компонентов фиксированные (не pattern-matching), т.к. в момент рендера
    существует ровно одна деталка на странице (см. AUDIO_PLAYER_ID выше — тот
    же принцип)."""
    has_override = not _is_missing(row.get("call_type_override")) and row.get("call_type_override") != ""
    status = (
        f"🏷️ подтверждено · AI предложил: {_text(row.get('call_type'))}"
        if has_override else "AI, не подтверждено"
    )
    current_value = row.get("call_type_override") if has_override else row.get("call_type")

    controls = [
        dcc.Input(
            id="calls-type-input", type="text",
            value=_text(current_value, ""), style=_EDIT_INPUT_STYLE,
        ),
        html.Button("💾 Сохранить", id="calls-type-save-btn", n_clicks=0, style=_EDIT_SAVE_BTN_STYLE),
    ]
    if not has_override:
        controls.append(html.Button(
            "✅ Подтвердить как есть", id="calls-type-confirm-btn", n_clicks=0,
            style=_EDIT_CONFIRM_BTN_STYLE,
        ))

    return html.Div(
        [
            html.Div([
                html.Span("Тип: ", style={"fontWeight": "600", "color": COLORS["text_primary"]}),
                html.Span(status, style={"color": COLORS["text_secondary"], "fontSize": "0.8rem"}),
            ]),
            html.Div(controls, style={"display": "flex", "gap": "0.4rem", "marginTop": "0.3rem", "flexWrap": "wrap"}),
        ],
        style={"marginBottom": "0.6rem", "fontSize": "0.875rem"},
    )


def _render_operator_editor(row: dict) -> html.Div:
    """Оператор звонка (D4.3) — свободный текст, без справочника операторов
    (см. комментарий в db.py про 10+ звонков и избыточность отдельной таблицы)."""
    current = row.get("operator_name")
    return html.Div(
        [
            html.Div([
                html.Span("Оператор: ", style={"fontWeight": "600", "color": COLORS["text_primary"]}),
                html.Span(_text(current), style={"color": COLORS["text_secondary"]}),
            ]),
            html.Div(
                [
                    dcc.Input(
                        id="calls-operator-input", type="text",
                        value=current if not _is_missing(current) else "",
                        placeholder="Имя оператора", style=_EDIT_INPUT_STYLE,
                    ),
                    html.Button("💾 Сохранить", id="calls-operator-save-btn", n_clicks=0, style=_EDIT_SAVE_BTN_STYLE),
                ],
                style={"display": "flex", "gap": "0.4rem", "marginTop": "0.3rem"},
            ),
        ],
        style={"marginBottom": "0.6rem", "fontSize": "0.875rem"},
    )


def _render_qa_editor(row: dict) -> html.Div:
    """QA-оценка (D4.3) — ручная оценка проверяющего, отдельно от AI-оценки по
    чек-листу; показываем расхождение (Δ), как в Streamlit-версии."""
    qa = row.get("qa_score")
    agent_score = row.get("agent_performance_score")
    if not _is_missing(qa):
        delta = qa - (agent_score or 0)
        status = f"{qa:.1f}/10 (Δ {delta:+.1f} к AI)"
        default_value = qa
    else:
        status = "— (не проставлена)"
        default_value = agent_score if not _is_missing(agent_score) else 0

    return html.Div(
        [
            html.Div([
                html.Span("QA-оценка: ", style={"fontWeight": "600", "color": COLORS["text_primary"]}),
                html.Span(status, style={"color": COLORS["text_secondary"]}),
            ]),
            html.Div(
                [
                    dcc.Input(
                        id="calls-qa-input", type="number", min=0, max=10, step=0.5,
                        value=default_value, style=_EDIT_INPUT_STYLE,
                    ),
                    html.Button("💾 Сохранить", id="calls-qa-save-btn", n_clicks=0, style=_EDIT_SAVE_BTN_STYLE),
                ],
                style={"display": "flex", "gap": "0.4rem", "marginTop": "0.3rem"},
            ),
        ],
        style={"marginBottom": "0.6rem", "fontSize": "0.875rem"},
    )


def _render_label_editor(
    icon: str, title: str, singular: str, current: list[str], all_options: list[str],
    dropdown_id: str, new_input_id: str, add_btn_id: str, save_btn_id: str,
) -> html.Div:
    """Теги/коллекции (D4.4) — выбор из существующих (dcc.Dropdown multi) +
    отдельное поле для нового значения, тот же паттерн, что render_label_editor
    в dashboard.py, но без auto-save на каждое изменение dropdown: явная
    кнопка «Сохранить выбор», как у остальных редакторов D4.3 — единый паттерн
    вместо двух разных (auto-save для тегов, explicit-save для типа/QA).

    singular — форма для плейсхолдера поля добавления («тег»/«коллекция»);
    выводить её из title автоматическим отсечением окончания не стал —
    «Коллекции» → «коллекци» таким способом получается некорректно."""
    options = sorted(set(all_options) | set(current))
    return html.Div(
        [
            html.Strong(f"{icon} {title}", style={"display": "block", "marginBottom": "0.3rem", "fontSize": "0.875rem"}),
            dcc.Dropdown(
                id=dropdown_id,
                options=[{"label": o, "value": o} for o in options],
                value=current, multi=True, placeholder=f"Выбрать {title.lower()}...",
                style={"fontSize": "0.8125rem"},
            ),
            html.Div(
                [
                    dcc.Input(
                        id=new_input_id, type="text", value="", placeholder=f"Новый {singular}...",
                        style=_EDIT_INPUT_STYLE,
                    ),
                    html.Button("➕ Добавить", id=add_btn_id, n_clicks=0, style=_EDIT_SAVE_BTN_STYLE),
                    html.Button("💾 Сохранить выбор", id=save_btn_id, n_clicks=0, style=_EDIT_SAVE_BTN_STYLE),
                ],
                style={"display": "flex", "gap": "0.4rem", "marginTop": "0.3rem", "flexWrap": "wrap"},
            ),
        ],
        style={"marginBottom": "0.75rem"},
    )


def render_comments_section(comments: list[dict]) -> html.Div:
    """Список комментариев + форма добавления (D4.4)."""
    if not comments:
        items = [html.P(
            "Пока нет комментариев.",
            style={"color": COLORS["text_secondary"], "fontStyle": "italic", "fontSize": "0.875rem"},
        )]
    else:
        items = []
        for c in comments:
            created = c.get("created_at")
            created_text = created.strftime("%d.%m.%Y %H:%M") if hasattr(created, "strftime") else _text(created, "")
            items.append(html.Div(
                [
                    html.Div([
                        html.Strong(c.get("author") or "Аноним", style={"fontSize": "0.8125rem"}),
                        html.Span(f" · {created_text}", style={"color": COLORS["text_secondary"], "fontSize": "0.75rem"}),
                    ]),
                    html.P(c.get("text", ""), style={"margin": "0.2rem 0 0 0", "fontSize": "0.875rem"}),
                ],
                style={
                    "marginBottom": "0.6rem", "paddingBottom": "0.6rem",
                    "borderBottom": f"1px solid {COLORS['border']}",
                },
            ))

    return html.Div(
        [
            html.Strong("💬 Комментарии", style={"display": "block", "marginBottom": "0.5rem"}),
            html.Div(items),
            dcc.Textarea(
                id="calls-new-comment-input", value="", placeholder="Новый комментарий...",
                style={
                    "width": "100%", "minHeight": "4rem", "fontFamily": "inherit",
                    "fontSize": "0.875rem", "border": f"1.5px solid {COLORS['border']}",
                    "borderRadius": "0.375rem", "padding": "0.5rem", "marginTop": "0.5rem",
                },
            ),
            html.Button(
                "💬 Добавить комментарий", id="calls-add-comment-btn", n_clicks=0,
                style={**_EDIT_SAVE_BTN_STYLE, "marginTop": "0.5rem"},
            ),
        ],
        style={"marginTop": "1.25rem"},
    )


def render_call_detail(row: dict, audio_url: str | None = None) -> html.Div:
    """Деталка звонка: параметры/чек-лист/compliance (D4.1) + плеер и
    перемотка по клику на реплику (D4.2) + инлайн-редакторы типа/оператора/
    QA-оценки/тегов/коллекций + комментарии (D4.3-D4.4) — полный функционал.

    audio_url — presigned-ссылка на аудио (storage.presigned_url), вызывающая
    сторона (pages/calls.py) сама решает, доступно ли аудио — эта функция
    остаётся чистой (без обращений к S3/БД), как и её сиблинги
    trends_logic.py/coaching_logic.py.
    """
    left_col = [
        _detail_row("Отдел", _text(row.get("department"))),
        _render_type_editor(row),
        _render_operator_editor(row),
        _render_label_editor(
            "🔖", "Теги", "тег", row.get("tags") or [], row.get("all_tags") or [],
            "calls-tags-dropdown", "calls-tags-new-input", "calls-tags-add-btn", "calls-tags-save-btn",
        ),
        _render_label_editor(
            "📦", "Коллекции", "коллекция", row.get("collections") or [], row.get("all_collections") or [],
            "calls-collections-dropdown", "calls-collections-new-input",
            "calls-collections-add-btn", "calls-collections-save-btn",
        ),
        _detail_row("Намерение клиента", _text(row.get("customer_intent"))),
        _detail_row("Срочность", _text(row.get("urgency"))),
        _detail_row("Статус", _text(row.get("resolution_status"))),
        _detail_row(
            "Оценка оператора (чек-лист)",
            f"{row.get('agent_performance_score')}/10" if not _is_missing(row.get("agent_performance_score")) else "—",
        ),
        _render_qa_editor(row),
    ]

    left_col.append(_detail_row(
        "Удовл. клиента",
        f"{row.get('customer_satisfaction')}/10" if not _is_missing(row.get("customer_satisfaction")) else "—",
    ))
    left_col.append(_detail_row("Эскалация", "Да" if row.get("escalation_flag") else "Нет"))

    if not _is_missing(row.get("silence_pct")):
        pause_count = row.get("pause_count")
        pause_text = f" ({int(pause_count)} пауз)" if not _is_missing(pause_count) else ""
        left_col.append(_detail_row("Тишина в диалоге", f"{row['silence_pct']:.0f}%{pause_text}"))
    if not _is_missing(row.get("operator_talk_ratio")):
        left_col.append(_detail_row("Доля речи оператора", f"{row['operator_talk_ratio']:.0f}%"))

    key_topics = row.get("key_topics")
    if key_topics:
        try:
            topics_list = json.loads(key_topics) if isinstance(key_topics, str) else key_topics
        except (TypeError, json.JSONDecodeError):
            topics_list = []
        if topics_list:
            left_col.append(html.Div(
                [html.Strong("Ключевые темы:"), html.Ul(
                    [html.Li(t, style={"fontSize": "0.8125rem"}) for t in topics_list],
                    style={"margin": "0.25rem 0 0 0", "paddingLeft": "1.25rem"},
                )],
                style={"marginBottom": "0.5rem", "fontSize": "0.875rem"},
            ))

    checklist_json = row.get("checklist_json")
    if checklist_json:
        try:
            checklist_result = json.loads(checklist_json) if isinstance(checklist_json, str) else checklist_json
        except (TypeError, json.JSONDecodeError):
            checklist_result = {}
        if checklist_result:
            items = [
                html.Li(
                    f"{'✅' if checklist_result.get(item['key']) else '❌'} {item['label']} ({item['weight']})",
                    style={"fontSize": "0.8125rem", "listStyle": "none"},
                )
                for item in CHECKLIST
            ]
            left_col.append(html.Div(
                [html.Strong("Чек-лист:"), html.Ul(items, style={"margin": "0.25rem 0 0 0", "padding": "0"})],
                style={"marginBottom": "0.5rem", "fontSize": "0.875rem"},
            ))

    compliance_json = row.get("compliance_json")
    if compliance_json:
        try:
            compliance = json.loads(compliance_json) if isinstance(compliance_json, str) else compliance_json
        except (TypeError, json.JSONDecodeError):
            compliance = None
        if compliance is not None:
            issues = compliance.get("issues") or compliance.get("llm_issues") or []
            if issues:
                left_col.append(html.Div(
                    [
                        html.Strong("⚠️ Compliance — найдены замечания:"),
                        html.Ul(
                            [html.Li(i, style={"fontSize": "0.8125rem"}) for i in issues],
                            style={"margin": "0.25rem 0 0 0", "paddingLeft": "1.25rem"},
                        ),
                    ],
                    style={
                        "background": COLORS["warning_light"], "padding": "0.5rem 0.75rem",
                        "borderRadius": "0.375rem", "marginBottom": "0.5rem", "fontSize": "0.875rem",
                    },
                ))
            else:
                left_col.append(html.Div(
                    "✅ Compliance — нарушений не найдено",
                    style={
                        "background": COLORS["success_light"], "padding": "0.5rem 0.75rem",
                        "borderRadius": "0.375rem", "marginBottom": "0.5rem", "fontSize": "0.875rem",
                        "color": "#166534",
                    },
                ))

    # Метрики-only синтетика (сессия 2026-07-22): у неё нет ни аудио, ни
    # транскрипта — только сгенерированные оценки. Отличаем от реального звонка
    # с упавшей заливкой в S3 (там transcript_text/segments всё равно есть).
    has_no_audio_or_transcript = (
        audio_url is None
        and _is_missing(row.get("transcript_text"))
        and not row.get("segments")
    )

    right_col = []
    has_summary = not _is_missing(row.get("call_summary"))
    if has_summary or has_no_audio_or_transcript:
        summary_children = [html.Strong("Резюме")]
        if has_summary:
            summary_children.append(html.P(row["call_summary"], style={"margin": "0.35rem 0 0 0"}))
        if has_no_audio_or_transcript:
            summary_children.append(html.P(
                "ℹ️ Ни аудио, ни транскрипта для этого звонка нет — похоже на "
                "синтетическую тестовую запись (сгенерированы только метрики/оценки, "
                "без реального содержания разговора).",
                style={
                    "margin": "0.35rem 0 0 0", "fontSize": "0.8125rem",
                    "color": COLORS["text_secondary"], "fontStyle": "italic",
                },
            ))
        right_col.append(html.Div(
            summary_children,
            style={
                "background": COLORS["primary_light"], "padding": "0.75rem",
                "borderRadius": "0.375rem", "marginBottom": "1rem", "fontSize": "0.875rem",
            },
        ))

    right_col.append(html.Div(
        [
            html.Strong("📄 Транскрипт"),
            html.Span(
                " (клик по ▶ перематывает плеер на реплику)" if audio_url else "",
                style={"color": COLORS["text_secondary"], "fontSize": "0.75rem", "fontWeight": "400"},
            ),
        ],
        style={"marginBottom": "0.5rem"},
    ))
    segments = row.get("segments")  # список dict {speaker, start_sec, end_sec, text} или None
    if segments:
        seg_rows = []
        for seg in segments:
            row_children = []
            if audio_url:
                # Pattern-matching id со значением-float ломает внутренний парсер
                # триггера в dash-renderer (Dash 2.18): он режет prop_id по первой
                # точке, попадая внутрь самого числа (например "6.14"), а не на
                # границу id/prop-имени. Поэтому время — целые сантисекунды.
                row_children.append(html.Button(
                    "▶",
                    id={"type": "seek-btn", "time_cs": round((seg.get("start_sec") or 0) * 100)},
                    n_clicks=0,
                    title="Перемотать плеер сюда",
                    style={
                        "background": COLORS["primary_light"], "color": COLORS["primary_bright"],
                        "border": "none", "borderRadius": "50%", "width": "1.75rem", "height": "1.75rem",
                        "cursor": "pointer", "flexShrink": "0", "fontSize": "0.75rem",
                    },
                ))
            row_children.append(html.Span([
                html.Strong(f"{_SPEAKER_LABEL.get(seg.get('speaker'), seg.get('speaker'))} "),
                html.Span(f"{seg.get('start_sec', 0):.0f}–{seg.get('end_sec', 0):.0f}с: ",
                           style={"color": COLORS["text_secondary"], "fontSize": "0.8rem"}),
                seg.get("text", ""),
            ], style={"fontSize": "0.875rem"}))
            seg_rows.append(html.Div(
                row_children,
                style={"display": "flex", "alignItems": "flex-start", "gap": "0.5rem", "marginBottom": "0.5rem"},
            ))
        right_col.append(html.Div(seg_rows))
    else:
        right_col.append(html.P(
            _text(row.get("transcript_text"), "Транскрипт недоступен."),
            style={"whiteSpace": "pre-wrap", "fontSize": "0.875rem", "color": COLORS["text_secondary"]},
        ))

    right_col.append(render_comments_section(row.get("comments") or []))

    if audio_url:
        audio_block = html.Audio(
            id=AUDIO_PLAYER_ID, src=audio_url, controls=True,
            style={"width": "100%", "marginBottom": "1.25rem"},
        )
    else:
        audio_block = html.P(
            "🔇 Аудио для этого звонка недоступно (хранилище не настроено или файл не заливался).",
            style={"color": COLORS["text_secondary"], "fontSize": "0.8125rem", "marginBottom": "1.25rem"},
        )

    return html.Div(
        [
            html.H3(_text(row.get("call_topic")), style={"color": COLORS["text_primary"], "marginTop": "0"}),
            audio_block,
            html.Div(
                [
                    html.Div(left_col, style={"flex": "1", "minWidth": "280px"}),
                    html.Div(right_col, style={"flex": "1.5", "minWidth": "320px"}),
                ],
                style={"display": "flex", "gap": "2rem", "flexWrap": "wrap"},
            ),
        ],
        style={
            "background": "white", "borderRadius": "0.625rem", "padding": "1.5rem",
            "boxShadow": "0 1px 3px rgba(0,0,0,0.07), 0 4px 16px rgba(0,0,0,0.04)",
        },
    )
