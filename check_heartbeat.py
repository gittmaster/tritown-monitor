import requests
from datetime import datetime

API        = 'https://tritown-monitor.onrender.com/api/stats'
NTFY_TOPIC = 'tritown-mfs-monitor-2024'

def send_alert(message):
    try:
        requests.post(
            'https://ntfy.sh/' + NTFY_TOPIC,
            data=message.encode('utf-8'),
            headers={'Title': 'TriTown Monitor ALERT'},
            timeout=10
        )
        print("%s ALERT sent: %s" % (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), message))
    except Exception as e:
        print("%s Alert failed: %s" % (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), str(e)))

try:
    r    = requests.get(API, timeout=10)
    data = r.json()
    last = data.get('last_updated')
    if last:
        last_time = datetime.strptime(last.split('.')[0], '%Y-%m-%d %H:%M:%S')
        diff = (datetime.utcnow() - last_time).total_seconds() / 60
        if diff > 15:
            send_alert('No sensor data for %.0f minutes! Check Pi at Middleton Fire Station.' % diff)
        else:
            print("%s OK: Last reading %.0f min ago" % (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), diff))
            # Wind check: only if wind has reported before (so a station with no
            # wind sensor is never nagged), and only while temperature/humidity
            # are still arriving (so one outage does not send two alerts).
            wind_last = data.get('wind_last_seen')
            if wind_last:
                wind_time = datetime.strptime(wind_last.split('.')[0], '%Y-%m-%d %H:%M:%S')
                wind_diff = (datetime.utcnow() - wind_time).total_seconds() / 60
                if wind_diff > 30:
                    send_alert('Wind sensor has stopped reporting for %.0f minutes. Temperature and humidity are still OK. Check the wind sensor and its USB adapter at Middleton Fire Station.' % wind_diff)
    else:
        send_alert('No data in database! Dashboard may be down.')
except Exception as e:
    send_alert('Dashboard unreachable: %s' % str(e))
