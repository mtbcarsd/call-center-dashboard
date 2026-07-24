"""Страница «Справка» — как пользоваться дашбордом, чем он сильнее конкурента,
таблица сравнения и используемый стек.

Статический контент (без БД) — та же структура, что в артефакте, который
показывали пользователю отдельно (2026-07-24), перенесённая в сами компоненты
Dash в стиле остального приложения (COLORS/FONTS, карточки с тенью), а не
отдельный HTML/CSS-документ. Видна всем ролям, включая employee — это просто
справочная информация, не чужие данные.
"""
import dash
from dash import html

from dash_app.colors import COLORS, FONTS
from dash_app.components.page_header import page_header, section_header

dash.register_page(__name__, path="/help", name="Справка", order=7)


def _card(children, extra_style=None):
    style = {
        "background": COLORS["card_bg"],
        "borderRadius": "0.625rem",
        "padding": "1.25rem 1.5rem",
        "boxShadow": "0 1px 3px rgba(0,0,0,0.07), 0 4px 16px rgba(0,0,0,0.04)",
    }
    if extra_style:
        style.update(extra_style)
    return html.Div(children, style=style)


_ROLE_CHIP_COLORS = {
    "executive": (COLORS["primary_light"], COLORS["primary"]),
    "manager": (COLORS["warning_light"], COLORS["warning"]),
    "employee": (COLORS["success_light"], COLORS["success"]),
}


def _role_chip(role: str) -> html.Span:
    bg, fg = _ROLE_CHIP_COLORS[role]
    return html.Span(
        role,
        style={
            "background": bg, "color": fg, "fontWeight": "600", "fontSize": "0.72rem",
            "padding": "0.15rem 0.55rem", "borderRadius": "999px", "whiteSpace": "nowrap",
        },
    )


_ACCOUNTS = [
    ("julia", "6o5OeXT8lPwuMP", "executive", "Все отделы, все страницы"),
    ("boss_oo", "boss_oo", "manager", "Только отдел ОО — фильтр на сервере, не в интерфейсе"),
    ("boss_orkki", "boss_orkki", "manager", "Только отдел ОРККиП"),
    ("sokolova", "sokolova123", "employee", "Только свои звонки — «Мой кабинет», больше ничего"),
]


def _th(text: str) -> html.Th:
    return html.Th(text, style={
        "textAlign": "left", "padding": "0.6rem 0.9rem", "fontFamily": FONTS["mono"],
        "fontSize": "0.68rem", "letterSpacing": "0.08em", "textTransform": "uppercase",
        "color": COLORS["text_secondary"], "borderBottom": f"1px solid {COLORS['border']}",
        "whiteSpace": "nowrap",
    })


def _td(children, **extra) -> html.Td:
    style = {"padding": "0.6rem 0.9rem", "borderBottom": f"1px solid {COLORS['border']}", "fontSize": "0.875rem"}
    style.update(extra)
    return html.Td(children, style=style)


def _credentials_table():
    header = html.Tr([_th(h) for h in ["Логин", "Пароль", "Роль", "Что видно"]])
    rows = [
        html.Tr([
            _td(html.Code(login, style={"fontFamily": FONTS["mono"]})),
            _td(html.Code(pwd, style={"fontFamily": FONTS["mono"]})),
            _td(_role_chip(role)),
            _td(desc, color=COLORS["text_secondary"]),
        ])
        for login, pwd, role, desc in _ACCOUNTS
    ]
    return html.Div(
        html.Table([html.Thead(header), html.Tbody(rows)], style={"width": "100%", "borderCollapse": "collapse"}),
        style={"overflowX": "auto"},
    )


_PAGES_TOUR = [
    ("📊", "Аналитика", "KPI-тайлы, гейджи, графики по темам и отделам, сводная таблица всех звонков.", False),
    ("📁", "Звонки", "Галерея (340+ записей, фильтр «только с аудио»), плеер с перемоткой по клику на реплику, "
                       "редактируемые категория/оператор/QA-оценка, теги, коллекции, комментарии.", False),
    ("🧑‍💼", "Операторы", "Сводная статистика по каждому оператору — AI-оценка, QA-оценка, удовлетворённость клиента.", False),
    ("🏆", "Рейтинг", "% прохождения по каждому пункту чек-листа отдельно, не единой оценкой.", False),
    ("🛡️", "Compliance", "% звонков без нарушений, список найденных нарушений, разбивка по операторам.", False),
    ("📈", "Тренды", "LLM ищет повторяющиеся паттерны в последних звонках и даёт рекомендации супервайзеру.", False),
    ("👥", "Команда", "Кто делает проект.", False),
    ("🙋", "Мой кабинет", "Свои звонки, свой чек-лист, кнопка «получить рекомендации» — LLM разбирает сильные "
                          "и слабые стороны лично для оператора.", True),
]


