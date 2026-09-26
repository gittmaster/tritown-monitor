"""
Tests the /api/forecast Flask route end-to-end, with weather_forecast's
network calls mocked out - so this runs fully offline, exercising the
real route code (including get_alert() integration) without needing a
live server or live network access.
Usage: python test_forecast_route.py
"""
from unittest.mock import patch
import app as app_module

passed = failed = 0


def check(label, condition):
    global passed, failed
    if condition:
        passed += 1
        print(f"[PASS] {label}")
    else:
        failed += 1
        print(f"[FAIL] {label}")


FAKE_DAILY = {
    "place_name": "Middleton, MA",
    "periods": [
        {"name": "This Afternoon", "temperature_f": 59, "short_forecast": "Patchy Fog"},
    ],
}
FAKE_HOURLY = {
    "place_name": "Middleton, MA",
    "hours": [
        # Deliberately severe values, to check get_alert() gets wired up
        # correctly and actually runs on each hour.
        {"time": "2026-09-26T14:00:00", "temperature_c": 30.0, "temperature_f": 86.0,
         "humidity_pct": 10, "wind_speed_mph": 30.0},
        {"time": "2026-09-26T15:00:00", "temperature_c": 20.0, "temperature_f": 68.0,
         "humidity_pct": 60, "wind_speed_mph": 5.0},
    ],
}

client = app_module.app.test_client()

with patch("weather_forecast.get_forecast", return_value=FAKE_DAILY), \
     patch("weather_forecast.get_hourly_projection", return_value=FAKE_HOURLY):
    resp = client.get("/api/forecast?zip=01949")
    data = resp.get_json()

    check("route returns 200", resp.status_code == 200)
    check("route returns place_name", data["place_name"] == "Middleton, MA")
    check("route returns daily periods", len(data["daily"]) == 1)
    check("route returns hourly data", len(data["hourly"]) == 2)
    check("route computes EXTREME alert for severe hour",
          data["hourly"][0]["alert_level"] == "EXTREME")
    check("route computes LOW alert for mild hour",
          data["hourly"][1]["alert_level"] == "LOW")
    check("route includes alert_message", "alert_message" in data["hourly"][0])

with patch("weather_forecast.get_forecast", side_effect=Exception("network down")):
    resp = client.get("/api/forecast?zip=01949")
    check("route returns 502 on upstream failure", resp.status_code == 502)
    check("route error response has 'error' key", "error" in resp.get_json())

print(f"\n{passed} passed, {failed} failed")
