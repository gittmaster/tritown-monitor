"""
Offline test for saving readings during an outage and resending them.

Part 1 tests reading_queue.py directly (limits, damaged files, power cuts).
Part 2 runs the real pi_sender.py send logic against pretend internet/website
failures. No hardware, no network, temporary files only.
Usage: python test_reading_queue.py
"""
import json
import os
import sys
import tempfile
import types
from collections import namedtuple
from datetime import datetime
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


from reading_queue import ReadingQueue  # noqa: E402

DAY = 86400
Usage = namedtuple("Usage", "total used free")
GB = 1024 ** 3


def tmpfile():
    return os.path.join(tempfile.mkdtemp(), "unsent.jsonl")


class Clock:
    def __init__(self, t=1_800_000_000.0): self.t = t
    def __call__(self): return self.t


def reading(n):
    return {"device_id": "pi", "temperature": 20.0 + n, "recorded_at": "2026-10-18T10:%02d:00" % (n % 60)}


# ============ Part 1: the queue itself
clock = Clock()
q = ReadingQueue(tmpfile(), clock=clock, disk_usage=lambda p: Usage(32 * GB, 1 * GB, 31 * GB))
check("empty queue: nothing waiting", q.count() == 0)
check("empty queue: flush does nothing", q.flush(lambda p: True) == (0, 0))
for i in range(5):
    q.add(reading(i))
check("five readings saved", q.count() == 5)

order = []
sent, left = q.flush(lambda p: order.append(p["temperature"]) or True)
check("all five resent, oldest first", sent == 5 and left == 0 and order == [20.0, 21.0, 22.0, 23.0, 24.0])
check("queue is empty afterwards", q.count() == 0)

for i in range(6):
    q.add(reading(i))
calls = []
def fail_on_third(p):
    calls.append(1)
    return len(calls) < 3
sent, left = q.flush(fail_on_third)
check("website fails part-way: stops at the first failure", sent == 2 and left == 4)
check("the unsent ones are still saved, in order", [e["payload"]["temperature"] for e in q._load()] == [22.0, 23.0, 24.0, 25.0])
check("a send function that crashes is handled", q.flush(lambda p: 1 / 0) in [(0, 4)])
check("nothing was lost by the crash", q.count() == 4)

# power cut / damaged file
path = tmpfile()
q2 = ReadingQueue(path, clock=clock, disk_usage=lambda p: Usage(32 * GB, 1 * GB, 31 * GB))
q2.add(reading(1))
with open(path, "a") as f:
    f.write("{this is damaged\n")
    f.write("\n")
    f.write('["not", "an", "entry"]\n')
q2.add(reading(2))
check("damaged lines are skipped, good ones kept", q2.count() == 2)
sent, left = q2.flush(lambda p: True)
check("damaged lines never block resending", sent == 2 and left == 0)
check("damaged lines are cleaned out", open(path).read() == "")
check("no half-written temp file is left behind", not os.path.exists(path + ".tmp"))

# time limit on each resend run
clock2 = Clock()
q3 = ReadingQueue(tmpfile(), clock=clock2, disk_usage=lambda p: Usage(32 * GB, 1 * GB, 31 * GB))
for i in range(10):
    q3.add(reading(i))
def slow(p):
    clock2.t += 50
    return True
sent, left = q3.flush(slow, max_seconds=120)
check("a long catch-up stops after its time budget and continues next run", 0 < sent < 10 and sent + left == 10)

# age limit: 60 days
clock4 = Clock()
q4 = ReadingQueue(tmpfile(), clock=clock4, max_days=60, disk_usage=lambda p: Usage(32 * GB, 1 * GB, 31 * GB))
q4.add(reading(1))
clock4.t += 61 * DAY
q4.add(reading(2))
check("older than 60 days: dropped, newer kept", q4.count() == 1 and q4._load()[0]["payload"]["temperature"] == 22.0)
q4b = ReadingQueue(tmpfile(), clock=clock4, max_days=30, disk_usage=lambda p: Usage(32 * GB, 1 * GB, 31 * GB))
q4b.add(reading(1))
clock4.t += 31 * DAY
q4b.add(reading(2))
check("the age limit is a setting (30 days)", q4b.count() == 1)

# size limit
q5 = ReadingQueue(tmpfile(), clock=Clock(), max_bytes=2000, disk_usage=lambda p: Usage(32 * GB, 1 * GB, 31 * GB))
for i in range(100):
    q5.add(reading(i))