def _page_tour_grid():
    cards = []
    for icon, title, desc, employee_only in _PAGES_TOUR:
        style = {
            "background": COLORS["card_bg"], "border": f"1px solid {COLORS['border']}", "borderRadius": "0.625rem",
            "padding": "1rem 1.1rem", "flex": "1", "minWidth": "220px",
        }
        if employee_only:
            style["border"] = f"1.5px solid {COLORS['success']}"
        children = [
            html.Div(icon, style={"fontSize": "1.15rem", "marginBottom": "0.35rem"}),
            html.Div(title, style={"fontWeight": "700", "fontSize": "0.9rem", "color": COLORS["text_primary"], "marginBottom": "0.3rem"}),
            html.Div(desc, style={"fontSize": "0.8125rem", "color": COLORS["text_secondary"]}),
        ]
        if employee_only:
            children.append(html.Div(
                "только role=employee",
                style={
                    "fontFamily": FONTS["mono"], "fontSize": "0.65rem", "color": COLORS["success"],
                    "textTransform": "uppercase", "letterSpacing": "0.05em", "marginTop": "0.5rem",
                },
            ))
        cards.append(html.Div(children, style=style))
    return html.Div(cards, style={"display": "flex", "flexWrap": "wrap", "gap": "0.9rem"})


_ADVANTAGES = [
    (
        "Оценка разложена на 4 независимых агента, а не один балл",
        "Классификация темы, чек-лист качества, compliance-проверка и резюме звонка считаются отдельными "
        "LLM-вызовами — видно, где именно проблема, а не общую цифру «7 из 10».",
        None,
    ),
    (
        "Compliance — regex и LLM вместе",
        "Запрещённые формулировки ловятся мгновенно детерминированным regex, более тонкие нарушения "
        "(забыл предупредить о записи разговора) — отдельным LLM-агентом поверх того же транскрипта.",
        None,
    ),
    (
        "Ролевой доступ проверяется на сервере, а не скрывается в интерфейсе",
        "Начальник отдела физически не получит чужие данные, даже если напрямую вызовет внутренний callback "
        "в обход интерфейса — фильтр по отделу встроен в сам SQL-запрос.",
        "У конкурента разграничение ролей в демо не показывали.",
    ),
    (
        "Личный кабинет с LLM-коучингом — самообслуживание оператора",
        "Оператор сам видит свои сильные и слабые места и получает рекомендации, не дожидаясь ручного "
        "разбора от супервайзера.",
        "У конкурента похожая идея — «автоотчёты через LLM», но получает их супервайзер, не сам оператор.",
    ),
    (
        "Плеер привязан к репликам транскрипта",
        "Клик по любой реплике перематывает аудио точно на неё — не нужно на слух искать нужный момент "
        "в получасовом звонке.",
        None,
    ),
    (
        "Чек-лист — открытый список в коде, а не закрытая настройка вендора",
        "Новый пункт чек-листа или изменение веса — правка одного файла (checklist.py), не заявка "
        "в поддержку вендора.",
        None,
    ),
    (
        "Self-hosted, без vendor lock-in",
        "Postgres + FastAPI + Dash, LLM подключается через переменную окружения (сейчас Groq) — можно "
        "сменить провайдера без переписывания системы.",
        None,
    ),
]


