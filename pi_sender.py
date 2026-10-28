import Adafruit_DHT
import requests
import time
import sys
import math
import shutil
import logging
from datetime import datetime

try:
    from wind_sensor import WindSensor
except Exception:            # wind_sensor.py not copied to the Pi: wind stays off
    WindSensor = None

try:
    from reading_queue import ReadingQueue
except Exception:            # reading_queue.py not copied to the Pi: old behaviour
    ReadingQueue = None

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
def load_api_key():
    """The password lives on the Pi only: in /home/pi/.tritown_api_key (or the TRITOWN_API_KEY setting).
    It is never stored in the code or on GitHub."""
    import os
    key = os.environ.get('TRITOWN_API_KEY', '').strip()
    if not key:
        try:
            with open('/home/pi/.tritown_api_key') as f:
                key = f.read().strip()
        except Exception:
            key = ''
    if not key:
        logging.error("No API key found. Put it in /home/pi/.tritown_api_key")
    return key

API_KEY    = load_api_key()
INTERVAL   = 300
DHT_SENSOR = Adafruit_DHT.DHT22
DHT_PIN    = 17
MAX_RETRIES = 3

# Wind sensor (XS-WSDS01 on a USB-to-RS485 adapter). If it is unplugged or
# broken, temperature and humidity are still sent exactly as before.
WIND_ENABLED = True
WIND_PORT = '/dev/ttyUSB0'
WIND_WINDOW_SECONDS = 30      # average the wind over this long before each send
try:
    wind_sensor = WindSensor(WIND_PORT) if (WIND_ENABLED and WindSensor) else None
except Exception:             # even a broken wind reader must not stop the sender
    wind_sensor = None

# Readings the website could not take (internet or website down) are saved in
# this file and sent again, with their original time, once it is back.
QUEUE_FILE = '/home/pi/unsent_readings.jsonl'
QUEUE_DAYS = 60               # keep unsent readings this long, then drop the oldest
try:
    saved_queue = ReadingQueue(QUEUE_FILE, max_days=QUEUE_DAYS, log=logging.warning) if ReadingQueue else None
except Exception:
    saved_queue = None
server_can_resend = False     # becomes True once the website says it understands resent readings
CLOCK_TRUSTED_AFTER = 2025    # a Pi clock earlier than this has not been set yet

def dew_point(temp_c, humidity):
    a, b = 17.27, 237.7
    alpha = ((a * temp_c) / (b + temp_c)) + math.log(humidity / 100.0)
    return round((b * alpha) / (a - alpha), 1)

def save_for_later(payload):
    """Keep a reading we could not deliver. Never lets a problem here escape."""
    if not saved_queue:
        return
    try:
        item = dict(payload)
        now = datetime.utcnow()
        if now.year >= CLOCK_TRUSTED_AFTER:      # otherwise the website stamps it on arrival
            item['recorded_at'] = now.strftime('%Y-%m-%dT%H:%M:%S')
        if saved_queue.add(item):
            logging.warning("[QUEUE] saved the reading for later (%d waiting)" % saved_queue.count())
    except Exception as e:
        logging.error("[QUEUE] could not save reading: %s" % str(e))

def post_saved(payload):
    """One attempt to deliver a saved reading. True means: done with it."""
    try:
        response = requests.post(SERVER_URL, json=payload, headers={'X-API-Key': API_KEY}, timeout=15)
    except Exception:
        return False
    if response.status_code == 201:
        return True
    if 400 <= response.status_code < 500 and response.status_code not in (401, 403, 408, 429):
        logging.error("[QUEUE] website refused a saved reading (%d); dropping it" % response.status_code)
        return True       # it will never be accepted, so do not let it block the others
    return False

def resend_saved():
    """After a successful send, deliver anything saved during an outage."""
    if not saved_queue:
        return
    try:
        waiting = saved_queue.count()
        if not waiting:
            return
        if not server_can_resend:
            logging.warning("[QUEUE] %d readings waiting; the website is not updated to take them yet" % waiting)
            return
        sent, left = saved_queue.flush(post_saved)
        logging.info("[QUEUE] resent %d saved readings, %d still waiting" % (sent, left))
    except Exception as e:
        logging.error("[QUEUE] resend problem: %s" % str(e))

