"""
Backup check that runs OUTSIDE the Pi (on GitHub's computers, every 30 minutes).
If the Pi loses power or WiFi, the Pi cannot warn anyone, so this does.

Only alerts when data has been missing for more than 45 minutes, so the Pi's
own faster alert (15 minutes) normally speaks first and you are not told twice
for a small hiccup. Uses only Python's built-in libraries.
"""
import json
import os
import sys
import time
import urllib.request
from datetime import datetime

API = 'https://tritown-monitor.onrender.com/api/stats'
NTFY_TOPIC = os.environ.get('NTFY_TOPIC') or 'tritown-mfs-monitor-2024'
SILENT_AFTER_MINUTES = 45
TRIES = 3                      # the free website host can take a minute to wake up
TIMEOUT_SECONDS = 60
PAUSE_SECONDS = 20


def fetch_stats():
    request = urllib.request.Request(API, headers={'User-Agent': 'tritown-outside-check'})
    with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
        return json.loads(response.read().decode('utf-8'))


def minutes_since(text, now):
    when = datetime.strptime(str(text).split('.')[0], '%Y-%m-%d %H:%M:%S')
    return (now - when).total_seconds() / 60


def check(fetch=fetch_stats, now=None, sleep=time.sleep):
    """Return the alert text, or None if everything looks fine."""
    now = now or datetime.utcnow()
    data, error = None, None
    for attempt in range(TRIES):
        try:
            data = fetch()
            break
        except Exception as e:
            error = str(e)
            if attempt < TRIES - 1:
                sleep(PAUSE_SECONDS)
    if data is None:
        return ('BACKUP CHECK: The TriTown website did not answer after %d tries (%s). '
                'Nobody can see the fire danger numbers. First check: open the dashboard '
                'in a browser, then look at the website host (Render) for an outage. '
                'Usually fixed within 30 minutes.' % (TRIES, error))
    try:
        last = data.get('last_updated')
        if not last:
            return ('BACKUP CHECK: The website has no readings at all. Check that the Pi '
                    'at Middleton Fire Station is on and sending.')
        age = minutes_since(last, now)
    except Exception as e:
        return 'BACKUP CHECK: The website answered with something unexpected (%s).' % str(e)
    if age > SILENT_AFTER_MINUTES:
        return ('BACKUP CHECK: No sensor data for %.0f minutes. The Pi at Middleton Fire '
                'Station may have lost power or WiFi (a dead Pi cannot warn you itself). '
                'First check: is the Pi powered with its lights on, and is the WiFi up? '
                'Restarting the power often fixes it in 5 to 10 minutes.' % age)
    return None


def send(message):
    request = urllib.request.Request(
        'https://ntfy.sh/' + NTFY_TOPIC, data=message.encode('utf-8'),
        headers={'Title': 'TriTown Backup Check'}, method='POST')
    urllib.request.urlopen(request, timeout=20).read()


def main():
    message = check()
    if message is None:
        print('OK')
        return 0
    print(message)
    try:
        send(message)
        print('Alert sent.')
        return 0
    except Exception as e:
        print('Could not send the alert: %s' % str(e))
        return 1          # makes the GitHub run show as failed, so GitHub emails you


if __name__ == '__main__':
    sys.exit(main())