def _advantages_list():
    items = []
    for title, desc, vs in _ADVANTAGES:
        children = [
            html.Div(title, style={"fontWeight": "700", "fontSize": "0.95rem", "color": COLORS["text_primary"]}),
            html.Div(desc, style={"fontSize": "0.875rem", "color": COLORS["text_secondary"], "marginTop": "0.25rem"}),
        ]
        if vs:
            children.append(html.Div(
                vs,
                style={"fontSize": "0.8rem", "color": COLORS["neutral"], "fontStyle": "italic", "marginTop": "0.4rem"},
            ))
        items.append(html.Div(
            children,
            style={
                "background": COLORS["card_bg"], "border": f"1px solid {COLORS['border']}",
                "borderLeft": f"3px solid {COLORS['primary_bright']}", "borderRadius": "0.5rem",
                "padding": "0.9rem 1.1rem",
            },
        ))
    return html.Div(items, style={"display": "flex", "flexDirection": "column", "gap": "0.75rem"})


# ── Сравнение с конкурентом ────────────────────────────────────────────────
# Источник: демо-встреча банка с вендором речевой аналитики, 06.07.2026 (см.
# SPEECH_ANALYTICS_IMPROVEMENT_PLAN.md → «Что показал конкурент»). ❔ — не
# демонстрировалось на встрече, поэтому не берёмся утверждать ни «есть», ни «нет».
_STATUS_STYLE = {
    "✅": COLORS["success"], "◐": COLORS["warning"], "❌": COLORS["neutral"], "❔": COLORS["faint"],
}

_COMPARISON_ROWS = [
    ("Чек-лист качества с весами", "✅", "Кастомные категории (checklist.py)",
     "✅", "+ LLM сам пишет промпт, поддержка морфологии слов"),
    ("Пауза/тишина в диалоге", "✅", "silence_pct, pause_count в каждом звонке",
     "✅", "+ настраиваемый порог и льготный период"),
    ("Диаризация оператор/клиент", "✅", "pyannote, включая моно-записи",
     "✅", "Заявлено в демо"),
    ("Compliance-проверка", "✅", "regex (мгновенно) + LLM (нюансы) вместе",
     "❔", "Не детализировано в демо"),
    ("Оценка звонка", "✅", "4 независимых агента, не единый балл",
     "◐", "Единая оценка + copilot-подсказки"),
    ("Ролевой доступ (директор/начальник/сотрудник)", "✅", "Server-side SQL-фильтр",
     "❔", "Не показывали в демо"),
    ("Личный кабинет оператора с рекомендациями", "✅", "LLM-коучинг, self-service",
     "✅", "Автоотчёты через LLM — но для супервайзера, не оператора"),
    ("Ручной override оценки с историей", "◐", "QA-оценка отдельно от AI, с Δ, без версий",
     "✅", "Пометка «M» + история изменений"),
    ("Детекция негатива по позиции в звонке", "❌", "Не реализовано",
     "✅", "Отдельная ML-модель, обучена на размеченных данных"),
    ("AI-копайлот на естественном языке", "❌", "Не реализовано",
     "✅", "«Покажи звонки Иванова за вчера» → фильтр"),
    ("Конструктор графиков", "❌", "Фиксированные страницы",
     "✅", "Drag-and-drop"),
    ("Геймификация/рейтинг среди коллег", "◐", "Рейтинг по чек-листу, без явной геймификации",
     "✅", "Личный рейтинг оператора"),
    ("Тренировочный бот", "❌", "Не реализовано",
     "✅", "Цифровой клиент + суфлёр"),
    ("Архитектура", "✅", "Self-hosted, открытые LLM-провайдеры, без lock-in",
     "❔", "Вендорское решение под ключ"),
]


def _status_cell(icon: str, note: str) -> html.Td:
    return _td(
        html.Div([
            html.Span(icon, style={"color": _STATUS_STYLE.get(icon, COLORS["text_primary"]), "fontWeight": "700", "marginRight": "0.4rem"}),
            html.Span(note, style={"color": COLORS["text_secondary"]}),
        ]),
    )


def _comparison_table():
    header = html.Tr([_th(h) for h in ["Возможность", "Наш дашборд", "Конкурент (демо 06.07.2026)"]])
    rows = [
        html.Tr([
            _td(feature, color=COLORS["text_primary"], fontWeight="600"),
            _status_cell(us_icon, us_note),
            _status_cell(comp_icon, comp_note),
        ])
        for feature, us_icon, us_note, comp_icon, comp_note in _COMPARISON_ROWS
    ]
    legend = html.P(
        "✅ есть  ·  ◐ частично  ·  ❌ нет  ·  ❔ не демонстрировалось, не утверждаем",
        style={"fontSize": "0.78rem", "color": COLORS["faint"], "marginTop": "0.9rem", "marginBottom": "0"},
    )
    return html.Div([
        html.Div(
            html.Table([html.Thead(header), html.Tbody(rows)], style={"width": "100%", "borderCollapse": "collapse"}),
            style={"overflowX": "auto"},
        ),
        legend,
    ])


