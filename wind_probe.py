#!/usr/bin/env python3
"""
wind_probe.py - read the XS-WSDS01 (Veinasa) RS485 wind sensor.

READ-ONLY: this only asks the sensor for numbers. It never changes any sensor
setting and never talks to the TriTown website.

Settings from the sensor manual (page 6):
  Modbus RTU, 9600 baud, 8 data bits, no parity, 1 stop bit, default address 1
  Register 0x0000  wind speed, m/s      (value / 10)
  Register 0x0001  wind level (Beaufort-style number)
  Register 0x0002  wind speed, km/h     (value / 100)
  Register 0x0003  wind direction, deg  (value / 10)
  Register 0x0004  compass bearing code (0x00 = N ... 8 or 16 points)

Run on a Windows PC or the Raspberry Pi with the USB-to-RS485 adapter plugged in:
    pip install pyserial         (once; pip3 on a Pi)
    python wind_probe.py         (python3 on a Pi)
"""
import glob
import sys
import time

try:
    import serial
except ImportError:
    print("pyserial is missing. Install it with:  pip3 install pyserial")
    sys.exit(1)

BAUDS = [9600, 4800, 2400, 19200]   # manual says 9600; the others are fallbacks
ADDRESSES = [1, 2, 3]
FUNCTION = 3                         # read holding registers
START, COUNT = 0, 5                  # registers 0x0000 .. 0x0004
MS_TO_MPH = 2.236936

BEARINGS_16 = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
               "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]


def crc16(data):
    crc = 0xFFFF
    for b in data:
        crc ^= b
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
    return crc


def ask(ser, addr, start=START, count=COUNT):
    frame = bytes([addr, FUNCTION, start >> 8, start & 255, count >> 8, count & 255])
    c = crc16(frame)
    frame += bytes([c & 255, c >> 8])
    ser.reset_input_buffer()
    ser.write(frame)
    ser.flush()
    time.sleep(0.35)
    resp = ser.read(5 + 2 * count)
    if len(resp) < 5:
        return None
    if crc16(resp[:-2]) != (resp[-2] | (resp[-1] << 8)):
        return None
    if resp[0] != addr or resp[1] != FUNCTION:
        return None
    n = resp[2]
    return [(resp[3 + 2 * i] << 8) | resp[4 + 2 * i] for i in range(n // 2)]


def decode(regs):
    """Turn the 5 raw registers into readable numbers."""
    ms = regs[0] / 10.0
    kmh = regs[2] / 100.0
    deg = regs[3] / 10.0
    code = regs[4]
    bearing = BEARINGS_16[code] if code < 16 else "?"
    return {"mph": round(ms * MS_TO_MPH, 1), "m_s": ms, "km_h": kmh,
            "level": regs[1], "degrees": deg, "bearing": bearing}


def find_sensor(port):
    for baud in BAUDS:
        try:
            ser = serial.Serial(port, baud, bytesize=8, parity="N",
                                stopbits=1, timeout=0.5)
        except Exception as e:
            print("  cannot open %s: %s" % (port, e))
            return None
        for addr in ADDRESSES:
            regs = ask(ser, addr)
            if regs is not None and len(regs) == COUNT:
                return ser, baud, addr, regs
        ser.close()
    return None


def main():
    ports = sorted(glob.glob("/dev/ttyUSB*") + glob.glob("/dev/ttyACM*"))
    try:  # Windows (COM3, COM4, ...) and anything else pyserial can see
        from serial.tools import list_ports
        for p in list_ports.comports():
            if p.device not in ports:
                ports.append(p.device)
    except Exception:
        pass
    if not ports:
        print("No USB serial adapter found. Check that the USB-to-RS485 adapter")
        print("is plugged in (on a Pi, run:  ls /dev/ttyUSB*).")
        sys.exit(2)
    print("Adapters found: %s" % ", ".join(ports))
    found = None
    for port in ports:
        print("Trying %s ..." % port)
        found = find_sensor(port)
        if found:
            break
    if not found:
        print("\nNo answer from the sensor. With the power OFF while you work, check:")
        print(" - 12V supply: red wire to +, black wire to -")
        print(" - yellow wire to the adapter's A, green wire to the adapter's B")
        print(" - then try swapping the yellow and green wires and run again")
        sys.exit(3)

    ser, baud, addr, regs = found
    print("\nSENSOR ANSWERED: port=%s baud=%d address=%d" % (ser.port, baud, addr))
    print("Raw registers: %s" % regs)
    print("\nNow spin the cups and turn the vane. Reading for ~30 seconds.\n")
    for _ in range(15):
        regs = ask(ser, addr)
        if regs and len(regs) == COUNT:
            d = decode(regs)
            print("%s  wind %5.1f mph (%.1f m/s)  direction %5.1f deg %s  level %d  raw=%s"
                  % (time.strftime("%H:%M:%S"), d["mph"], d["m_s"],
                     d["degrees"], d["bearing"], d["level"], regs))
        else:
            print(time.strftime("%H:%M:%S"), "no answer")
        time.sleep(2)
    ser.close()


if __name__ == "__main__":
    main()