size = os.path.getsize(q5.path)
check("file never grows past its size cap", size <= 2000)
check("when trimming, the newest readings survive", q5._load()[-1]["payload"]["temperature"] == 119.0)

# nearly-full SD card
q6 = ReadingQueue(tmpfile(), clock=Clock(), disk_usage=lambda p: Usage(32 * GB, 31 * GB, 50 * 1024 * 1024))
for i in range(10):
    q6.add(reading(i))
check("SD card nearly full: oldest readings dropped to make room, newest kept",
      0 < q6.count() < 10 and q6._load()[-1]["payload"]["temperature"] == 29.0)

q7 = ReadingQueue(tmpfile(), clock=Clock(), disk_usage=lambda p: (_ for _ in ()).throw(OSError("no info")))
q7.add(reading(1))
check("cannot read free space: still saves", q7.count() == 1)

# cannot write at all
logged = []
q8 = ReadingQueue("/this/folder/does/not/exist/q.jsonl", log=logged.append)
check("cannot write the file: returns False, no crash", q8.add(reading(1)) is False and q8.count() == 0)
check("cannot write the file: a message is logged", any("could not save" in m for m in logged))

# saved data survives a Pi restart (a brand-new queue object on the same file)
path = tmpfile()
ReadingQueue(path, disk_usage=lambda p: Usage(32 * GB, 1 * GB, 31 * GB)).add(reading(7))
again = ReadingQueue(path, disk_usage=lambda p: Usage(32 * GB, 1 * GB, 31 * GB))
check("readings survive a Pi restart", again.count() == 1)

# ============ Part 2: the real sender logic
stub = types.ModuleType("Adafruit_DHT")
stub.DHT22 = object()
sys.modules["Adafruit_DHT"] = stub
SRC = open("pi_sender.py", encoding="utf-8").read()
LOG = tempfile.NamedTemporaryFile(suffix=".log", delete=False).name
setup = SRC.split("consecutive_failures = 0")[0].replace("LOG_FILE = '/home/pi/sender.log'", "LOG_FILE = %r" % LOG)


def fresh_sender():
    qpath = tmpfile()
    code = setup.replace("QUEUE_FILE = '/home/pi/unsent_readings.jsonl'", "QUEUE_FILE = %r" % qpath)
    ns = {"__name__": "sender_under_test"}
    exec(compile(code, "pi_sender.py", "exec"), ns)
    return ns, qpath


def response(status, supports=True):
    r = MagicMock(status_code=status)
    r.json.return_value = {"alert_level": "LOW", "supports_recorded_at": supports}
    return r


import requests as real_requests  # noqa: E402

