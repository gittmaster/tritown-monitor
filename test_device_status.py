"""
Offline test: the Pi reporting its own problems (temperature sensor / wind
sensor), the website storing and showing them, and the phone alert using them.
Temporary database, pretend network, no hardware.   Usage: python test_device_status.py
"""
import json
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


client = site.app.test_client()
HEAD = {"X-API-Key": site.API_KEY}
LOC = "Middleton Fire Station"


def reading():
    return client.post("/api/reading", json={"device_id": "pi-library", "location": LOC,
                       "temperature": 20.0, "humidity": 50.0, "dew_point": 9.0}, headers=HEAD)


def status(problems, **extra):
    body = {"device_id": "pi-library", "location": LOC, "problems": problems}
    body.update(extra)
    return client.post("/api/status", json=body, headers=HEAD)


def latest_row():
    return client.get("/api/latest").get_json()["readings"][0]


TEMP = {"part": "temperature_sensor", "detail": "The temperature sensor has not answered."}
WIND = {"part": "wind_sensor", "detail": "The wind sensor has not answered."}

# ================= website
reading()
check("no report yet: no problems on the card", latest_row()["device_problems"] == [])
check("no report yet: none in stats", client.get("/api/stats").get_json()["device_problems"] == [])

check("wrong key is refused", client.post("/api/status", json={}, headers={"X-API-Key": "nope"}).status_code == 401)
check("no key is refused", client.post("/api/status", json={}).status_code == 401)

r = status([TEMP], disk_free_mb=5400.5, queue_waiting=3)
check("a problem report is accepted", r.status_code == 201 and r.get_json()["problems"] == 1)
row = latest_row()
check("the card now lists the problem", [p["part"] for p in row["device_problems"]] == ["temperature_sensor"])
check("problem text comes through", "has not answered" in row["device_problems"][0]["detail"])
check("stats lists it too", client.get("/api/stats").get_json()["device_problems"][0]["location"] == LOC)

status([TEMP, WIND])
check("a new report REPLACES the old one", len(latest_row()["device_problems"]) == 2)
status([])
check("an all-clear report removes the problems", latest_row()["device_problems"] == [])

r = status([{"part": "toaster", "detail": "x"}, {"nope": 1}, "junk", None, {"part": "wind_sensor", "detail": "y" * 5000}])
check("unknown parts and junk are ignored", r.status_code == 201 and r.get_json()["problems"] == 1)
check("very long text is cut short", len(latest_row()["device_problems"][0]["detail"]) == 200)
check("problems that is not a list is harmless", status("everything is on fire").status_code == 201)
check("an empty or broken body does not crash",
      client.post("/api/status", data="not json", headers=HEAD, content_type="text/plain").status_code == 201)
check("junk disk/queue numbers are ignored", status([], disk_free_mb="lots", queue_waiting=-4).status_code == 201)

# an old report is not shown any more
status([TEMP])
conn = site.get_db()
cur = conn.cursor()
old = (datetime.utcnow() - timedelta(hours=4)).strftime("%Y-%m-%d %H:%M:%S")
cur.execute("UPDATE device_status SET updated_at=?", (old,))
conn.commit()
conn.close()
check("a report older than 3 hours is not shown", latest_row()["device_problems"] == [])

# a broken status table must never break the main dashboard data
conn = site.get_db()
cur = conn.cursor()
cur.execute("DROP TABLE device_status")
conn.commit()
conn.close()
r = client.get("/api/latest")
check("status table missing: /api/latest still works", r.status_code == 200 and r.get_json()["readings"][0]["device_problems"] == [])
check("status table missing: /api/stats still works", client.get("/api/stats").status_code == 200)
site.init_db()
check("table is recreated on start (init_db)", status([TEMP]).status_code == 201)

# ================= Pi
stub = types.ModuleType("Adafruit_DHT")
stub.DHT22 = object()
sys.modules["Adafruit_DHT"] = stub
SRC = open("pi_sender.py", encoding="utf-8").read()
LOG = tempfile.NamedTemporaryFile(suffix=".log", delete=False).name
SRC = SRC.replace("LOG_FILE = '/home/pi/sender.log'", "LOG_FILE = %r" % LOG)
SRC = SRC.replace("QUEUE_FILE = '/home/pi/unsent_readings.jsonl'",
                  "QUEUE_FILE = %r" % os.path.join(tempfile.mkdtemp(), "q.jsonl"))
SRC = SRC.replace("WIND_WINDOW_SECONDS = 30", "WIND_WINDOW_SECONDS = 1")
import requests as real_requests  # noqa: E402


class StopLoop(BaseException):
    pass


class NoWind:
    def __init__(self, port): pass
    def read_average(self, seconds): return None


class GoodWind:
    def __init__(self, port): pass
    def read_average(self, seconds): return {"speed_mph": 5.0, "direction_deg": 90.0, "gust_mph": 6.0, "samples": 9}


