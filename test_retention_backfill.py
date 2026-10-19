"""
Offline test for: configurable retention (default 60 days), accepting the
original time of a resent reading, and duplicate protection.
Uses a temporary throwaway database; never touches monitor_v2.db or the live site.
Usage: python test_retention_backfill.py
"""
import os
import tempfile
import time
from datetime import datetime, timedelta

_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp.close()
os.environ["DB_PATH"] = _tmp.name
os.environ.pop("DATABASE_URL", None)
os.environ.pop("RETENTION_DAYS", None)

import app as app_module  # noqa: E402

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
read = app_module.read_retention_days


def iso(minutes_ago=0, days_ago=0):
    t = datetime.utcnow() - timedelta(minutes=minutes_ago, days=days_ago)
    return t.strftime("%Y-%m-%dT%H:%M:%S")


def post(**extra):
    body = {"device_id": "pi-test", "location": "Test Station", "temperature": 21.0,
            "humidity": 45.0, "dew_point": 9.0}
    body.update(extra)
    return client.post("/api/reading", json=body, headers=HEAD)


def count():
    conn = app_module.get_db()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM readings")
    n = cur.fetchone()[0]
    conn.close()
    return n


def rows():
    conn = app_module.get_db()
    cur = conn.cursor()
    cur.execute("SELECT created_at FROM readings ORDER BY created_at")
    out = [str(r[0]) for r in cur.fetchall()]
    conn.close()
    return out


# --- retention setting
check("default is 60 days", app_module.RETENTION_DAYS == 60 and read(None) == 60)
check("30 days accepted", read("30") == 30)
check("90 days accepted", read("90") == 90)
check("text falls back to 60", read("lots") == 60)
check("zero falls back to 60", read("0") == 60)
check("negative falls back to 60", read("-5") == 60)
check("absurdly large falls back to 60", read("99999") == 60)
check("shown on the stats page for support", client.get("/api/stats").get_json().get("retention_days") == 60)

# --- normal live reading is unchanged
r = post()
check("normal reading still stored (201)", r.status_code == 201 and count() == 1)
check("reply tells the Pi resend is supported", r.get_json().get("supports_recorded_at") is True)

# --- resent reading keeps its original time
want = iso(minutes_ago=180)
r = post(recorded_at=want)
check("resent reading accepted", r.status_code == 201 and count() == 2)
check("resent reading keeps its ORIGINAL time", want.replace("T", " ") in rows())

# --- sending the same one twice does not double it
r = post(recorded_at=want)
check("same resent reading again: not stored twice", r.status_code == 201 and count() == 2)
check("duplicate is reported as success so the Pi can drop it", r.get_json().get("duplicate") is True)

# --- different device with the same time is a different reading
r = post(recorded_at=want, device_id="pi-other")
check("another device at the same second is kept", count() == 3)

# --- same device and same second but a different reading is kept
n = count()
post(recorded_at=want, temperature=33.0)
check("same second but different temperature: both kept", count() == n + 1)

# --- bad or odd times never lose the reading
before = count()
for label, val in [("garbage text", "yesterday-ish"), ("a number", 12345), ("empty", ""),
                   ("a time far in the future", iso(minutes_ago=-600))]:
    r = post(recorded_at=val)
    check("%s: reading still stored with current time" % label, r.status_code == 201)
check("all four were stored", count() == before + 4)

# --- too old: skipped quietly, reported as success so the Pi drops it
before = count()
r = post(recorded_at=iso(days_ago=61))
check("older than 60 days: not stored", r.status_code == 201 and count() == before)
check("older than 60 days: Pi told it was skipped", "skipped" in r.get_json())
r = post(recorded_at=iso(days_ago=59))
check("59 days old: still stored", count() == before + 1)

# --- old readings are deleted by the cleanup, new ones are kept
conn = app_module.get_db()
cur = conn.cursor()
old_stamp = (datetime.utcnow() - timedelta(days=61)).strftime("%Y-%m-%d %H:%M:%S")
cur.execute("INSERT INTO readings (id,device_id,location,created_at) VALUES ('old1','pi-test','Test Station',?)", (old_stamp,))
conn.commit()
conn.close()
total = count()
app_module.cleanup_old_readings()
check("cleanup removed the 61-day-old reading only", count() == total - 1 and old_stamp not in rows())

# --- a shorter setting really deletes more
app_module.RETENTION_DAYS = 30
conn = app_module.get_db()
cur = conn.cursor()
mid = (datetime.utcnow() - timedelta(days=45)).strftime("%Y-%m-%d %H:%M:%S")
cur.execute("INSERT INTO readings (id,device_id,location,created_at) VALUES ('mid1','pi-test','Test Station',?)", (mid,))
conn.commit()
conn.close()
total = count()
app_module.cleanup_old_readings()
check("with 30 days, a 45-day-old reading is deleted", mid not in rows())
app_module.RETENTION_DAYS = 90
conn = app_module.get_db()
cur = conn.cursor()
cur.execute("INSERT INTO readings (id,device_id,location,created_at) VALUES ('mid2','pi-test','Test Station',?)", (mid,))
conn.commit()
conn.close()
total = count()
app_module.cleanup_old_readings()
check("with 90 days, the same 45-day-old reading is kept", mid in rows())
app_module.RETENTION_DAYS = 60

# --- cleanup also runs by itself every few hours, and a failure never blocks a reading
app_module._last_cleanup = time.time()
conn = app_module.get_db()
cur = conn.cursor()
cur.execute("INSERT INTO readings (id,device_id,location,created_at) VALUES ('old2','pi-test','Test Station',?)", (old_stamp,))
conn.commit()
conn.close()
post()
check("not run again within a few hours", old_stamp in rows())
app_module._last_cleanup = time.time() - 7 * 3600
post()
check("runs by itself after six hours", old_stamp not in rows())

app_module._last_cleanup = time.time() - 7 * 3600
original = app_module.cleanup_old_readings
def boom():
    raise RuntimeError("database hiccup")
app_module.cleanup_old_readings = boom
before = count()
r = post()
app_module.cleanup_old_readings = original
check("a cleanup failure never blocks a reading", r.status_code == 201 and count() == before + 1)

# --- the alert/heartbeat time stays in the format the heartbeat script reads
stamp = client.get("/api/stats").get_json()["last_updated"]
try:
    datetime.strptime(stamp.split(".")[0], "%Y-%m-%d %H:%M:%S")
    ok = True
except Exception:
    ok = False
check("last_updated format is unchanged", ok)

print(f"\n{passed} passed, {failed} failed")
raise SystemExit(1 if failed else 0)
