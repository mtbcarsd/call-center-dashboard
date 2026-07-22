"""KPI-карточка: замена st.metric() для директорского дашборда."""
from dash import html

from dash_app.colors import COLORS


def stat_tile(
    label: str,
    value: str,
    subtitle: str = None,
    accent: str = COLORS["primary_bright"],
) -> html.Div:
    children = [
        html.P(
            label,
            style={
                "fontSize": "0.7rem",
                "fontWeight": "700",
                "color": COLORS["text_secondary"],
                "textTransform": "uppercase",
                "letterSpacing": "0.08em",
                "margin": "0 0 0.5rem 0",
            },
        ),
        html.P(
            value,
            style={
                "fontSize": "1.875rem",
                "fontWeight": "700",
                "color": COLORS["text_primary"],
                "lineHeight": "1",
                "margin": "0",
            },
        ),
    ]
    if subtitle:
        children.append(
            html.P(
                subtitle,
                style={
                    "fontSize": "0.75rem",
                    "color": COLORS["text_secondary"],
                    "margin": "0.4rem 0 0 0",
                },
            )
        )
    return html.Div(
        children,
        style={
            "background": "white",
            "borderRadius": "0.625rem",
            "padding": "1.25rem 1.5rem",
            "borderLeft": f"4px solid {accent}",
            "boxShadow": "0 1px 3px rgba(0,0,0,0.07), 0 4px 16px rgba(0,0,0,0.04)",
            "flex": "1",
            "minWidth": "130px",
        },
    )
