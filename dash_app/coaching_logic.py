"""Чистая функция сборки UI для страницы «Мой кабинет» (коучинг-панель).

Вынесена из pages/me.py по тому же принципу, что trends_logic.py — тестируется
без Dash-app-instance (dash.register_page() требует инициализированного app).
"""
from dash import html

from dash_app.colors import COLORS


def render_coaching_result(result: dict | None, error: str | None) -> html.Div:
    """Строит Dash-компонент по ответу GET /coaching/{operator_name} или ошибке."""
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

    strengths = (result or {}).get("strengths") or []
    weaknesses = (result or {}).get("weaknesses") or []
    recommendations = (result or {}).get("recommendations") or []

    if not strengths and not weaknesses and not recommendations:
        return html.P(
            "Недостаточно данных для рекомендаций.",
            style={"color": COLORS["text_secondary"], "fontStyle": "italic"},
        )

    def _list_block(title: str, items: list[str], color: str, bg: str, icon: str):
        return html.Div(
            [
                html.H4(
                    title,
                    style={"color": COLORS["text_primary"], "fontWeight": "600", "marginBottom": "0.75rem"},
                ),
                *[
                    html.Div(
                        [html.Span(f"{icon} ", style={"fontSize": "1.05rem"}), item],
                        style={
                            "background": bg,
                            "borderLeft": f"4px solid {color}",
                            "padding": "0.625rem 0.875rem",
                            "borderRadius": "0.375rem",
                            "marginBottom": "0.5rem",
                            "fontSize": "0.9rem",
                            "color": COLORS["text_primary"],
                        },
                    )
                    for item in items
                ],
            ],
            style={"marginBottom": "1.25rem"},
        )

    blocks = []
    if strengths:
        blocks.append(_list_block("Сильные стороны", strengths, COLORS["success"], "#F0FDF4", "✅"))
    if weaknesses:
        blocks.append(_list_block("Точки роста", weaknesses, COLORS["warning"], COLORS["warning_light"], "⚠️"))
    if recommendations:
        blocks.append(_list_block("Рекомендации", recommendations, COLORS["primary_bright"], COLORS["primary_light"], "💡"))

    return html.Div(blocks)
