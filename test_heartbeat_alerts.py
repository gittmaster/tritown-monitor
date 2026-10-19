"""
Offline test for the alert messages, hourly reminder limit and "back to normal"
message in check_heartbeat.py. The network is replaced; nothing is really sent.
Usage: python test_heartbeat_alerts.py
"""
import json
import os
import tempfile
import time
from datetime import datetime, timedelta
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


SRC = open("check_heartbeat.py", encoding="utf-8").read()
STATE = os.path.join(tempfile.mkdtemp(), "state.json")
os.environ["HEARTBEAT_STATE"] = STATE


def ago(minutes):
    return (datetime.utcnow() - timedelta(minutes=minutes)).strftime("%Y-%m-%d %H:%M:%S.123456")


def run(stats=None, get_error=None, post_error=None):
    """Run one heartbeat check; return list of (title, text) notifications attempted."""
    get = MagicMock()
    if get_error:
        get.side_effect = get_error
    else:
        get.return_value.json.return_value = stats
    post = MagicMock()
    if post_error:
        post.side_effect = post_error
    with patch("requests.get", get), patch("requests.post", post):
        exec(compile(SRC, "check_heartbeat.py", "exec"), {"__name__": "t"})
    return [(c.kwargs["headers"]["Title"], c.kwargs["data"].decode()) for c in post.call_args_list]


def reset():
    if os.path.exists(STATE):
        os.remove(STATE)


def age_state(minutes):
    s = json.load(open(STATE))
    json.dump({k: v - minutes * 60 for k, v in s.items()}, open(STATE, "w"))


# Messages are plain and say what / likely cause / what to check / how long.
reset()
a = run({"last_updated": ago(40)})
check("silent station: one alert", len(a) == 1)
t = a[0][1]
check("silent message says PROBLEM and how many minutes", "PROBLEM" in t and "40 minutes" in t)
check("silent message gives a likely cause", "power or WiFi" in t)
check("silent message gives a first check", "First check" in t)
check("silent message gives a fix time", "5 to 10 minutes" in t)

reset()
t = run({"last_updated": ago(3), "wind_last_seen": ago(45)})[0][1]
check("wind message: cause, first check, fix time",
      "USB adapter" in t and "First check" in t and "10 minute" in t)
check("wind message says temperature and humidity are fine", "still OK" in t)

reset()
t = run(get_error=ConnectionError("boom"))[0][1]
check("website down message: says what, wait 15 min, fix time",
      "website did not answer" in t and "15 minutes" in t and "30 minutes" in t)

# Reminder limit.
reset()
run({"last_updated": ago(40)})
check("same problem 15 min later: no second alert", run({"last_updated": ago(55)}) == [])
age_state(61)
check("same problem 61 min later: one reminder", len(run({"last_updated": ago(100)})) == 1)

# A different problem is announced immediately.
reset()
run({"last_updated": ago(3), "wind_last_seen": ago(45)})
a = run({"last_updated": ago(40), "wind_last_seen": ago(45)})
check("wind problem then whole station silent: new alert right away",
      len(a) == 1 and "No sensor data" in a[0][1])

# Back to normal.
reset()
run({"last_updated": ago(40)})
a = run({"last_updated": ago(2)})
check("problem fixed: one RESOLVED message", len(a) == 1 and "RESOLVED" in a[0][1])
check("RESOLVED uses a calm title", a[0][0] == "TriTown Monitor OK")
check("after RESOLVED, nothing more is sent", run({"last_updated": ago(2)}) == [])
reset()
check("healthy and no prior problem: silent", run({"last_updated": ago(2)}) == [])

# When the phone message cannot be sent, it retries next run and never crashes.
reset()
run({"last_updated": ago(40)}, post_error=ConnectionError("no internet"))
check("send failed: problem not marked as alerted", not os.path.exists(STATE) or json.load(open(STATE)) == {})
check("next run retries the alert", len(run({"last_updated": ago(55)})) == 1)

# Unwritable state file: still alerts (old behaviour), never crashes.
os.environ["HEARTBEAT_STATE"] = os.path.join(tempfile.mkdtemp(), "no_such_dir", "s.json")
a = run({"last_updated": ago(40)})
check("cannot save state: still sends the alert", len(a) == 1)
check("cannot save state: healthy run is quiet", run({"last_updated": ago(2)}) == [])

print(f"\n{passed} passed, {failed} failed")
raise SystemExit(1 if failed else 0)
