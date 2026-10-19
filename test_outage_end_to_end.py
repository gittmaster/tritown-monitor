"""
End to end: the real Pi sending code talks to the real website code (temporary
database) while the "internet" is cut and then restored.
Usage: python test_outage_end_to_end.py
"""
import os
import sys
import tempfile
import types
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_db.close()
os.environ["DB_PATH"] = _db.name
os.environ.pop("DATABASE_URL", None)

import app as site  # noqa: E402

passed = failed = 0


def check(label, condition):
    global passed, failed
    if condition:
        passed += 1
        print(f"[PASS] {label}")
    else:
        failed += 1
        print(f"[FAIL] {label}")


stub = types.ModuleType("Adafruit_DHT")
stub.DHT22 = object()
sys.modules["Adafruit_DHT"] = stub
src = open("pi_sender.py", encoding="utf-8").read().split("consecutive_failures = 0")[0]
log = tempfile.NamedTemporaryFile(suffix=".log", delete=False).name
qpath = os.path.join(tempfile.mkdtemp(), "unsent.jsonl")
src = src.replace("LOG_FILE = '/home/pi/sender.log'", "LOG_FILE = %r" % log)
src = src.replace("QUEUE_FILE = '/home/pi/unsent_readings.jsonl'", "QUEUE_FILE = %r" % qpath)
ns = {"__name__": "pi"}
exec(compile(src, "pi_sender.py", "exec"), ns)

client = site.app.test_client()
internet_up = {"on": True}


def fake_post(url, json=None, headers=None, timeout=None):
    if not internet_up["on"]:
        import requests
        raise requests.exceptions.ConnectionError("no internet")
    r = client.post("/api/reading", json=json, headers=headers)
    out = MagicMock(status_code=r.status_code)
    out.json.return_value = r.get_json()
    return out


def stored():
    conn = site.get_db()
    cur = conn.cursor()
    cur.execute("SELECT temperature, created_at FROM readings ORDER BY created_at")
    rows = [(r[0], str(r[1])) for r in cur.fetchall()]
    conn.close()
    return rows


with patch("time.sleep"), patch.object(ns["requests"], "post", side_effect=fake_post):
    ns["send_reading"](20.0, 50.0)
    check("normal: 1 reading on the website", len(stored()) == 1)

    internet_up["on"] = False
    for t in (21.0, 22.0, 23.0):
        ns["send_reading"](t, 50.0)
    check("internet cut: website still has only 1", len(stored()) == 1)
    check("internet cut: 3 readings saved on the Pi", ns["saved_queue"].count() == 3)

    internet_up["on"] = True
    ns["send_reading"](24.0, 50.0)
    rows = stored()
    check("internet back: all 5 readings are on the website", [r[0] for r in rows].count(21.0) == 1 and len(rows) == 5)
    check("nothing left waiting on the Pi", ns["saved_queue"].count() == 0)
    check("no duplicates", sorted(r[0] for r in rows) == [20.0, 21.0, 22.0, 23.0, 24.0])

    # resend the same saved reading again (reply got lost): website keeps one copy
    ns["saved_queue"].add({"device_id": "pi-library", "location": "Middleton Fire Station",
                           "temperature": 21.0, "humidity": 50.0, "dew_point": 9.0,
                           "recorded_at": rows[1][1].replace(" ", "T")})
    ns["send_reading"](25.0, 50.0)
    temps = sorted(r[0] for r in stored())
    check("a repeated saved reading is not stored twice", temps.count(21.0) == 1 and len(temps) == 6)

print(f"\n{passed} passed, {failed} failed")
raise SystemExit(1 if failed else 0)
