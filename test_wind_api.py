"""
Offline test for wind handling in the website backend (app.py).

Uses a temporary throwaway database, so it never touches monitor_v2.db or the
live site.   Usage: python test_wind_api.py
"""
import os
import tempfile

_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp.close()
os.environ["DB_PATH"] = _tmp.name
os.environ.pop("DATABASE_URL", None)

import app as app_module  # noqa: E402  (must come after the env vars above)

passed = failed = 0


def check(label, condition):
    global passed, failed
    if condition:
        passed += 1
        print(f"[PASS] {label}")
    else:
        failed += 1
        print(f"[FAIL] {label}")


client = app_module.app.test_client()
HEAD = {"X-API-Key": app_module.API_KEY}


def post(payload):
    return client.post("/api/reading", json=payload, headers=HEAD)


def latest(location):
    rows = client.get("/api/latest").get_json()["readings"]
    return next(r for r in rows if r["location"] == location)


base = {"device_id": "t", "temperature": 20.0, "humidity": 50.0}

# --- wind is stored and returned ---------------------------------------
r = post({**base, "location": "A", "wind_speed": 8.3, "wind_direction": 270.5})
check("reading with wind is accepted (201)", r.status_code == 201)
row = latest("A")
check("wind_speed is returned by /api/latest", row["wind_speed"] == 8.3)
check("wind_direction is returned by /api/latest", row["wind_direction"] == 270.5)

# --- old Pi senders (no wind) keep working ------------------------------
r = post({**base, "location": "B"})
check("reading WITHOUT wind is still accepted (old sender)", r.status_code == 201)
row = latest("B")
check("missing wind is stored as null", row["wind_speed"] is None and row["wind_direction"] is None)

# --- a bad wind sensor never blocks temperature/humidity ----------------
r = post({**base, "location": "C", "wind_speed": "abc", "wind_direction": 999})
check("garbage wind values do not reject the reading", r.status_code == 201)
row = latest("C")
check("garbage wind is stored as null", row["wind_speed"] is None and row["wind_direction"] is None)
check("temperature still stored when wind is bad", row["temperature"] == 20.0)

r = post({**base, "location": "D", "wind_speed": -5, "wind_direction": -1})
row = latest("D")
check("negative wind is stored as null", row["wind_speed"] is None and row["wind_direction"] is None)

r = post({**base, "location": "E", "wind_speed": float("nan")})
check("NaN wind does not break the reading", r.status_code == 201 and latest("E")["wind_speed"] is None)

r = post({**base, "location": "F", "wind_speed": 0, "wind_direction": 0})
row = latest("F")
check("zero wind and 0 degrees are real values, not null",
      row["wind_speed"] == 0 and row["wind_direction"] == 0)

# --- history includes wind too ------------------------------------------
hist = client.get("/api/history?location=A").get_json()
check("/api/history includes wind", hist and hist[0]["wind_speed"] == 8.3)

# --- security unchanged --------------------------------------------------
r = client.post("/api/reading", json={**base, "location": "G", "wind_speed": 5})
check("missing API key is still rejected (401)", r.status_code == 401)

# --- existing databases get the columns added safely --------------------
import sqlite3  # noqa: E402
old = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
old.close()
conn = sqlite3.connect(old.name)
conn.execute("""CREATE TABLE readings (id TEXT PRIMARY KEY, device_id TEXT NOT NULL,
    location TEXT NOT NULL, temperature REAL, humidity REAL, pressure REAL,
    dew_point REAL, alert_level TEXT, alert_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
conn.execute("INSERT INTO readings (id,device_id,location,temperature,humidity) VALUES ('x','d','OLD',10,40)")
conn.commit()
conn.close()
os.environ["DB_PATH"] = old.name
app_module.init_db()
app_module.init_db()  # running twice must be harmless
conn = sqlite3.connect(old.name)
cols = [c[1] for c in conn.execute("PRAGMA table_info(readings)")]
kept = conn.execute("SELECT temperature FROM readings WHERE id='x'").fetchone()
conn.close()
check("old database gets wind columns added", "wind_speed" in cols and "wind_direction" in cols)
check("old rows are kept untouched", kept == (10.0,))

# --- warning support: when did each location last report wind? -----------
import time  # noqa: E402
os.environ["DB_PATH"] = _tmp.name
post({**base, "location": "WORKS", "wind_speed": 5.0, "wind_direction": 90})
post({**base, "location": "NEVER"})                      # never had a wind sensor
post({**base, "location": "BROKE", "wind_speed": 6.0, "wind_direction": 80})
time.sleep(1.1)                                          # so "latest" is unambiguous
post({**base, "location": "BROKE"})                      # wind sensor stopped
rows = {r["location"]: r for r in client.get("/api/latest").get_json()["readings"]}
check("working sensor: wind_last_seen is set", rows["WORKS"]["wind_last_seen"] is not None)
check("never had wind: wind_last_seen is null (no false alarm)", rows["NEVER"]["wind_last_seen"] is None)
check("sensor stopped: latest has no wind...", rows["BROKE"]["wind_speed"] is None)
check("sensor stopped: ...but wind_last_seen remembers it worked", rows["BROKE"]["wind_last_seen"] is not None)
stats = client.get("/api/stats").get_json()
check("/api/stats reports wind_last_seen", stats.get("wind_last_seen") is not None)
check("/api/stats still has its old fields",
      all(k in stats for k in ("total_readings", "locations", "last_updated")))

# --- the wind lookup must never break the main readings -------------------
legacy = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
legacy.close()
conn = sqlite3.connect(legacy.name)
conn.execute("""CREATE TABLE readings (id TEXT PRIMARY KEY, device_id TEXT NOT NULL,
    location TEXT NOT NULL, temperature REAL, humidity REAL, pressure REAL,
    dew_point REAL, alert_level TEXT, alert_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
conn.execute("INSERT INTO readings (id,device_id,location,temperature,humidity,alert_level) VALUES ('y','d','LEGACY',10,40,'LOW')")
conn.commit()
conn.close()
os.environ["DB_PATH"] = legacy.name          # database WITHOUT wind columns, never upgraded
r = client.get("/api/latest")
check("no wind columns: /api/latest still works (200)", r.status_code == 200)
check("no wind columns: readings still returned",
      r.get_json()["readings"][0]["location"] == "LEGACY")
r = client.get("/api/stats")
check("no wind columns: /api/stats still works (200)", r.status_code == 200)
check("no wind columns: stats totals still correct", r.get_json()["total_readings"] == 1)
os.environ["DB_PATH"] = _tmp.name
try:
    os.unlink(legacy.name)
except OSError:
    pass

for f in (_tmp.name, old.name):
    try:
        os.unlink(f)
    except OSError:
        pass

print(f"\n{passed} passed, {failed} failed")
raise SystemExit(1 if failed else 0)
