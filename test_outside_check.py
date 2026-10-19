"""
Offline test for outside_check.py (the backup watchdog that runs off the Pi).
Usage: python test_outside_check.py
"""
from datetime import datetime, timedelta

import outside_check as oc

passed = failed = 0


def check(label, condition):
    global passed, failed
    if condition:
        passed += 1
        print(f"[PASS] {label}")
    else:
        failed += 1
        print(f"[FAIL] {label}")


NOW = datetime(2026, 10, 18, 12, 0, 0)


def stamp(minutes):
    return (NOW - timedelta(minutes=minutes)).strftime("%Y-%m-%d %H:%M:%S.123456")


def run(fetch):
    pauses = []
    result = oc.check(fetch=fetch, now=NOW, sleep=pauses.append)
    return result, pauses


check("fresh data (3 min): no alert", run(lambda: {"last_updated": stamp(3)})[0] is None)
check("20 min old: no alert (the Pi's own check handles that)", run(lambda: {"last_updated": stamp(20)})[0] is None)
check("44 min old: no alert yet", run(lambda: {"last_updated": stamp(44)})[0] is None)
msg = run(lambda: {"last_updated": stamp(50)})[0]
check("50 min old: alert", msg is not None and "50 minutes" in msg)
check("alert says what, the likely cause, the first check and a fix time",
      "Pi" in msg and "power or WiFi" in msg and "First check" in msg and "5 to 10 minutes" in msg)
check("alert says a dead Pi cannot warn you itself", "cannot warn you itself" in msg)

msg = run(lambda: {"last_updated": None})[0]
check("empty database: alert", msg is not None and "no readings" in msg)

calls = []
def always_down():
    calls.append(1)
    raise ConnectionError("timed out")
msg, pauses = run(always_down)
check("website down: tries 3 times then alerts", len(calls) == 3 and msg is not None and "did not answer" in msg)
check("website down: waits between tries", len(pauses) == 2)
check("website down: alert says what to check", "Render" in msg and "30 minutes" in msg)

seq = iter([ConnectionError("waking up"), {"last_updated": stamp(2)}])
def wakes_up():
    v = next(seq)
    if isinstance(v, Exception):
        raise v
    return v
msg, pauses = run(wakes_up)
check("website slow to wake: second try works, no alert", msg is None and len(pauses) == 1)

check("garbage answer (a list): alert, no crash", run(lambda: ["nope"])[0] is not None)
check("garbage time text: alert, no crash", run(lambda: {"last_updated": "yesterday"})[0] is not None)

check("workflow file runs the script on a schedule", "outside_check.py" in open(".github/workflows/outside-check.yml", encoding="utf-8").read()
      and "cron" in open(".github/workflows/outside-check.yml", encoding="utf-8").read())

print(f"\n{passed} passed, {failed} failed")
raise SystemExit(1 if failed else 0)
