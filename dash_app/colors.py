# Ключи ниже, указывающие на var(--...), резолвятся браузером по CSS-каскаду,
# определённому в dash_app/app.py::app.index_string (:root/@media(prefers-
# color-scheme)/[data-theme]) — переключение темы (2026-07-25) перекрашивает
# всё, что через них стилизовано, без единой правки в самих страницах.
#
# Акцентные/семантические цвета (primary, success/warning/danger, chart series,
# kpi_*) СОЗНАТЕЛЬНО остаются raw hex, не var(): часть из них попадает прямо в
# Plotly-фигуры (marker_color, gauge bar color и т.п.), а Plotly не умеет
# резолвить CSS custom properties — передать ему "var(--x)" вместо реального
# цвета либо ничего не нарисует, либо упадёт. Поэтому графики держатся на
# фиксированной палитре независимо от темы (см. components/gauge_tile.py).
COLORS = {
    # Brand
    "primary": "#1E3A8A",
    "primary_bright": "#2563EB",
    "primary_light": "var(--brand-wash)",
    # Status
    "success": "#15803D",
    "success_light": "var(--good-wash)",
    "warning": "#B45309",
    "warning_light": "var(--warn-wash)",
    "danger": "#B91C1C",
    "danger_light": "var(--bad-wash)",
    "neutral": "#6B7280",
    # Layout
    "bg": "var(--paper)",
    "card_bg": "var(--surface)",
    "nav_bg": "var(--nav-bg)",
    "text_primary": "var(--ink)",
    "text_secondary": "var(--muted)",
    "faint": "var(--faint)",
    "border": "var(--line)",
    # Chart series
    "operator": "#2563EB",
    "client": "#F59E0B",
    "urgency_low": "#15803D",
    "urgency_medium": "#D97706",
    "urgency_high": "#DC2626",
    # KPI tile accents
    "kpi_calls": "#7C3AED",
    "kpi_agent": "#2563EB",
    "kpi_client": "#D97706",
    "kpi_resolved": "#15803D",
    "kpi_escalated": "#DC2626",
    "kpi_silence": "#6B7280",
}

# Единая типографика приложения (введена вместе со страницей «Справка»,
# 2026-07-24): serif для заголовков страниц/секций (гравитас, банковское
# наследие бухгалтерских книг), sans для основного текста/UI, monospace для
# данных и служебных ярлыков-«eyebrow» — тот же приём, что в справочном
# артефакте, теперь общий для всего приложения. Плотные таблицы (ag-grid) и
# подписи графиков сознательно остаются на BODY, не DISPLAY — засечки на
# мелких данных в сетке ухудшают считываемость, а не улучшают вид.
FONTS = {
    "display": "Georgia, 'Times New Roman', serif",
    "body": "-apple-system, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif",
    "mono": "ui-monospace, 'SF Mono', 'Cascadia Code', Consolas, monospace",
}

CHART_FONT = {
    "family": FONTS["body"],
    "size": 12,
    "color": "#0F172A",
}
