"""
Offline test for the wind warning added to check_heartbeat.py.
The network is replaced with stand-ins; no alerts are really sent.
Usage: python test_heartbeat_wind.py
"""
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


def ago(minutes):
    return (datetime.utcnow() - timedelta(minutes=minutes)).strftime("%Y-%m-%d %H:%M:%S.123456")


def alerts_for(stats):
    """Run the heartbeat script against fake stats; return the alert texts it would send."""
    get = MagicMock()
    get.return_value.json.return_value = stats
    with patch("requests.get", get), patch("requests.post") as post:
        exec(compile(SRC, "check_heartbeat.py", "exec"), {"__name__": "heartbeat_under_test"})
    return [c.kwargs["data"].decode() for c in post.call_args_list]


# Existing behaviour first: it must be exactly as before.
check("fresh data, no wind info (old server): no alert",
      alerts_for({"last_updated": ago(3)}) == [])
a = alerts_for({"last_updated": ago(40)})
check("no data for 40 min: the original alert still fires", len(a) == 1 and "No sensor data" in a[0])
check("empty database: the original alert still fires",
      "No data in database" in alerts_for({"last_updated": None})[0])

# New wind behaviour.
check("no wind sensor ever (wind_last_seen null): no alert, no nagging",
      alerts_for({"last_updated": ago(3), "wind_last_seen": None}) == [])
check("wind reporting normally (5 min ago): no alert",
      alerts_for({"last_updated": ago(3), "wind_last_seen": ago(5)}) == [])
check("wind a bit late (20 min ago): no alert yet",
      alerts_for({"last_updated": ago(3), "wind_last_seen": ago(20)}) == [])
a = alerts_for({"last_updated": ago(3), "wind_last_seen": ago(45)})
check("wind silent 45 min while temperature is fine: ONE wind alert", len(a) == 1 and "Wind sensor" in a[0])
check("wind alert says temperature and humidity are still OK", "still OK" in a[0])
a = alerts_for({"last_updated": ago(40), "wind_last_seen": ago(45)})
check("whole station silent: only the original alert, not a second wind alert",
      len(a) == 1 and "No sensor data" in a[0])

print(f"\n{passed} passed, {failed} failed")
raise SystemExit(1 if failed else 0)
