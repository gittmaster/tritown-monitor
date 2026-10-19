"""
Offline test for wind_sensor.py. Uses a FAKE sensor, so it needs no hardware,
no network and no pyserial.   Usage: python test_wind_sensor.py
"""
import wind_sensor as ws

passed = failed = 0


def check(label, condition):
    global passed, failed
    if condition:
        passed += 1
        print(f"[PASS] {label}")
    else:
        failed += 1
        print(f"[FAIL] {label}")


def reply(regs, addr=1, func=3):
    body = bytes([addr, func, 2 * len(regs)])
    for r in regs:
        body += bytes([r >> 8, r & 255])
    c = ws.crc16(body)
    return body + bytes([c & 255, c >> 8])


# --- request frame ---------------------------------------------------------
check("request frame matches the known Modbus frame for 5 registers at address 1",
      ws.build_request(1) == bytes.fromhex("0103000000058 5C9".replace(" ", "")))

# --- parsing ---------------------------------------------------------------
good = reply([37, 3, 1346, 77, 0])
check("valid reply is parsed", ws.parse_response(good, 1) == [37, 3, 1346, 77, 0])
bad_crc = bytearray(good); bad_crc[-1] ^= 0xFF
check("bad CRC is rejected", ws.parse_response(bytes(bad_crc), 1) is None)
check("wrong address is rejected", ws.parse_response(reply([1, 2, 3, 4, 5], addr=2), 1) is None)
check("wrong function is rejected", ws.parse_response(reply([1, 2, 3, 4, 5], func=4), 1) is None)
err = bytes([1, 0x83, 2]); c = ws.crc16(err); err += bytes([c & 255, c >> 8])
check("Modbus error reply is rejected", ws.parse_response(err, 1) is None)
check("short / empty reply is rejected",
      ws.parse_response(b"", 1) is None and ws.parse_response(good[:6], 1) is None)

# --- decoding: numbers from the real sensor test on 2026-10-18 ---------------
d = ws.decode([37, 3, 1346, 77, 0])
check("37 -> 3.7 m/s -> 8.3 mph", round(d["speed_mph"], 1) == 8.3)
check("77 -> 7.7 degrees", d["direction_deg"] == 7.7)
d = ws.decode([45, 3, 1626, 128, 1])
check("45 -> 4.5 m/s -> 10.1 mph", round(d["speed_mph"], 1) == 10.1)
d = ws.decode([0, 0, 0, 3399, 15])
check("calm: 0 mph, direction 339.9", d["speed_mph"] == 0 and d["direction_deg"] == 339.9)
check("implausible speed (garbage) is rejected", ws.decode([9999, 0, 0, 100, 0]) is None)
check("implausible direction (garbage) is rejected", ws.decode([10, 0, 0, 4000, 0]) is None)
check("too few registers is rejected", ws.decode([1, 2]) is None and ws.decode(None) is None)

# --- averaging -------------------------------------------------------------
S = lambda mph, deg: {"speed_mph": mph, "direction_deg": deg}
a = ws.average_samples([S(4, 90), S(8, 90), S(12, 90)])
check("average speed", a["speed_mph"] == 8)
check("gust is the highest sample", a["gust_mph"] == 12)
a = ws.average_samples([S(5, 350), S(5, 10)])
check("350 and 10 degrees average to north (not south)",
      min(a["direction_deg"], 360 - a["direction_deg"]) < 1)
a = ws.average_samples([S(0, 100), S(0, 200)])
check("dead calm reports the latest direction", a["direction_deg"] == 200)
check("no samples -> None", ws.average_samples([]) is None)

# --- WindSensor with a fake serial port --------------------------------------
class FakeSerial:
    def __init__(self, replies):
        self.replies = list(replies)
        self.closed = False
    def reset_input_buffer(self): pass
    def write(self, data): self.last_request = data
    def flush(self): pass
    def read(self, n):
        r = self.replies.pop(0) if self.replies else b""
        if isinstance(r, Exception):
            raise r
        return r
    def close(self): self.closed = True


class FakeModule:
    """Stands in for the pyserial module."""
    def __init__(self, serials=None, fail_open=False):
        self.serials = list(serials or [])
        self.fail_open = fail_open
        self.opened = 0
    def Serial(self, *a, **k):
        if self.fail_open:
            raise OSError("no such port")
        self.opened += 1
        return self.serials.pop(0)


nosleep = lambda s: None

fs = FakeSerial([reply([37, 3, 1346, 77, 0])])
sensor = ws.WindSensor(serial_module=FakeModule([fs]), sleep=nosleep)
r = sensor.read_once()
check("read_once returns a decoded reading", r is not None and round(r["speed_mph"], 1) == 8.3)
check("request sent to the sensor is correct", fs.last_request == ws.build_request(1))

sensor = ws.WindSensor(serial_module=FakeModule(fail_open=True), sleep=nosleep)
check("missing adapter -> None, no crash", sensor.read_once() is None)
check("missing adapter -> average is None too", sensor.read_average(seconds=10, interval=2) is None)

check("pyserial not installed -> None, no crash",
      ws.WindSensor(serial_module=type("M", (), {"Serial": staticmethod(lambda *a, **k: (_ for _ in ()).throw(ImportError("no pyserial")))}),
                    sleep=nosleep).read_once() is None)

# adapter unplugged mid-run, then plugged back in
fs1 = FakeSerial([OSError("device disappeared")])
fs2 = FakeSerial([reply([20, 2, 700, 900, 4])])
mod = FakeModule([fs1, fs2])
sensor = ws.WindSensor(serial_module=mod, sleep=nosleep)
check("read error -> None, no crash", sensor.read_once() is None)
check("failed port was closed", fs1.closed)
r = sensor.read_once()
check("sensor recovers on the next try (port reopened)", r is not None and r["direction_deg"] == 90.0 and mod.opened == 2)

# average over a window
reps = [reply([30, 3, 1000, 900, 4])] * 5
sensor = ws.WindSensor(serial_module=FakeModule([FakeSerial(reps)]), sleep=nosleep)
a = sensor.read_average(seconds=10, interval=2)
check("read_average collects the samples", a is not None and a["samples"] == 5)
check("read_average speed = 3.0 m/s = 6.7 mph", round(a["speed_mph"], 1) == 6.7)

reps = [reply([30, 3, 1000, 900, 4]), b"", b"", b"", reply([30, 3, 1000, 900, 4])]
sensor = ws.WindSensor(serial_module=FakeModule([FakeSerial(reps)]), sleep=nosleep)
check("too few good samples -> None (not a misleading average)",
      sensor.read_average(seconds=10, interval=2) is None)

print(f"\n{passed} passed, {failed} failed")
raise SystemExit(1 if failed else 0)
