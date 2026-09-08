import Adafruit_DHT
import requests
import time
import sys
import math

LOG_FILE = '/home/pi/sender.log'
log = open(LOG_FILE, 'a', buffering=1)
sys.stdout = log
sys.stderr = log

DEVICE_ID  = 'pi-library'
LOCATION   = 'Middleton Fire Station'
SERVER_URL = 'https://tritown-monitor.onrender.com/api/reading'
API_KEY    = 'tritown2024'
INTERVAL   = 300
DHT_SENSOR = Adafruit_DHT.DHT22
DHT_PIN    = 17

def dew_point(temp_c, humidity):
    a, b = 17.27, 237.7
    alpha = ((a * temp_c) / (b + temp_c)) + math.log(humidity / 100.0)
    return round((b * alpha) / (a - alpha), 1)

print("TriTown Pi Sender starting...")
print("Location : %s" % LOCATION)
print("Server   : %s" % SERVER_URL)
print("Interval : %d seconds" % INTERVAL)

while True:
    try:
        humidity, temp_c = Adafruit_DHT.read_retry(DHT_SENSOR, DHT_PIN)
        if temp_c and humidity:
            temp_f = temp_c * 9/5 + 32
            dp     = dew_point(temp_c, humidity)
            dp_f   = round(dp * 9/5 + 32, 1)
            payload = {
                'device_id'  : DEVICE_ID,
                'location'   : LOCATION,
                'temperature': round(temp_c, 1),
                'humidity'   : round(humidity, 1),
                'dew_point'  : dp,
            }
            response = requests.post(SERVER_URL, json=payload, headers={'X-API-Key': API_KEY}, timeout=10)
            if response.status_code == 201:
                data = response.json()
                print("[OK] Sent: Temp=%.1f F  Humidity=%.1f%%  DewPoint=%.1f F  Alert=%s" % (
                    temp_f, humidity, dp_f, data.get('alert_level','?')))
            else:
                print("[ERROR] Server returned: %d" % response.status_code)
        else:
            print("[ERROR] DHT22 read failed")
    except Exception as e:
        print("[ERROR] %s" % str(e))
    time.sleep(INTERVAL)