def run_passes(passes, dht, wind_cls=None, status_error=None):
    """Run the real main loop for N passes. dht is a function(pass_number)->(humidity,temp)."""
    mod = types.ModuleType("Adafruit_DHT")
    mod.DHT22 = object()
    counter = {"n": 0}
    mod.read_retry = lambda *a, **k: dht(counter["n"])
    sys.modules["Adafruit_DHT"] = mod
    sys.modules.pop("wind_sensor", None)
    ws = types.ModuleType("wind_sensor")
    ws.WindSensor = wind_cls
    sys.modules["wind_sensor"] = ws

    posts = []

    def fake_post(url, json=None, headers=None, timeout=None):
        posts.append((url, json))
        if url.endswith("/api/status") and status_error:
            raise status_error
        m = MagicMock(status_code=201)
        m.json.return_value = {"alert_level": "LOW", "supports_recorded_at": True}
        return m

    def fake_sleep(seconds):
        if seconds == 300:
            counter["n"] += 1
            if counter["n"] >= passes:
                raise StopLoop

    ns = {"__name__": "pi"}
    with patch("time.sleep", side_effect=fake_sleep), patch("requests.post", side_effect=fake_post):
        try:
            exec(compile(SRC, "pi_sender.py", "exec"), ns)
        except StopLoop:
            pass
    status_posts = [b for u, b in posts if u.endswith("/api/status")]
    reading_posts = [b for u, b in posts if u.endswith("/api/reading")]
    return ns, status_posts, reading_posts


OK = (45.0, 21.0)
BAD = (None, None)

ns, sp, rp = run_passes(3, lambda n: OK, wind_cls=GoodWind)
check("healthy sensors: no status traffic at all", sp == [] and len(rp) == 3)

ns, sp, rp = run_passes(1, lambda n: BAD, wind_cls=GoodWind)
check("one failed temperature read: not reported yet (could be a blip)", sp == [])
ns, sp, rp = run_passes(2, lambda n: BAD, wind_cls=GoodWind)
check("two failed reads in a row: reported", len(sp) == 1 and sp[0]["problems"][0]["part"] == "temperature_sensor")
check("report names the device and place", sp[0]["device_id"] == "pi-library" and sp[0]["location"] == "Middleton Fire Station")
check("report includes SD card space", isinstance(sp[0]["disk_free_mb"], float))
check("report says what to check", "wires" in sp[0]["problems"][0]["detail"])
ns, sp, rp = run_passes(4, lambda n: BAD, wind_cls=GoodWind)
check("still failing: reminded every cycle so the website knows the Pi is alive", len(sp) == 3)
check("no readings are sent while the temperature chip is dead", rp == [])

ns, sp, rp = run_passes(4, lambda n: BAD if n < 2 else OK, wind_cls=GoodWind)
check("temperature recovers: one all-clear report", [len(x["problems"]) for x in sp] == [1, 0])
check("temperature recovers: readings flow again", len(rp) == 2)

ns, sp, rp = run_passes(2, lambda n: OK, wind_cls=NoWind)
check("wind silent twice: not reported yet", sp == [] and len(rp) == 2)
ns, sp, rp = run_passes(3, lambda n: OK, wind_cls=NoWind)
check("wind silent three times: reported", len(sp) == 1 and sp[0]["problems"][0]["part"] == "wind_sensor")
check("wind trouble: temperature/humidity readings still sent", len(rp) == 3)

ns, sp, rp = run_passes(5, lambda n: OK, wind_cls=None)
check("no wind sensor installed at all: never reported as a problem", sp == [] and len(rp) == 5)

ns, sp, rp = run_passes(4, lambda n: BAD, wind_cls=GoodWind, status_error=real_requests.exceptions.ConnectionError("down"))
check("status report fails: loop keeps going", len(sp) == 3)
ns, sp, rp = run_passes(3, lambda n: OK if n == 0 else BAD, wind_cls=GoodWind, status_error=RuntimeError("weird"))
check("status report crashes with a strange error: loop keeps going", len(sp) == 1)

# ================= phone alert wording
SRC_HB = open("check_heartbeat.py", encoding="utf-8").read()
os.environ["HEARTBEAT_STATE"] = os.path.join(tempfile.mkdtemp(), "s.json")


def ago(minutes):
    return (datetime.utcnow() - timedelta(minutes=minutes)).strftime("%Y-%m-%d %H:%M:%S")


def alert_text(stats):
    get = MagicMock()
    get.return_value.json.return_value = stats
    with patch("requests.get", get), patch("requests.post") as post:
        exec(compile(SRC_HB, "check_heartbeat.py", "exec"), {"__name__": "t"})
    return [c.kwargs["data"].decode() for c in post.call_args_list]


def fresh_state():
    if os.path.exists(os.environ["HEARTBEAT_STATE"]):
        os.remove(os.environ["HEARTBEAT_STATE"])


fresh_state()
a = alert_text({"last_updated": ago(40), "device_problems": [
    {"location": LOC, "part": "temperature_sensor", "detail": "x", "updated_at": ago(3)}]})
check("silent + Pi says its temperature sensor is broken: specific alert",
      len(a) == 1 and "temperature sensor is not answering" in a[0] and "Pi is on and online" in a[0])
check("that alert gives the first check and a fix time", "three wires" in a[0] and "10 minute" in a[0])

fresh_state()
a = alert_text({"last_updated": ago(40), "device_problems": [
    {"location": LOC, "part": "temperature_sensor", "detail": "x", "updated_at": ago(120)}]})
check("an old report (2 hours) proves nothing: usual power/WiFi alert", "power or WiFi" in a[0])
fresh_state()
a = alert_text({"last_updated": ago(40)})
check("silent and no report: usual power/WiFi alert", "power or WiFi" in a[0])
fresh_state()
a = alert_text({"last_updated": ago(40), "device_problems": [
    {"location": LOC, "part": "wind_sensor", "detail": "x", "updated_at": ago(3)}]})
check("silent and only the wind part reported: still the usual alert", "power or WiFi" in a[0])
fresh_state()
a = alert_text({"last_updated": ago(40), "device_problems": [{"part": "temperature_sensor"}]})
check("a damaged report never crashes the alert check", len(a) == 1)

print(f"\n{passed} passed, {failed} failed")
raise SystemExit(1 if failed else 0)
