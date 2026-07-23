"""Конфигурируемый чек-лист оценки звонка (вместо жёсткой оценки от LLM одним числом).

Каждая категория — да/нет вопрос с весом. Сумма весов = 100,
поэтому взвешенный итог сразу читается как процент/оценка из 10.
"""
import json

CHECKLIST = [
    {
        "key": "greeting",
        "label": "Приветствие",
        "weight": 15,
        "question": "Поприветствовал ли оператор клиента в начале разговора (поздоровался, представил банк)?",
    },
    {
        "key": "needs_discovery",
        "label": "Выявление потребности",
        "weight": 20,
        "question": "Задавал ли оператор уточняющие вопросы, чтобы понять точную потребность клиента?",
    },
    {
        "key": "solution_presented",
        "label": "Предложено решение",
        "weight": 20,
        "question": "Предложил ли оператор конкретное решение или продукт по запросу клиента?",
    },
    {
        "key": "objection_handling",
        "label": "Отработка возражений",
        "weight": 15,
        "question": "Если клиент выражал сомнение или возражение, отработал ли его оператор?",
    },
    {
        "key": "politeness",
        "label": "Вежливость и тон",
        "weight": 15,
        "question": "Был ли оператор вежлив и спокоен, не грубил ли клиенту?",
    },
    {
        "key": "closing",
        "label": "Прощание",
        "weight": 15,
        "question": "Попрощался ли оператор в конце разговора (поблагодарил, попрощался)?",
    },
]

assert sum(item["weight"] for item in CHECKLIST) == 100


def weighted_score(checklist_result: dict) -> float:
    """Взвешенный итог 0-10 по результатам чек-листа {key: true/false}."""
    total = sum(
        item["weight"] for item in CHECKLIST if checklist_result.get(item["key"])
    )
    return round(total / 10, 1)


# ── Парсинг сохранённых в БД checklist_json/compliance_json ──────────────────
# Единый источник вместо дублей в dashboard.py (Streamlit) и dash_app/data.py (Dash).

def parse_checklist(raw) -> dict:
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return {}


def parse_compliance(raw) -> dict | None:
    if not raw:
        return None
    try:
        parsed = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return None
    return {
        "passed": bool(parsed.get("passed", True)),
        "issues": parsed.get("issues") or [],
    }


def checklist_pass_rates(checklists: list[dict]) -> dict[str, float | None]:
    """Процент прохождения каждого пункта чек-листа (0-100 или None если нет данных)."""
    rates = {}
    for item in CHECKLIST:
        key = item["key"]
        results = [c[key] for c in checklists if key in c]
        rates[item["label"]] = (
            sum(1 for r in results if r) / len(results) * 100
            if results else None
        )
    return rates
