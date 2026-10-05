"""
Local, offline test for the fire-danger alert logic in app.py.
Runs entirely on your machine — no network, no database, no live site.
Usage: python test_alerts.py
"""
from app import get_alert

def c(f):
    """Convert Fahrenheit to Celsius (get_alert takes temp_c)."""
    return (f - 32) * 5 / 9

cases = [
    # (label, temp_f, humidity, wind_speed, expected_level)
    ("Calm summer day",           75, 60, 0,   "LOW"),
    ("Warm + dry afternoon",      65, 45, 0,   "MODERATE"),
    ("Hot + dry",                 72, 25, 0,   "HIGH"),
    ("Very hot + very dry",       82, 18, 0,   "VERY_HIGH"),
    ("Extreme conditions + wind", 90, 10, 30,  "EXTREME"),
    ("Extreme temp/humidity, NO wind data (known bug)", 90, 10, None, "EXTREME"),
]

passed = 0
failed = 0
for label, temp_f, humidity, wind, expected in cases:
    level, _ = get_alert(c(temp_f), humidity, wind_speed=wind)
    ok = (level == expected)
    status = "PASS" if ok else "FAIL"
    if ok:
        passed += 1
    else:
        failed += 1
    print(f"[{status}] {label}: temp={temp_f}F humidity={humidity}% wind={wind} -> got {level}, expected {expected}")

print(f"\n{passed} passed, {failed} failed")
