"""Загрузить в локальную SQLite-базу результаты, уже посчитанные и сохранённые в results_cache.json."""
import json
from pipeline import upload_to_db

with open("results_cache.json", encoding="utf-8") as f:
    records = json.load(f)

print(f"Загружаю {len(records)} записей из кэша в локальную базу (call_center.db)...")
upload_to_db(records)
print("Готово.")
