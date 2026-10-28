"""
Runs the WHOLE pi_sender.py main loop (one pass) through every way the wind
sensor can fail, and checks that temperature and humidity are ALWAYS still
sent, exactly as they were before wind existed.

Uses stand-ins for the Pi's temperature chip, the network and the clock, so it
needs no hardware and takes about a second.   Usage: python test_pi_sender_resilience.py
"""
import importlib
import os
import sys
import tempfile
import types

os.environ.setdefault('TRITOWN_API_KEY', 'test-key')   # the Pi sender reads its key from settings
from unittest.mock import MagicMock, patch

passed = failed = 0


def check(label, condition):
    global passed, failed
    if condition:
        passed += 1
        print(f"[PASS] {label}")
    else:
        failed += 1
        print(f"[FAIL] {label}")


class StopLoop(BaseException):
    """Ends the endless loop after one pass (BaseException so the loop can't swallow it)."""


SRC = open("pi_sender.py", encoding="utf-8").read()
LOGFILE = tempfile.NamedTemporaryFile(suffix=".log", delete=False).name
SRC = SRC.replace("LOG_FILE = '/home/pi/sender.log'", "LOG_FILE = %r" % LOGFILE)
SRC = SRC.replace("WIND_WINDOW_SECONDS = 30", "WIND_WINDOW_SECONDS = 2")  # keep the test fast
OLD_KEYS = {"device_id", "location", "temperature", "humidity", "dew_point"}


def run_loop(dht_result=(45.0, 21.0), wind_cls=None, wind_module="stub", post_status=201):
    """One pass of the main loop. Returns (namespace, mocked requests.post)."""
    dht = types.ModuleType("Adafruit_DHT")
    dht.DHT22 = object()
    dht.read_retry = lambda *a, **k: dht_result
    sys.modules["Adafruit_DHT"] = dht

    sys.modules.pop("wind_sensor", None)
    if wind_module == "missing":
        sys.modules["wind_sensor"] = None            # makes `import wind_sensor` fail
    elif wind_module == "stub":
        stub = types.ModuleType("wind_sensor")
        stub.WindSensor = wind_cls
        sys.modules["wind_sensor"] = stub
    # wind_module == "real": let the real wind_sensor.py import normally

    ok = MagicMock(status_code=post_status)
    ok.json.return_value = {"alert_level": "LOW"}

    def fake_sleep(seconds):
        if seconds == 300:        # INTERVAL: the loop reached the end of its first pass
            raise StopLoop

    ns = {"__name__": "pi_sender_under_test"}
    with patch("time.sleep", side_effect=fake_sleep), \
         patch("requests.post", return_value=ok) as post:
        try:
            exec(compile(SRC, "pi_sender.py", "exec"), ns)
        except StopLoop:
            pass
    return ns, post


class GoodWind:
    def __init__(self, port): pass
    def read_average(self, seconds):
        return {"speed_mph": 9.0, "direction_deg": 200.0, "gust_mph": 12.0, "samples": 15}

class NoneWind:
    def __init__(self, port): pass
    def read_average(self, seconds): return None

class RaisingWind:
    def __init__(self, port): pass
    def read_average(self, seconds): raise RuntimeError("sensor exploded")

class BrokenConstructor:
    def __init__(self, port): raise RuntimeError("cannot even start")


# 1. everything healthy
ns, post = run_loop(wind_cls=GoodWind)
body = post.call_args.kwargs["json"]
check("healthy sensor: reading sent once", post.call_count == 1)
check("healthy sensor: wind included", body["wind_speed"] == 9.0 and body["wind_direction"] == 200.0)
check("healthy sensor: temperature/humidity unchanged", body["temperature"] == 21.0 and body["humidity"] == 45.0)

# 2. sensor answers nothing
ns, post = run_loop(wind_cls=NoneWind)
body = post.call_args.kwargs["json"]
check("wind returns nothing: reading STILL sent", post.call_count == 1)
check("wind returns nothing: payload identical to the pre-wind payload", set(body) == OLD_KEYS)

# 3. sensor code blows up
ns, post = run_loop(wind_cls=RaisingWind)
body = post.call_args.kwargs["json"]
check("wind raises an error: reading STILL sent", post.call_count == 1)
check("wind raises an error: payload identical to the pre-wind payload", set(body) == OLD_KEYS)
check("wind raises an error: loop not counted as a failure", ns["consecutive_failures"] == 0)

# 4. wind_sensor.py was never copied to the Pi
ns, post = run_loop(wind_module="missing")
body = post.call_args.kwargs["json"]
check("wind_sensor.py missing: reading STILL sent", post.call_count == 1 and set(body) == OLD_KEYS)

# 5. wind reader cannot even be created
ns, post = run_loop(wind_cls=BrokenConstructor)
body = post.call_args.kwargs["json"]
check("wind reader fails at startup: reading STILL sent", post.call_count == 1 and set(body) == OLD_KEYS)

# 6. the REAL wind_sensor.py with no adapter plugged in
ns, post = run_loop(wind_module="real")
body = post.call_args.kwargs["json"]
check("real wind code, adapter unplugged: reading STILL sent", post.call_count == 1)
check("real wind code, adapter unplugged: payload identical to pre-wind", set(body) == OLD_KEYS)

# 7. the temperature chip fails (existing behaviour must be unchanged)
ns, post = run_loop(dht_result=(None, None), wind_cls=GoodWind)
check("temperature chip fails: nothing is sent", post.call_count == 0)
check("temperature chip fails: counted as a failure (existing behaviour)", ns["consecutive_failures"] == 1)

# 8. the website is down (existing behaviour must be unchanged)
ns, post = run_loop(wind_cls=GoodWind, post_status=500)
check("website down: retries 3 times, as before", post.call_count == 3)
check("website down: counted as a failure (existing behaviour)", ns["consecutive_failures"] == 1)

print(f"\n{passed} passed, {failed} failed")
raise SystemExit(1 if failed else 0)
