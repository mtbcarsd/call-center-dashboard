"""Чистая функция сборки UI для страницы Тренды.

Вынесена из pages/trends.py, чтобы тестировать без Dash-app-instance
(dash.register_page() требует инициализированного app — эта функция не требует).
"""
from dash import html

from dash_app.colors import COLORS


def render_trends_result(result: dict | None, error: str | None) -> html.Div:
    """Строит Dash-компонент по ответу API или сообщению об ошибке."""
    if error:
        return html.Div(
            f"❌ Сервис api недоступен: {error}",
            style={
                "background": COLORS["danger_light"],
                "color": COLORS["danger"],
                "padding": "1rem",
                "borderRadius": "0.5rem",
                "fontWeight": "500",
            },
        )

    trends = (result or {}).get("trends") or []
    recommendations = (result or {}).get("recommendations") or []

    if not trends and not recommendations:
        return html.P(
            "Недостаточно данных для выводов по выбранным звонкам.",
            style={"color": COLORS["text_secondary"], "fontStyle": "italic"},
        )

    def _card(children):
        return html.Div(
            children,
            style={
                "background": COLORS["card_bg"],
                "borderRadius": "0.625rem",
                "padding": "1.25rem",
                "boxShadow": "0 1px 3px rgba(0,0,0,0.07), 0 4px 16px rgba(0,0,0,0.04)",
                "marginBottom": "1rem",
            },
        )

    blocks = []
    if trends:
        blocks.append(_card([
            html.H4(
                "Найденные паттерны",
                style={"color": COLORS["text_primary"], "fontWeight": "600", "marginBottom": "0.75rem"},
            ),
            html.Ul(
                [html.Li(t, style={"marginBottom": "0.4rem", "color": COLORS["text_secondary"]}) for t in trends],
                style={"margin": "0", "paddingLeft": "1.25rem"},
            ),
        ]))

    if recommendations:
        rec_items = [
            html.Div(
                [html.Span("💡 ", style={"fontSize": "1.1rem"}), r],
                style={
                    "background": COLORS["success_light"],
                    "borderLeft": f"4px solid {COLORS['success']}",
                    "padding": "0.75rem 1rem",
                    "borderRadius": "0.375rem",
                    "color": COLORS["success"],
                    "marginBottom": "0.5rem",
                    "fontSize": "0.9rem",
                },
            )
            for r in recommendations
        ]
        blocks.append(_card([
            html.H4(
                "Рекомендации для супервайзера",
                style={"color": COLORS["text_primary"], "fontWeight": "600", "marginBottom": "0.75rem"},
            ),
            *rec_items,
        ]))

    return html.Div(blocks)
