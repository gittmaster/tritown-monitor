import Adafruit_DHT
import smbus2
import requests
import time

# ── Config — change these! ────────────────────────────────────────
DEVICE_ID   = 'pi-library'
LOCATION    = 'TriTown Library'
SERVER_URL  = 'https://tritown-monitor.onrender.com/api/reading'
API_KEY     = 'tritown2024'
INTERVAL    = 300  # seconds between readings (5 minutes)

# ── Sensor setup ──────────────────────────────────────────────────
DHT_SENSOR  = Adafruit_DHT.DHT22
DHT_PIN     = 17
BME_ADDRESS = 0x76
bus         = smbus2.SMBus(1)

def get_calib():
    calib = bus.read_i2c_block_data(BME_ADDRESS, 0x88, 24)
    h     = bus.read_i2c_block_data(BME_ADDRESS, 0xA1, 1)
    h2    = bus.read_i2c_block_data(BME_ADDRESS, 0xE1, 7)
    T     = [0]*3
    T[0]  = calib[1] << 8 | calib[0]
    T[1]  = calib[3] << 8 | calib[2]
    T[2]  = calib[5] << 8 | calib[4]
    if T[1] > 32767: T[1] -= 65536
    if T[2] > 32767: T[2] -= 65536
    H     = [0]*6
    H[0]  = h[0]
    H[1]  = h2[1] << 8 | h2[0]
    H[2]  = h2[2]
    H[3]  = h2[3] << 4 | (h2[4] & 0x0F)
    H[4]  = (h2[4] >> 4) | h2[5] << 4
    H[5]  = h2[6]
    if H[1] > 32767: H[1] -= 65536
    if H[3] > 32767: H[3] -= 65536
    if H[4] > 32767: H[4] -= 65536
    if H[5] > 127:   H[5] -= 256
    return T, H

def read_bme(T, H):
    bus.write_byte_data(BME_ADDRESS, 0xF2, 0x01)
    bus.write_byte_data(BME_ADDRESS, 0xF4, 0x27)
    bus.write_byte_data(BME_ADDRESS, 0xF5, 0xA0)
    time.sleep(0.5)
    data     = bus.read_i2c_block_data(BME_ADDRESS, 0xF7, 8)
    temp_raw = (data[3] << 12) | (data[4] << 4) | (data[5] >> 4)
    hum_raw  = (data[6] << 8)  |  data[7]
    var1     = (temp_raw / 16384.0 - T[0] / 1024.0) * T[1]
    var2     = (temp_raw / 131072.0 - T[0] / 8192.0) ** 2 * T[2]
    t_fine   = var1 + var2
    temp     = t_fine / 5120.0
    x        = t_fine - 76800.0
    if x == 0:
        hum = 0
    else:
        x   = (hum_raw - (H[3] * 64.0 + (H[4] / 16384.0) * x)) * (H[1] / 65536.0 * (1.0 + H[5] / 67108864.0 * x * (1.0 + H[2] / 67108864.0 * x)))
        hum = max(0.0, min(x * (1.0 - H[0] * x / 524288.0), 100.0))
    return temp, hum

print("TriTown Pi Sender starting...")
print("Location : %s" % LOCATION)
print("Server   : %s" % SERVER_URL)
print("Interval : %d seconds\n" % INTERVAL)

T, H = get_calib()

while True:
    try:
        dht_hum, dht_temp = Adafruit_DHT.read_retry(DHT_SENSOR, DHT_PIN)
        bme_temp, bme_hum = read_bme(T, H)

        if dht_temp and dht_hum:
            avg_temp = (dht_temp + bme_temp) / 2
            avg_hum  = (dht_hum  + bme_hum)  / 2
        else:
            avg_temp = bme_temp
            avg_hum  = bme_hum

        payload = {
            'device_id'  : DEVICE_ID,
            'location'   : LOCATION,
            'temperature': round(avg_temp, 1),
            'humidity'   : round(avg_hum, 1),
        }

        response = requests.post(
            SERVER_URL,
            json=payload,
            headers={'X-API-Key': API_KEY},
            timeout=10
        )

        if response.status_code == 201:
            data = response.json()
            print("[OK] Sent: Temp=%.1f C  Humidity=%.1f%%  Alert=%s" % (
                avg_temp, avg_hum, data.get('alert_level','?')))
        else:
            print("[ERROR] Server returned: %d" % response.status_code)

    except Exception as e:
        print("[ERROR] %s" % str(e))

    time.sleep(INTERVAL)