# ── Технологический стек ───────────────────────────────────────────────────

_STACK = [
    ("Backend / API", "Python 3.12 · FastAPI (api) · Flask-сессии (Dash-сервер)"),
    ("Дашборд / BI", "Plotly Dash · dash-ag-grid · Plotly"),
    ("Распознавание речи", "OpenAI Whisper (транскрипция) · pyannote.audio (диаризация оператор/клиент)"),
    ("LLM-агенты", "4 независимых агента (classifier / quality / compliance / summarizer) + trends + "
                    "coaching, через OpenAI-совместимый API (Groq в проде, Ollama локально)"),
    ("База данных", "PostgreSQL"),
    ("Хранилище аудио", "S3-совместимый бакет (Railway Bucket)"),
    ("Инфраструктура", "Docker · gunicorn · Railway"),
    ("Авторизация", "Flask-сессии + bcrypt, ролевой доступ на сервере"),
]


def _stack_grid():
    rows = [
        html.Div(
            [
                html.Div(layer, style={
                    "fontFamily": FONTS["mono"], "fontSize": "0.72rem", "letterSpacing": "0.06em",
                    "textTransform": "uppercase", "color": COLORS["primary_bright"],
                    "minWidth": "180px", "flexShrink": "0",
                }),
                html.Div(techs, style={"fontSize": "0.9rem", "color": COLORS["text_primary"]}),
            ],
            style={
                "display": "flex", "gap": "1rem", "padding": "0.75rem 0",
                "borderBottom": f"1px solid {COLORS['border']}", "flexWrap": "wrap",
            },
        )
        for layer, techs in _STACK
    ]
    rows[-1].style["borderBottom"] = "none"
    return html.Div(rows)


_GAPS = [
    "Детекция негатива по позиции в звонке (начало/середина/конец)",
    "AI-копайлот на естественном языке",
    "Drag-and-drop конструктор графиков",
    "Тренировочный бот для операторов",
    "Явная геймификация/рейтинг среди коллег",
]


def _gaps_block():
    chips = html.Div(
        [
            html.Span(g, style={
                "background": COLORS["bg"], "border": f"1px solid {COLORS['border']}",
                "color": COLORS["text_secondary"], "fontSize": "0.83rem",
                "padding": "0.5rem 0.85rem", "borderRadius": "0.55rem",
            })
            for g in _GAPS
        ],
        style={"display": "flex", "flexWrap": "wrap", "gap": "0.6rem"},
    )
    note = html.P(
        "Всё это конкурент показывал на демо 06.07.2026 — держим в бэклоге, не выдаём за уже сделанное.",
        style={"fontSize": "0.8125rem", "color": COLORS["neutral"], "marginTop": "1rem", "marginBottom": "0"},
    )
    return html.Div([chips, note])


def layout():
    return html.Div([
        page_header("ℹ️", "Справка", "Как пользоваться дашбордом, чем он сильнее конкурентов и на чём собран."),

        _card([section_header("Доступ"), _credentials_table()], {"marginBottom": "1.5rem"}),
        _card([section_header("Разделы дашборда"), _page_tour_grid()], {"marginBottom": "1.5rem"}),
        _card([section_header("Чем сильнее конкурентов"), _advantages_list()], {"marginBottom": "1.5rem"}),
        _card([section_header("Сравнение с конкурентом"), _comparison_table()], {"marginBottom": "1.5rem"}),
        _card([section_header("Технологический стек"), _stack_grid()], {"marginBottom": "1.5rem"}),
        _card([section_header("Что пока нет — честно"), _gaps_block()], {"marginBottom": "1.5rem"}),

        html.P(
            [
                "Легаси-версия (Streamlit, страховка на откат): ",
                html.Code("call-center-dashboard-production-6a6b.up.railway.app", style={"fontFamily": FONTS["mono"]}),
            ],
            style={"fontSize": "0.8125rem", "color": COLORS["neutral"]},
        ),
    ])