# Telling the website what is wrong with the Pi itself (so the dashboard and
# your phone alert can say WHICH part failed, not just "no data").
STATUS_URL = SERVER_URL.replace('/api/reading', '/api/status')
TEMP_PROBLEM_AFTER = 2        # failed temperature reads in a row before we report it (about 10 min)
WIND_PROBLEM_AFTER = 3        # silent wind readings in a row before we report it (about 15 min)
dht_fail_streak = 0
wind_miss_streak = 0
last_reported_parts = ()

def current_problems():
    problems = []
    if dht_fail_streak >= TEMP_PROBLEM_AFTER:
        problems.append({'part': 'temperature_sensor',
                         'detail': 'The temperature sensor has not answered for %d readings in a row. '
                                   'Check its three wires and plug.' % dht_fail_streak})
    if wind_sensor and wind_miss_streak >= WIND_PROBLEM_AFTER:
        problems.append({'part': 'wind_sensor',
                         'detail': 'The wind sensor has not answered for %d readings in a row. '
                                   'Check the USB adapter and cable.' % wind_miss_streak})
    return problems

def free_disk_mb():
    try:
        return round(shutil.disk_usage('/').free / 1048576, 1)
    except Exception:
        return None

def report_status():
    """While anything is wrong, tell the website every cycle; tell it once when
    everything is fine again. One quick try, never blocks, never raises."""
    global last_reported_parts
    problems = current_problems()
    parts = tuple(sorted(p['part'] for p in problems))
    if not problems and not last_reported_parts:
        return                      # healthy and nothing to clear
    payload = {'device_id': DEVICE_ID, 'location': LOCATION, 'problems': problems,
               'disk_free_mb': free_disk_mb(),
               'queue_waiting': saved_queue.count() if saved_queue else 0}
    try:
        response = requests.post(STATUS_URL, json=payload, headers={'X-API-Key': API_KEY}, timeout=10)
        if response.status_code == 201:
            last_reported_parts = parts
            if problems:
                logging.warning("[STATUS] reported: %s" % ", ".join(parts))
            else:
                logging.info("[STATUS] reported all sensors OK again")
    except Exception as e:
        logging.info("[STATUS] could not report (will retry): %s" % str(e))

def send_reading(temp_c, humidity, wind=None):
    global server_can_resend
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
    if wind:
        payload['wind_speed']     = round(wind['speed_mph'], 1)
        payload['wind_direction'] = round(wind['direction_deg'], 1)
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
                server_can_resend = bool(data.get('supports_recorded_at'))
                wind_txt = ("  Wind=%.1f mph @ %.0f deg" % (wind['speed_mph'], wind['direction_deg'])) if wind else "  Wind=none"
                logging.info("[OK] Sent: Temp=%.1f F  Humidity=%.1f%%  DewPoint=%.1f F  Alert=%s%s" % (
                    temp_f, humidity, dp_f, data.get('alert_level','?'), wind_txt))
                resend_saved()
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
    save_for_later(payload)
    return False

logging.info("TriTown Pi Sender starting...")
logging.info("Location : %s" % LOCATION)
logging.info("Server   : %s" % SERVER_URL)
logging.info("Interval : %d seconds" % INTERVAL)

consecutive_failures = 0

if not API_KEY:
    print("No API key found. Put it in /home/pi/.tritown_api_key")
    sys.exit(1)

while True:
    try:
        humidity, temp_c = Adafruit_DHT.read_retry(DHT_SENSOR, DHT_PIN, retries=5)
        if temp_c is not None and humidity is not None:
            wind = None
            if wind_sensor:
                try:
                    wind = wind_sensor.read_average(WIND_WINDOW_SECONDS)
                except Exception as e:   # belt and braces: never let wind stop the send
                    logging.warning("[WIND] skipped: %s" % str(e))
            dht_fail_streak = 0
            if wind_sensor:
                wind_miss_streak = 0 if wind else wind_miss_streak + 1
            success = send_reading(temp_c, humidity, wind)
            if success:
                consecutive_failures = 0
            else:
                consecutive_failures += 1
        else:
            logging.error("[ERROR] DHT22 read failed")
            dht_fail_streak += 1
            consecutive_failures += 1

        if consecutive_failures >= 10:
            logging.error("[CRITICAL] 10 consecutive failures — restarting sender")
            sys.exit(1)

    except Exception as e:
        logging.error("[ERROR] Unexpected: %s" % str(e))
        consecutive_failures += 1

    try:
        report_status()
    except Exception as e:
        logging.warning("[STATUS] problem: %s" % str(e))

    time.sleep(INTERVAL)
