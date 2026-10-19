"""
Offline test: the class-day method is wired into the website behind a switch
(ALERT_METHOD), OFF by default, with safe fallbacks. Temporary database.
Usage: python test_class_day_wiring.py
"""
import os
import tempfile

_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_db.close()
os.environ["DB_PATH"] = _db.name
os.environ.pop("DATABASE_URL", None)
os.environ.pop("ALERT_METHOD", None)
os.environ.pop("HERBACEOUS_STAGE", None)

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


def f_to_c(f):
    return (f - 32) * 5.0 / 9.0


def post(temp_f, rh, wind, loc="Test"):
    body = {"device_id": "d", "location": loc, "temperature": f_to_c(temp_f), "humidity": rh, "dew_point": 5.0}
    if wind is not None:
        body["wind_speed"] = wind
        body["wind_direction"] = 90.0
    return client.post("/api/reading", json=body, headers=HEAD).get_json()


def stats():
    return client.get("/api/stats").get_json()


# ---- OFF by default: exactly the original behaviour
check("default method is the original rule", site.ALERT_METHOD == "legacy" and stats()["alert_method"] == "legacy")
cases = [(90, 10, 30), (82, 42, 14), (63, 85, 5), (75, 28, None), (55, 60, 3)]
same = all(post(t, rh, w)["alert_level"] == site.get_alert(f_to_c(t), rh, None, w)[0] for t, rh, w in cases)
check("with the switch off, every answer equals the original rule", same)

# ---- ON: Ben's examples
site.ALERT_METHOD = "class_day"
check("stats report the new method", stats()["alert_method"] == "class_day")
check("Ben #1 (82F, 42%, 14 mph, Transition) -> EXTREME (class 5)", post(82, 42, 14)["alert_level"] == "EXTREME")
check("Ben #2 (63F, 85%, 5 mph) with Green -> LOW (class 1)",
      (setattr(site, "HERBACEOUS_STAGE", "green"), post(63, 85, 5)["alert_level"])[1] == "LOW")
check("Ben #3 (96F, 30%, 17 mph) with Cured -> EXTREME",
      (setattr(site, "HERBACEOUS_STAGE", "cured"), post(96, 30, 17)["alert_level"])[1] == "EXTREME")
check("stats report the stage in use", stats()["herbaceous_stage"] == "cured")
site.HERBACEOUS_STAGE = "transition"

# the same air gives a different answer when the stage changes
site.HERBACEOUS_STAGE = "green"
green = post(70, 40, 10)["alert_level"]
site.HERBACEOUS_STAGE = "cured"
cured = post(70, 40, 10)["alert_level"]
levels = ["LOW", "MODERATE", "HIGH", "VERY_HIGH", "EXTREME"]
check("cured grass is at least as dangerous as green grass (same air, same wind)",
      levels.index(cured) >= levels.index(green))
site.HERBACEOUS_STAGE = "transition"

# the stored reading carries the new level and one of the known messages
rows = client.get("/api/latest").get_json()["readings"]
known = set(site.class_day.MESSAGES.values())
check("every stored message is a known class-day message (or the no-wind note)",
      all(r["alert_message"] in known or r["alert_message"].startswith("Wind data not available") for r in rows))

# ---- the 7-day forecast uses the same method
from unittest.mock import patch  # noqa: E402

FAKE_DAILY = {"place_name": "Middleton, MA", "periods": [{"name": "Today", "temperature_f": 82, "short_forecast": "Sunny"}]}
FAKE_HOURLY = {"place_name": "Middleton, MA", "hours": [
    {"time": "2026-10-20T14:00:00", "temperature_c": f_to_c(82), "temperature_f": 82.0, "humidity_pct": 42, "wind_speed_mph": 14.0},
    {"time": "2026-10-20T15:00:00", "temperature_c": f_to_c(82), "temperature_f": 82.0, "humidity_pct": 42, "wind_speed_mph": None},
]}
site._forecast_cache.clear()
site.HERBACEOUS_STAGE = "transition"
with patch("weather_forecast.get_forecast", return_value=FAKE_DAILY), \
     patch("weather_forecast.get_hourly_projection", return_value=FAKE_HOURLY):
    hours = client.get("/api/forecast?zip=01949").get_json()["hourly"]
check("forecast hour with wind uses the class-day answer (EXTREME)", hours[0]["alert_level"] == "EXTREME")
check("forecast hour without wind falls back and says so", hours[1]["alert_message"].startswith("Wind data not available"))
site.ALERT_METHOD = "legacy"
site._forecast_cache.clear()
with patch("weather_forecast.get_forecast", return_value=FAKE_DAILY), \
     patch("weather_forecast.get_hourly_projection", return_value=FAKE_HOURLY):
    hours = client.get("/api/forecast?zip=01949").get_json()["hourly"]
check("switch off: forecast is the original rule again", hours[0]["alert_level"] == site.get_alert(f_to_c(82), 42, None, 14.0)[0])
site.ALERT_METHOD = "class_day"

# ---- no wind data
r = post(82, 42, None, loc="NoWind")
row = [x for x in client.get("/api/latest").get_json()["readings"] if x["location"] == "NoWind"][0]
check("no wind: reading still accepted with a normal dashboard level", r["alert_level"] in levels)
check("no wind: message says wind was not available", row["alert_message"].startswith("Wind data not available"))
check("no wind: level is the original rule's estimate", r["alert_level"] == site.get_alert(f_to_c(82), 42, None, None)[0])

# ---- safety nets
real = site.class_day.assess
def boom(*a, **k):
    raise RuntimeError("chart exploded")
site.class_day.assess = boom
r = post(90, 10, 30)
check("new method crashes: reading still accepted, original rule used", r["alert_level"] == site.get_alert(f_to_c(90), 10, None, 30)[0])
site.class_day.assess = real

holder = site.class_day
site.class_day = None
check("class_day.py missing: original rule used", post(90, 10, 30)["alert_level"] == site.get_alert(f_to_c(90), 10, None, 30)[0])
check("class_day.py missing: stats say legacy, not class_day", stats()["alert_method"] == "legacy")
site.class_day = holder

# unusual settings never break anything
site.ALERT_METHOD = "something-else"
check("unknown method name behaves like the original rule", post(82, 42, 14)["alert_level"] == site.get_alert(f_to_c(82), 42, None, 14)[0])
site.ALERT_METHOD = "legacy"

# a bad stage in the host setting falls back to transition (checked at start-up)
import importlib
os.environ["HERBACEOUS_STAGE"] = "sprouting"
os.environ["ALERT_METHOD"] = " Class_Day "
fresh = importlib.reload(site)
check("bad stage setting falls back to transition", fresh.HERBACEOUS_STAGE == "transition")
check("method setting ignores spaces and capital letters", fresh.ALERT_METHOD == "class_day")

print(f"\n{passed} passed, {failed} failed")
raise SystemExit(1 if failed else 0)
