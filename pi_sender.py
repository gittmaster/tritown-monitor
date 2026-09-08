import Adafruit_DHT
import requests
import time
import sys
import math
import logging

LOG_FILE = '/home/pi/sender.log'
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format='%(asctime)s %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

DEVICE_ID  = 'pi-library'
LOCATION   = 'Middleton Fire Station'
SERVER_URL = 'https://tritown-monitor.onrender.com/api/reading'
API_KEY    = 'tritown2024'
INTERVAL   = 300
DHT_SENSOR = Adafruit_DHT.DHT22
DHT_PIN    = 17
MAX_RETRIES = 3

def dew_point(temp_c, humidity):
    a, b = 17.27, 237.7
    alpha = ((a * temp_c) / (b + temp_c)) + math.log(humidity / 100.0)
    return round((b * alpha) / (a - alpha), 1)

def send_reading(temp_c, humidity):
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
    for attempt in range(MAX_RETRIES):
        try:
            response = requests.post(
                SERVER_URL,
                json=payload,
                headers={'X-API-Key': API_KEY},
                timeout=15
            )
            if response.status_code == 201:
                data = response.json()
                logging.info("[OK] Sent: Temp=%.1f F  Humidity=%.1f%%  DewPoint=%.1f F  Alert=%s" % (
                    temp_f, humidity, dp_f, data.get('alert_level','?')))
                return True
            else:
                logging.warning("[WARN] Server returned: %d (attempt %d)" % (response.status_code, attempt+1))
        except requests.exceptions.ConnectionError:
            logging.warning("[WARN] Connection error (attempt %d)" % (attempt+1))
        except requests.exceptions.Timeout:
            logging.warning("[WARN] Timeout (attempt %d)" % (attempt+1))
        except Exception as e:
            logging.error("[ERROR] %s (attempt %d)" % (str(e), attempt+1))
        time.sleep(10)
    logging.error("[ERROR] Failed to send after %d attempts" % MAX_RETRIES)
    return False

logging.info("TriTown Pi Sender starting...")
logging.info("Location : %s" % LOCATION)
logging.info("Server   : %s" % SERVER_URL)
logging.info("Interval : %d seconds" % INTERVAL)

consecutive_failures = 0

while True:
    try:
        humidity, temp_c = Adafruit_DHT.read_retry(DHT_SENSOR, DHT_PIN, retries=5)
        if temp_c is not None and humidity is not None:
            success = send_reading(temp_c, humidity)
            if success:
                consecutive_failures = 0
            else:
                consecutive_failures += 1
        else:
            logging.error("[ERROR] DHT22 read failed")
            consecutive_failures += 1

        if consecutive_failures >= 10:
            logging.error("[CRITICAL] 10 consecutive failures — restarting sender")
            sys.exit(1)

    except Exception as e:
        logging.error("[ERROR] Unexpected: %s" % str(e))
        consecutive_failures += 1

    time.sleep(INTERVAL)
