"""Страница «Команда разработчиков» (D1.2).

Эквивалент вкладки «👥 Команда» (dashboard.py:883-907).
"""
import dash
from dash import html

from dash_app.colors import COLORS

dash.register_page(__name__, path="/team", name="Команда", order=5)

_TEAM = [
    {"name": "Ксения", "role": "Data Scientist", "icon": "🔬"},
    {"name": "Алексей", "role": "Data Scientist", "icon": "🔬"},
    {"name": "Андрей", "role": "Data Scientist", "icon": "🔬"},
]


def layout():
    member_cards = [
        html.Div(
            [
                html.Div(m["icon"], style={"fontSize": "2.5rem", "marginBottom": "0.5rem"}),
                html.Div(
                    m["name"],
                    style={"fontWeight": "700", "color": COLORS["text_primary"], "fontSize": "1rem"},
                ),
                html.Div(
                    m["role"],
                    style={"color": COLORS["text_secondary"], "fontSize": "0.85rem", "marginTop": "0.25rem"},
                ),
            ],
            style={
                "background": "white",
                "borderRadius": "0.625rem",
                "padding": "1.5rem",
                "textAlign": "center",
                "flex": "1",
                "minWidth": "150px",
                "boxShadow": "0 1px 3px rgba(0,0,0,0.07)",
                "borderTop": f"4px solid {COLORS['primary_bright']}",
            },
        )
        for m in _TEAM
    ]

    org_card = html.Div(
        [
            html.H3(
                "🏢 ЦАР · ds-team prospects, (песочница)",
                style={"fontWeight": "700", "color": COLORS["text_primary"],
                       "margin": "0 0 0.75rem 0", "fontSize": "1.1rem"},
            ),
            html.P("МТБанк, Беларусь",
                   style={"fontWeight": "600", "color": COLORS["text_secondary"], "margin": "0 0 0.5rem 0"}),
            html.P("👩‍🏫 Воспитатель: Пилипенко Светлана",
                   style={"margin": "0.25rem 0", "color": COLORS["text_secondary"]}),
            html.P("🤱 Нянечка: Гуринович Анастасия",
                   style={"margin": "0.25rem 0", "color": COLORS["text_secondary"]}),
        ],
        style={
            "background": "white",
            "borderRadius": "0.625rem",
            "padding": "1.5rem",
            "boxShadow": "0 1px 3px rgba(0,0,0,0.07)",
            "marginBottom": "1.5rem",
            "borderLeft": f"4px solid {COLORS['primary_bright']}",
        },
    )

    return html.Div([
        html.H2(
            "👥 Команда разработчиков",
            style={"color": COLORS["text_primary"], "margin": "0 0 1.5rem 0", "fontWeight": "700"},
        ),
        org_card,
        html.H4(
            "Участники команды",
            style={"color": COLORS["text_primary"], "fontWeight": "600", "marginBottom": "1rem"},
        ),
        html.Div(member_cards, style={"display": "flex", "gap": "1rem", "flexWrap": "wrap"}),
    ])
