"""Dash-приложение Call Center Analytics — точка входа для gunicorn.

Запуск локально:
    python -m dash_app.app          # из корня репозитория
На Railway:
    gunicorn dash_app.app:server --bind 0.0.0.0:$PORT --workers 2
"""
import os
import secrets

import dash
from dash import html, dcc, callback, Input, Output
from flask import redirect, render_template_string, request, session

from dash_app.auth import get_current_user, get_user_from_db, verify_password
from dash_app.colors import COLORS

app = dash.Dash(
    __name__,
    use_pages=True,
    suppress_callback_exceptions=True,
    title="Call Center Analytics",
    update_title=None,
    meta_tags=[{"name": "viewport", "content": "width=device-width, initial-scale=1"}],
)
server = app.server
server.secret_key = os.environ.get("DASH_SECRET_KEY") or secrets.token_hex(32)

# ── Страница логина ───────────────────────────────────────────────────────────

_LOGIN_HTML = """<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Войти — Call Center Analytics</title>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      background: #F0F4F8;
      display: flex; align-items: center; justify-content: center; min-height: 100vh;
    }
    .card {
      background: #fff; border-radius: 0.75rem; padding: 2.5rem 2.75rem;
      box-shadow: 0 4px 24px rgba(0,0,0,0.10), 0 1px 4px rgba(0,0,0,0.06);
      width: 100%; max-width: 390px;
    }
    .logo { display: flex; align-items: center; gap: 0.5rem; margin-bottom: 1.75rem; }
    .logo-icon { font-size: 1.75rem; }
    .logo-text { font-size: 1rem; font-weight: 700; color: #0F172A; }
    h1 { font-size: 1.3rem; font-weight: 700; color: #0F172A; margin-bottom: 0.25rem; }
    .subtitle { font-size: 0.875rem; color: #475569; margin-bottom: 1.75rem; }
    label { display: block; font-size: 0.8125rem; font-weight: 600; color: #374151;
            margin-bottom: 0.375rem; }
    input[type=text], input[type=password] {
      width: 100%; padding: 0.625rem 0.875rem; border: 1.5px solid #E2E8F0;
      border-radius: 0.5rem; font-size: 0.9375rem; font-family: inherit;
      outline: none; transition: border-color 0.15s, box-shadow 0.15s; color: #0F172A;
    }
    input:focus { border-color: #2563EB; box-shadow: 0 0 0 3px rgba(37,99,235,0.12); }
    .field { margin-bottom: 1.125rem; }
    .btn {
      width: 100%; padding: 0.75rem; background: #2563EB; color: #fff; border: none;
      border-radius: 0.5rem; font-size: 0.9375rem; font-weight: 600; cursor: pointer;
      font-family: inherit; margin-top: 0.375rem; transition: background 0.15s;
      letter-spacing: 0.01em;
    }
    .btn:hover { background: #1D4ED8; }
    .error {
      color: #B91C1C; background: #FEE2E2; border: 1px solid #FECACA;
      padding: 0.75rem 1rem; border-radius: 0.5rem;
      font-size: 0.875rem; margin-bottom: 1.25rem;
    }
  </style>
</head>
<body>
  <div class="card">
    <div class="logo">
      <span class="logo-icon">📞</span>
      <span class="logo-text">Call Center Analytics</span>
    </div>
    <h1>Войти</h1>
    <p class="subtitle">Введите логин и пароль для доступа к системе</p>
    {% if error %}<div class="error">{{ error }}</div>{% endif %}
    <form method="POST">
      <div class="field">
        <label for="username">Логин</label>
        <input id="username" name="username" type="text" autocomplete="username"
               value="{{ username }}" autofocus>
      </div>
      <div class="field">
        <label for="password">Пароль</label>
        <input id="password" name="password" type="password" autocomplete="current-password">
      </div>
      <button class="btn" type="submit">Войти →</button>
    </form>
  </div>
</body>
</html>"""


# ── Flask routes: login / logout ──────────────────────────────────────────────

@server.route("/login", methods=["GET", "POST"])
def login():
    error = None
    username_val = ""
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        username_val = username
        user = get_user_from_db(username)
        if user and verify_password(password, user["password_hash"]):
            session["user"] = {
                "username": user["username"],
                "role": user["role"],
                "display_name": user["display_name"],
                "department": user["department"],
                "operator_match_name": user["operator_match_name"],
            }
            return redirect(request.args.get("next") or "/")
        error = "Неверный логин или пароль"
    return render_template_string(_LOGIN_HTML, error=error, username=username_val)


@server.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


# ── Защита всех Dash-роутов ────────────────────────────────────────────────────

@server.before_request
def _require_login():
    if request.path in ("/login", "/logout"):
        return None
    if not session.get("user"):
        return redirect(f"/login?next={request.path}")


# ── Навигация ─────────────────────────────────────────────────────────────────

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
                    style={"display": "flex", "alignItems": "center", "flexShrink": "0"},
                ),
                html.Div(
                    id="nav-items",
                    style={"display": "flex", "gap": "0.25rem", "flexWrap": "wrap"},
                ),
                html.Div(
                    id="nav-user",
                    style={"display": "flex", "alignItems": "center", "gap": "0.75rem",
                           "flexShrink": "0"},
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


@callback(
    Output("nav-items", "children"),
    Output("nav-user", "children"),
    Input("url", "pathname"),
)
def update_nav(pathname: str):
    pathname = pathname or "/"
    nav_links = [
        _nav_link(href, label, pathname == href or (href != "/" and pathname.startswith(href)))
        for href, label in _NAV_LINKS
    ]

    user = get_current_user()
    if user:
        dept_badge = []
        if user.get("department"):
            dept_badge = [
                html.Span(
                    user["department"],
                    style={
                        "background": "rgba(37,99,235,0.25)",
                        "color": "#93C5FD",
                        "borderRadius": "0.25rem",
                        "padding": "0.1rem 0.4rem",
                        "fontSize": "0.75rem",
                        "fontWeight": "600",
                    },
                )
            ]
        nav_user = [
            html.Span(
                user["display_name"],
                style={"color": "#CBD5E1", "fontSize": "0.8125rem"},
            ),
            *dept_badge,
            html.A(
                "Выйти",
                href="/logout",
                style={
                    "color": "#94A3B8",
                    "fontSize": "0.8125rem",
                    "textDecoration": "none",
                    "borderLeft": "1px solid #334155",
                    "paddingLeft": "0.75rem",
                },
            ),
        ]
    else:
        nav_user = []

    return nav_links, nav_user


if __name__ == "__main__":
    app.run(debug=True, port=8050)
