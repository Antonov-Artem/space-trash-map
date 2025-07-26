import requests
import sqlite3
import os
from flask import Flask, jsonify, request
from skyfield.api import EarthSatellite, load
from datetime import timedelta
from flask_cors import CORS


# Источники TLE
TLE_URLS = {
    "debris": "https://celestrak.org/NORAD/elements/gp.php?GROUP=geo&FORMAT=TLE",
    "satellite": "https://celestrak.org/NORAD/elements/gp.php?GROUP=active&FORMAT=TLE"
}

DB_PATH = "debris.db"
app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "https://space-trash-map.vercel.app"}})

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
    response = requests.get(url)
    if response.status_code != 200:
        print(f"❌ Ошибка загрузки {group_name}: {response.status_code}")
        return 0, 0

    lines = [line.strip() for line in response.text.splitlines() if line.strip()]
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
            except Exception:
                skipped += 1
            i += 3
        else:
            skipped += 1
            i += 1

    return inserted, skipped

def reset_database():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DROP TABLE IF EXISTS debris")
    conn.commit()
    conn.close()
    init_db()

@app.route("/update", methods=["POST"])
def update():
    debris_count = int(request.form.get("debris", 10))
    satellite_count = int(request.form.get("satellite", 10))

    reset_database()
    fetch_and_store_group("debris", TLE_URLS["debris"], max_count=debris_count)
    fetch_and_store_group("satellite", TLE_URLS["satellite"], max_count=satellite_count)

    return jsonify({"status": "ok"})

@app.route("/api/objects")
def api_objects():
    limit = int(request.args.get("limit", 40))

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, tle1, tle2, is_satellite FROM debris LIMIT ?", (limit,))
    rows = cursor.fetchall()
    conn.close()

    ts = load.timescale()
    now = ts.now()
    result = []

    for row in rows:
        try:
            sat = EarthSatellite(row[2], row[3], row[1], ts)
            geocentric_now = sat.at(now)
            position_now = geocentric_now.position.km

            orbit_points = []
            for minutes_ahead in range(0, 91, 10):
                t = ts.utc(now.utc_datetime() + timedelta(minutes=minutes_ahead))
                pos = sat.at(t).position.km
                orbit_points.append([float(pos[0]), float(pos[1]), float(pos[2])])

            obj_type = 'satellite' if row[4] else 'debris'

            result.append({
                "id": row[0],
                "name": row[1],
                "type": obj_type,
                "description": f"{obj_type.capitalize()}: {row[1]}",
                "position": [float(position_now[0]), float(position_now[1]), float(position_now[2])],
                "orbit": orbit_points
            })
        except Exception as e:
            print(f"⚠️ Ошибка орбиты: {row[1]} – {e}")
            continue

    return jsonify(result)

if __name__ == "__main__":
    print("🚀 Starting Space Debris Tracker API...")
    init_db()

    # Проверка на пустую БД
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM debris")
    count = cursor.fetchone()[0]
    conn.close()

    if count == 0:
        print("📡 Загружаем объекты...")
        fetch_and_store_group("debris", TLE_URLS["debris"], max_count=20)
        fetch_and_store_group("satellite", TLE_URLS["satellite"], max_count=20)

    print("✅ Сервер готов к работе.")
    app.run(host="0.0.0.0", port=5000, debug=True)
