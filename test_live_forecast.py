"""
REAL end-to-end test - hits the live Zippopotam.us and api.weather.gov
APIs over the network. Run this yourself in your own terminal (not
through any Claude tool), since it needs your machine's normal internet
connection.

Usage: python test_live_forecast.py [zip_code]
"""
import sys
from weather_forecast import get_forecast, get_hourly_projection

zip_code = sys.argv[1] if len(sys.argv) > 1 else "01949"

print(f"Testing live forecast for ZIP {zip_code}...\n")

print("--- Daily forecast ---")
try:
    daily = get_forecast(zip_code)
    print(f"Place: {daily['place_name']}")
    for p in daily["periods"][:4]:
        print(f"  {p['name']:20s} {p['temperature_f']:>3}F  "
              f"wind {p['wind_speed_mph']}mph  {p['short_forecast']}")
    print(f"PASS: got {len(daily['periods'])} forecast periods\n")
except Exception as e:
    print(f"FAIL: {e}\n")
    sys.exit(1)

print("--- Hourly projection (with computed fire-danger alerts) ---")
try:
    hourly = get_hourly_projection(zip_code, hours=24)
    print(f"Place: {hourly['place_name']}")
    from app import get_alert
    for h in hourly["hours"][:6]:
        level, _ = get_alert(h["temperature_c"], h["humidity_pct"], wind_speed=h["wind_speed_mph"])
        print(f"  {h['time']}  {h['temperature_f']:>5}F  "
              f"{h['humidity_pct']:>3}% RH  {h['wind_speed_mph']:>5} mph  -> {level}")
    print(f"PASS: got {len(hourly['hours'])} hourly readings\n")
except Exception as e:
    print(f"FAIL: {e}\n")
    sys.exit(1)

print("All live checks passed.")
