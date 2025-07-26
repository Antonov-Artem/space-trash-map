import requests
import sqlite3
import os
from skyfield.api import EarthSatellite

# Источники для мусора и спутников
TLE_URLS = {
    "debris": "https://celestrak.org/NORAD/elements/gp.php?GROUP=geo&FORMAT=TLE",
    "satellite": "https://celestrak.org/NORAD/elements/gp.php?GROUP=active&FORMAT=TLE"
}

DB_PATH = "debris.db"

# Удалим старую базу, если есть
if os.path.exists(DB_PATH):
    os.remove(DB_PATH)

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS debris (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            tle1 TEXT,
            tle2 TEXT,
            is_satellite INTEGER
        )
    """)
    conn.commit()
    conn.close()

def insert_tle_data(name, line1, line2, is_satellite):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO debris (name, tle1, tle2, is_satellite)
        VALUES (?, ?, ?, ?)
    """, (name, line1, line2, is_satellite))
    conn.commit()
    conn.close()

def fetch_and_store_group(group_name, url, max_count=20):
    print(f"\n🌐 Загружаем {group_name} с {url} ...")
    response = requests.get(url)

    if response.status_code != 200:
        print(f"❌ Ошибка загрузки {group_name}: {response.status_code}")
        return 0, 0

    lines = [line.strip() for line in response.text.splitlines() if line.strip()]
    lines = lines[:max_count * 6]  # Запас: если часть TLE невалидна

    inserted = 0
    skipped = 0
    i = 0

    while i < len(lines) - 2 and inserted < max_count:
        name = lines[i]
        line1 = lines[i + 1]
        line2 = lines[i + 2]

        if line1.startswith("1 ") and line2.startswith("2 "):
            try:
                EarthSatellite(line1, line2, name)
                insert_tle_data(name, line1, line2, int(group_name == "satellite"))
                inserted += 1
                print(f"✅ [{inserted}/{max_count}] {name}")
            except Exception as e:
                print(f"[ERROR] Пропуск {name}: {e}")
                skipped += 1
            i += 3
        else:
            skipped += 1
            i += 1

    print(f"📦 Загружено: {inserted} | Пропущено: {skipped}")
    return inserted, skipped

def reset_database():
    print("\n🧹 Очищаем таблицу...")
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DROP TABLE IF EXISTS debris")
    conn.commit()
    conn.close()
    init_db()
    print("✅ Таблица создана заново.")

if __name__ == "__main__":
    print("🛰 Обновление базы данных TLE...")

    # Изменяй количество объектов здесь:
    max_debris = 20
    max_satellites = 20

    reset_database()

    total_inserted = 0
    total_skipped = 0

    inserted, skipped = fetch_and_store_group("debris", TLE_URLS["debris"], max_count=max_debris)
    total_inserted += inserted
    total_skipped += skipped

    inserted, skipped = fetch_and_store_group("satellite", TLE_URLS["satellite"], max_count=max_satellites)
    total_inserted += inserted
    total_skipped += skipped

    print(f"\n🎯 ИТОГО: добавлено {total_inserted} объектов, пропущено {total_skipped} строк.")
    print("🚀 Готово!\n")
