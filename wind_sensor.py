"""
wind_sensor.py - read the XS-WSDS01 (Veinasa) RS485 wind sensor.
Runs on the Raspberry Pi, next to pi_sender.py.

Sensor settings (from the manual, page 6): Modbus RTU, 9600 baud, 8 data bits,
no parity, 1 stop bit, default address 1.
  register 0 : wind speed, m/s      (value / 10)
  register 3 : wind direction, deg  (value / 10)
This module only READS. It never writes a setting to the sensor.

Design rule: a missing, unplugged or misbehaving wind sensor must NEVER stop
the Pi from sending temperature and humidity. Every public method here returns
None on trouble instead of raising.
"""
import logging
import math
import time

MS_TO_MPH = 2.236936
REG_START, REG_COUNT = 0, 5
FUNCTION_READ_HOLDING = 3
MAX_PLAUSIBLE_MS = 60.0       # sensor range is 0-30 m/s; above 60 is garbage
MIN_GOOD_SAMPLES = 3          # need at least this many valid samples to trust an average


def crc16(data):
    """Modbus CRC-16."""
    crc = 0xFFFF
    for b in data:
        crc ^= b
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
    return crc


def build_request(addr, start=REG_START, count=REG_COUNT):
    frame = bytes([addr, FUNCTION_READ_HOLDING, start >> 8, start & 255,
                   count >> 8, count & 255])
    c = crc16(frame)
    return frame + bytes([c & 255, c >> 8])


def parse_response(resp, addr, count=REG_COUNT):
    """Return the list of register values, or None if the reply is not valid."""
    if resp is None or len(resp) < 5:
        return None
    if crc16(resp[:-2]) != (resp[-2] | (resp[-1] << 8)):
        return None
    if resp[0] != addr or resp[1] != FUNCTION_READ_HOLDING:
        return None            # includes Modbus error replies (function | 0x80)
    n = resp[2]
    if n != 2 * count or len(resp) != 5 + n:
        return None
    return [(resp[3 + 2 * i] << 8) | resp[4 + 2 * i] for i in range(n // 2)]


def decode(regs):
    """Turn raw registers into {'speed_mph', 'direction_deg'}, or None if implausible."""
    if regs is None or len(regs) < 4:
        return None
    speed_ms = regs[0] / 10.0
    direction = regs[3] / 10.0
    if speed_ms > MAX_PLAUSIBLE_MS or direction > 360.0:
        return None
    return {"speed_mph": speed_ms * MS_TO_MPH, "direction_deg": direction}


def average_samples(samples):
    """
    Combine several {'speed_mph', 'direction_deg'} samples into one reading:
    average speed, highest gust, and the average direction.

    Direction is averaged as a compass direction (so 350 and 10 degrees average
    to about 0, not 180), weighted by wind speed. If the air is dead calm the
    direction is meaningless, so the most recent direction is reported.
    """
    if not samples:
        return None
    speeds = [s["speed_mph"] for s in samples]
    x = sum(s["speed_mph"] * math.cos(math.radians(s["direction_deg"])) for s in samples)
    y = sum(s["speed_mph"] * math.sin(math.radians(s["direction_deg"])) for s in samples)
    if math.hypot(x, y) < 1e-9:
        direction = samples[-1]["direction_deg"]
    else:
        direction = math.degrees(math.atan2(y, x)) % 360.0
    return {
        "speed_mph": sum(speeds) / len(speeds),
        "gust_mph": max(speeds),
        "direction_deg": direction,
        "samples": len(samples),
    }


class WindSensor:
    def __init__(self, port="/dev/ttyUSB0", baud=9600, address=1,
                 serial_module=None, sleep=time.sleep):
        self.port = port
        self.baud = baud
        self.address = address
        self._serial_module = serial_module
        self._sleep = sleep
        self._ser = None
        self._warned_missing = False

    def _open(self):
        if self._ser is not None:
            return self._ser
        try:
            ser_mod = self._serial_module
            if ser_mod is None:
                import serial as ser_mod
            self._ser = ser_mod.Serial(self.port, self.baud, bytesize=8,
                                       parity="N", stopbits=1, timeout=0.5,
                                       write_timeout=1)
        except Exception as e:
            if not self._warned_missing:
                logging.warning("[WIND] cannot open %s: %s (wind disabled until it works)"
                                % (self.port, e))
                self._warned_missing = True
            self._ser = None
        return self._ser

    def _close(self):
        try:
            if self._ser is not None:
                self._ser.close()
        except Exception:
            pass
        self._ser = None

    def read_once(self):
        """One instant reading, or None. Never raises."""
        try:
            ser = self._open()
            if ser is None:
                return None
            ser.reset_input_buffer()
            ser.write(build_request(self.address))
            ser.flush()
            self._sleep(0.35)
            resp = ser.read(5 + 2 * REG_COUNT)
            return decode(parse_response(resp, self.address))
        except Exception as e:
            logging.warning("[WIND] read failed: %s" % e)
            self._close()      # reopen on the next try (e.g. adapter replugged)
            return None

    def read_average(self, seconds=30, interval=2.0):
        """
        Sample for `seconds`, return {'speed_mph', 'gust_mph', 'direction_deg',
        'samples'} or None if too few good samples. Never raises.
        A single instant reading is too gusty to describe the wind, so the Pi
        reports an average over a short window instead.
        """
        samples = []
        attempts = max(1, int(seconds / interval))
        for i in range(attempts):
            s = self.read_once()
            if s is not None:
                samples.append(s)
            if i < attempts - 1:
                self._sleep(interval)
        if len(samples) < MIN_GOOD_SAMPLES:
            logging.warning("[WIND] only %d good samples out of %d, skipping wind this round"
                            % (len(samples), attempts))
            return None
        return average_samples(samples)
