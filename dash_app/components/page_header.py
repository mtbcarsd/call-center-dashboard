"""Единый заголовок страницы — eyebrow + serif-заголовок + подзаголовок.

Введён вместе со страницей «Справка» (2026-07-24) и распространён на все
страницы вместо продублированного по каждой странице html.H2()+html.P().
"""
from dash import html

from dash_app.colors import COLORS, FONTS


def page_header(icon: str, title: str, subtitle: str = None, eyebrow: str = "CALL CENTER ANALYTICS") -> html.Div:
    children = [
        html.P(
            eyebrow,
            style={
                "fontFamily": FONTS["mono"], "fontSize": "0.72rem", "letterSpacing": "0.14em",
                "textTransform": "uppercase", "color": COLORS["primary_bright"],
                "margin": "0 0 0.4rem 0",
            },
        ),
        html.H2(
            f"{icon} {title}",
            style={
                "fontFamily": FONTS["display"], "fontWeight": "400", "color": COLORS["text_primary"],
                "margin": "0", "fontSize": "1.9rem", "lineHeight": "1.15",
            },
        ),
    ]
    if subtitle:
        children.append(html.P(
            subtitle,
            style={
                "color": COLORS["text_secondary"], "margin": "0.5rem 0 0 0",
                "fontSize": "0.9375rem", "fontFamily": FONTS["body"], "maxWidth": "62ch",
            },
        ))
    return html.Div(children, style={"marginBottom": "1.75rem"})


def section_header(text: str) -> html.H3:
    """Заголовок секции внутри карточки — sans, не serif: секции внутри
    карточек плотнее и сканируются, а не читаются, крупный serif-заголовок
    там будет спорить с содержимым (та же логика, что у ag-grid/графиков)."""
    return html.H3(
        text,
        style={
            "fontFamily": FONTS["body"], "color": COLORS["text_primary"], "fontWeight": "700",
            "margin": "0 0 1rem 0", "fontSize": "1rem",
        },
    )
