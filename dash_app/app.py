"""Dash-приложение Call Center Analytics — точка входа для gunicorn.

Запуск локально:
    python -m dash_app.app          # из корня репозитория
На Railway:
    gunicorn dash_app.app:server --bind 0.0.0.0:$PORT --workers 2
"""
import dash
from dash import html, dcc, callback, Input, Output

from dash_app.colors import COLORS

app = dash.Dash(
    __name__,
    use_pages=True,
    suppress_callback_exceptions=True,
    title="Call Center Analytics",
    update_title=None,
    meta_tags=[{"name": "viewport", "content": "width=device-width, initial-scale=1"}],
)
server = app.server  # точка подключения gunicorn

_NAV_LINKS = [
    ("/", "📊 Аналитика"),
    ("/operators", "🧑‍💼 Операторы"),
    ("/rating", "🏆 Рейтинг"),
    ("/compliance", "🛡️ Compliance"),
    ("/trends", "📈 Тренды"),
    ("/team", "👥 Команда"),
]


def _nav_link(href: str, label: str, is_active: bool) -> dcc.Link:
    return dcc.Link(
        label,
        href=href,
        style={
            "color": "white" if is_active else "#94A3B8",
            "textDecoration": "none",
            "padding": "0.4rem 0.875rem",
            "borderRadius": "0.375rem",
            "background": "rgba(255,255,255,0.12)" if is_active else "transparent",
            "fontWeight": "600" if is_active else "400",
            "fontSize": "0.875rem",
            "whiteSpace": "nowrap",
        },
    )


app.layout = html.Div(
    [
        dcc.Location(id="url"),
        html.Nav(
            [
                html.Div(
                    [
                        html.Span("📞", style={"fontSize": "1.3rem", "marginRight": "0.5rem"}),
                        html.Span(
                            "Call Center Analytics",
                            style={"fontWeight": "700", "fontSize": "1rem", "color": "white"},
                        ),
                    ],
                    style={"display": "flex", "alignItems": "center"},
                ),
                html.Div(
                    id="nav-items",
                    style={"display": "flex", "gap": "0.25rem", "flexWrap": "wrap"},
                ),
            ],
            style={
                "display": "flex",
                "alignItems": "center",
                "justifyContent": "space-between",
                "background": COLORS["nav_bg"],
                "padding": "0.75rem 1.5rem",
                "position": "sticky",
                "top": "0",
                "zIndex": "100",
                "boxShadow": "0 2px 8px rgba(0,0,0,0.2)",
            },
        ),
        html.Div(
            dash.page_container,
            style={
                "padding": "1.5rem",
                "background": COLORS["bg"],
                "minHeight": "calc(100vh - 52px)",
            },
        ),
    ],
    style={
        "fontFamily": "Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
        "margin": "0",
    },
)


@callback(Output("nav-items", "children"), Input("url", "pathname"))
def update_nav(pathname: str):
    pathname = pathname or "/"
    return [
        _nav_link(href, label, pathname == href or (href != "/" and pathname.startswith(href)))
        for href, label in _NAV_LINKS
    ]


if __name__ == "__main__":
    app.run(debug=True, port=8050)