with patch("time.sleep"):
    # website healthy: nothing saved, payload exactly as before
    ns, qpath = fresh_sender()
    with patch.object(ns["requests"], "post", return_value=response(201)) as post:
        check("healthy: sent and nothing saved", ns["send_reading"](20.0, 50.0) is True and ns["saved_queue"].count() == 0)
        check("healthy: live reading carries no recorded_at (website stamps arrival)", "recorded_at" not in post.call_args.kwargs["json"])

    # internet down
    ns, qpath = fresh_sender()
    with patch.object(ns["requests"], "post", side_effect=real_requests.exceptions.ConnectionError("down")) as post:
        check("internet down: 3 tries then failure, as before", ns["send_reading"](20.0, 50.0) is False and post.call_count == 3)
    check("internet down: the reading was saved", ns["saved_queue"].count() == 1)
    saved = ns["saved_queue"]._load()[0]["payload"]
    check("saved reading has its original time", datetime.strptime(saved["recorded_at"], "%Y-%m-%dT%H:%M:%S"))
    check("saved reading keeps temperature and humidity", saved["temperature"] == 20.0 and saved["humidity"] == 50.0)

    # several readings during the outage
    with patch.object(ns["requests"], "post", side_effect=real_requests.exceptions.Timeout("slow")):
        ns["send_reading"](21.0, 51.0)
        ns["send_reading"](22.0, 52.0)
    check("three readings waiting after a longer outage", ns["saved_queue"].count() == 3)

    # website error 500 also saves
    with patch.object(ns["requests"], "post", return_value=response(500)):
        ns["send_reading"](23.0, 53.0)
    check("website error (500): also saved", ns["saved_queue"].count() == 4)

    # connection returns: live reading goes, then the 4 saved ones follow
    with patch.object(ns["requests"], "post", return_value=response(201)) as post:
        ok = ns["send_reading"](24.0, 54.0)
    bodies = [c.kwargs["json"] for c in post.call_args_list]
    check("recovered: live reading sent first", ok and bodies[0]["temperature"] == 24.0 and "recorded_at" not in bodies[0])
    check("recovered: all four saved readings resent", post.call_count == 5 and all("recorded_at" in b for b in bodies[1:]))
    check("recovered: resent oldest first", [b["temperature"] for b in bodies[1:]] == [20.0, 21.0, 22.0, 23.0])
    check("recovered: queue empty", ns["saved_queue"].count() == 0)

    # website flaps again in the middle of catching up
    ns, qpath = fresh_sender()
    with patch.object(ns["requests"], "post", side_effect=real_requests.exceptions.ConnectionError("down")):
        for t in (20.0, 21.0, 22.0, 23.0):
            ns["send_reading"](t, 50.0)
    seq = iter([response(201), response(201), response(201), real_requests.exceptions.ConnectionError("down again")])
    def flaky(*a, **k):
        v = next(seq)
        if isinstance(v, Exception):
            raise v
        return v
    with patch.object(ns["requests"], "post", side_effect=flaky):
        ns["send_reading"](30.0, 50.0)
    check("drops out mid-catch-up: 2 resent, 2 still saved", ns["saved_queue"].count() == 2)

    # old website version that cannot take resent readings: keep them safe
    ns, qpath = fresh_sender()
    with patch.object(ns["requests"], "post", side_effect=real_requests.exceptions.ConnectionError("down")):
        ns["send_reading"](20.0, 50.0)
    with patch.object(ns["requests"], "post", return_value=response(201, supports=False)) as post:
        ns["send_reading"](25.0, 50.0)
    check("old website version: saved readings are NOT sent (would get wrong times)",
          post.call_count == 1 and ns["saved_queue"].count() == 1)

    # a reading the website will never accept must not block the rest
    ns, qpath = fresh_sender()
    with patch.object(ns["requests"], "post", side_effect=real_requests.exceptions.ConnectionError("down")):
        ns["send_reading"](20.0, 50.0)
        ns["send_reading"](21.0, 50.0)
    seq = iter([response(201), response(400), response(201)])
    with patch.object(ns["requests"], "post", side_effect=lambda *a, **k: next(seq)):
        ns["send_reading"](30.0, 50.0)
    check("a refused (400) saved reading is dropped, the next one still goes", ns["saved_queue"].count() == 0)

    # wrong password must not delete anything
    ns, qpath = fresh_sender()
    with patch.object(ns["requests"], "post", side_effect=real_requests.exceptions.ConnectionError("down")):
        ns["send_reading"](20.0, 50.0)
    seq = iter([response(201), response(401)])
    with patch.object(ns["requests"], "post", side_effect=lambda *a, **k: next(seq)):
        ns["send_reading"](30.0, 50.0)
    check("wrong key (401): saved readings are kept", ns["saved_queue"].count() == 1)

    # the queue itself broken: sending must still behave exactly as before
    ns, qpath = fresh_sender()
    ns["saved_queue"] = ReadingQueue("/no/such/folder/q.jsonl")
    with patch.object(ns["requests"], "post", side_effect=real_requests.exceptions.ConnectionError("down")) as post:
        check("cannot save: failure still reported normally", ns["send_reading"](20.0, 50.0) is False and post.call_count == 3)
    with patch.object(ns["requests"], "post", return_value=response(201)):
        check("cannot save: healthy sends unaffected", ns["send_reading"](20.0, 50.0) is True)

    # reading_queue.py was never copied to the Pi: old behaviour
    sys.modules["reading_queue"] = None
    ns, qpath = fresh_sender()
    sys.modules.pop("reading_queue")
    check("reading_queue.py missing: sender still starts, nothing saved", ns["saved_queue"] is None)
    with patch.object(ns["requests"], "post", side_effect=real_requests.exceptions.ConnectionError("down")) as post:
        check("reading_queue.py missing: failure handled as before", ns["send_reading"](20.0, 50.0) is False)

    # Pi clock not set yet: do not invent a time
    ns, qpath = fresh_sender()
    class FakeDT:
        @staticmethod
        def utcnow(): return datetime(1970, 1, 1, 0, 5)
    ns["datetime"] = FakeDT
    with patch.object(ns["requests"], "post", side_effect=real_requests.exceptions.ConnectionError("down")):
        ns["send_reading"](20.0, 50.0)
    check("Pi clock not set: reading saved without a made-up time", "recorded_at" not in ns["saved_queue"]._load()[0]["payload"])

print(f"\n{passed} passed, {failed} failed")
raise SystemExit(1 if failed else 0)
