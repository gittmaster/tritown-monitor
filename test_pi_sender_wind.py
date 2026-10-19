"""
Offline test for the wind additions to pi_sender.py.

pi_sender.py normally needs the Pi's temperature chip library and runs forever,
so this loads only its setup section (everything before the main loop) with
stand-ins. No hardware, no network.   Usage: python test_pi_sender_wind.py
"""
import sys
import tempfile
import types
from unittest.mock import patch, MagicMock

passed = failed = 0


def check(label, condition):
    global passed, failed
    if condition:
        passed += 1
        print(f"[PASS] {label}")
    else:
        failed += 1
        print(f"[FAIL] {label}")


src = open("pi_sender.py", encoding="utf-8").read()
check("main loop still reads wind inside a try/except",
      "wind = wind_sensor.read_average(WIND_WINDOW_SECONDS)" in src
      and "except Exception as e:   # belt and braces" in src)
check("main loop sends wind along with temperature and humidity",
      "send_reading(temp_c, humidity, wind)" in src)

# stand-ins for the Pi-only library, and a log file we can write anywhere
stub = types.ModuleType("Adafruit_DHT")
stub.DHT22 = object()
sys.modules["Adafruit_DHT"] = stub
logfile = tempfile.NamedTemporaryFile(suffix=".log", delete=False).name
setup = src.split("consecutive_failures = 0")[0].replace(
    "LOG_FILE = '/home/pi/sender.log'", "LOG_FILE = %r" % logfile)
ns = {"__name__": "pi_sender_under_test"}
exec(compile(setup, "pi_sender.py", "exec"), ns)

send_reading = ns["send_reading"]
ok = MagicMock(status_code=201)
ok.json.return_value = {"alert_level": "LOW"}

with patch.object(ns["requests"], "post", return_value=ok) as post:
    wind = {"speed_mph": 8.34, "direction_deg": 270.46, "gust_mph": 12.0, "samples": 15}
    check("send with wind succeeds", send_reading(20.0, 50.0, wind) is True)
    body = post.call_args.kwargs["json"]
    check("payload carries wind_speed (mph, 1 decimal)", body.get("wind_speed") == 8.3)
    check("payload carries wind_direction (degrees, 1 decimal)", body.get("wind_direction") == 270.5)
    check("temperature and humidity are still in the payload",
          body["temperature"] == 20.0 and body["humidity"] == 50.0)

with patch.object(ns["requests"], "post", return_value=ok) as post:
    check("send WITHOUT wind still succeeds (sensor missing)", send_reading(20.0, 50.0) is True)
    body = post.call_args.kwargs["json"]
    check("payload has no wind keys when there is no wind reading",
          "wind_speed" not in body and "wind_direction" not in body)

with patch.object(ns["requests"], "post", return_value=ok) as post:
    send_reading(20.0, 50.0, None)
    check("wind=None behaves like no wind", "wind_speed" not in post.call_args.kwargs["json"])

with patch.object(ns["requests"], "post", return_value=ok) as post:
    send_reading(20.0, 50.0, {"speed_mph": 0.0, "direction_deg": 0.0})
    body = post.call_args.kwargs["json"]
    check("calm wind (0 mph, 0 deg) is sent as a real value, not dropped",
          body.get("wind_speed") == 0.0 and body.get("wind_direction") == 0.0)

print(f"\n{passed} passed, {failed} failed")
raise SystemExit(1 if failed else 0)
