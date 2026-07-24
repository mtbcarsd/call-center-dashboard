COLORS = {
    # Brand
    "primary": "#1E3A8A",
    "primary_bright": "#2563EB",
    "primary_light": "#DBEAFE",
    # Status
    "success": "#15803D",
    "success_light": "#DCFCE7",
    "warning": "#B45309",
    "warning_light": "#FEF3C7",
    "danger": "#B91C1C",
    "danger_light": "#FEE2E2",
    "neutral": "#6B7280",
    # Layout
    "bg": "#F1F4F8",
    "card_bg": "#FFFFFF",
    "nav_bg": "#1E293B",
    "text_primary": "#0F172A",
    "text_secondary": "#475569",
    "faint": "#7C8AA0",
    "border": "#E2E8F0",
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
