import json
import os
import time
import requests
from datetime import datetime

API        = 'https://tritown-monitor.onrender.com/api/stats'
NTFY_TOPIC = 'tritown-mfs-monitor-2024'
STATE_FILE = os.environ.get('HEARTBEAT_STATE', '/home/pi/heartbeat_state.json')
REPEAT_MINUTES = 60      # while a problem lasts, remind at most once an hour
STATION = 'Middleton Fire Station'


def stamp():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def send_alert(message, title='TriTown Monitor ALERT'):
    """Send a phone notification. Returns True only if it really went out."""
    try:
        requests.post(
            'https://ntfy.sh/' + NTFY_TOPIC,
            data=message.encode('utf-8'),
            headers={'Title': title},
            timeout=10
        )
        print("%s %s sent: %s" % (stamp(), title, message))
        return True
    except Exception as e:
        print("%s Alert failed: %s" % (stamp(), str(e)))
        return False


def load_state():
    try:
        with open(STATE_FILE) as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_state(state):
    try:
        with open(STATE_FILE, 'w') as f:
            json.dump(state, f)
    except Exception as e:      # cannot remember: fall back to alerting every run
        print("%s Could not save state: %s" % (stamp(), str(e)))


def minutes_since(text):
    when = datetime.strptime(text.split('.')[0], '%Y-%m-%d %H:%M:%S')
    return (datetime.utcnow() - when).total_seconds() / 60


def pi_reports_problem(data, part):
    """True if the Pi itself said, within the last 15 minutes, that this part is broken.
    That also proves the Pi has power and internet."""
    try:
        for item in data.get('device_problems') or []:
            if item.get('part') == part and minutes_since(item['updated_at']) <= 15:
                return True
    except Exception:
        pass
    return False


def find_problem():
    """Return (kind, message) for the current problem, or (None, ok_text)."""
    try:
        r    = requests.get(API, timeout=10)
        data = r.json()
    except Exception as e:
        return ('unreachable',
                'PROBLEM: The website did not answer (%s). The monitor may be '
                'fine but nobody can see it. It is often just waking up, so wait '
                '15 minutes. If this message repeats, check the website host '
                '(Render) for an outage. Usually fixed within 30 minutes.' % str(e))
    last = data.get('last_updated')
    if not last:
        return ('empty',
                'PROBLEM: No data in database! Dashboard may be down. The website '
                'has no readings at all. Check that the Pi is on and the website '
                'database is working. Usually fixed in under an hour.')
    diff = minutes_since(last)
    if diff > 15:
        if pi_reports_problem(data, 'temperature_sensor'):
            return ('silent',
                    'PROBLEM: No sensor data for %.0f minutes! The Pi is on and online, '
                    'but its temperature sensor is not answering, so the dashboard is '
                    'showing old numbers. First check: the three wires and the plug on '
                    'the temperature sensor at %s. A loose wire is the usual cause, '
                    'about a 10 minute fix.' % (diff, STATION))
        return ('silent',
                'PROBLEM: No sensor data for %.0f minutes! %s has stopped sending '
                'readings, so the dashboard is showing old numbers. Most likely '
                'the Pi lost power or WiFi, or the temperature sensor came loose. '
                'First check: is the Pi powered with its lights on, and is the '
                'WiFi up? Restarting the power often fixes it in 5 to 10 minutes.'
                % (diff, STATION))
    ok = "Last reading %.0f min ago" % diff
    # Wind: only if wind has reported before (a station with no wind sensor is
    # never nagged), and only while temperature/humidity still arrive (so one
    # outage does not send two alerts).
    wind_last = data.get('wind_last_seen')
    if wind_last:
        wind_diff = minutes_since(wind_last)
        if wind_diff > 30:
            return ('wind',
                    'PROBLEM: Wind sensor has stopped reporting for %.0f minutes. '
                    'Temperature and humidity are still OK. The dashboard shows a '
                    'warning, and fire danger cannot use wind until it is fixed. '
                    'First check: the wind sensor cable and its USB adapter at %s. '
                    'A loose plug is the usual cause, about a 10 minute fix.'
                    % (wind_diff, STATION))
    return (None, ok)


kind, text = find_problem()
state = load_state()

if kind is None:
    print("%s OK: %s" % (stamp(), text))
    if state:       # there was a problem before, so tell the user it is over
        if send_alert('RESOLVED: %s is reporting normally again. %s.' % (STATION, text),
                      title='TriTown Monitor OK'):
            save_state({})
else:
    last_sent = state.get(kind)
    due = last_sent is None or (time.time() - last_sent) > REPEAT_MINUTES * 60
    if due:
        if send_alert(text):
            save_state({kind: time.time()})     # a different old problem is forgotten
    else:
        print("%s Still a problem (%s); already alerted recently." % (stamp(), kind))
