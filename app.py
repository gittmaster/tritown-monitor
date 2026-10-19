from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import os, uuid, time
from datetime import datetime, timedelta

app = Flask(__name__, static_folder='static', static_url_path='/static')
CORS(app)
API_KEY      = os.environ.get('API_KEY', 'tritown2024')
DATABASE_URL = os.environ.get('DATABASE_URL', '')

def get_db():
    if DATABASE_URL:
        import psycopg2
        import psycopg2.extras
        conn = psycopg2.connect(DATABASE_URL, sslmode='require')
        conn.cursor_factory = psycopg2.extras.RealDictCursor
        return conn
    else:
        import sqlite3
        conn = sqlite3.connect(os.environ.get('DB_PATH', 'monitor_v2.db'))
        conn.row_factory = sqlite3.Row
        return conn

def is_pg():
    return bool(DATABASE_URL)

def ph():
    return '%s' if is_pg() else '?'

DEFAULT_RETENTION_DAYS = 60

def read_retention_days(raw):
    """How many days of readings to keep. Set RETENTION_DAYS on the host
    (for example 30 or 90). Anything missing or silly falls back to 60."""
    try:
        days = int(str(raw).strip())
    except (TypeError, ValueError):
        return DEFAULT_RETENTION_DAYS
    return days if 1 <= days <= 3650 else DEFAULT_RETENTION_DAYS

RETENTION_DAYS = read_retention_days(os.environ.get('RETENTION_DAYS'))

def utc_text(when):
    return when.strftime('%Y-%m-%d %H:%M:%S')

def cleanup_old_readings():
    cutoff = utc_text(datetime.utcnow() - timedelta(days=RETENTION_DAYS))
    conn = get_db()
    cur = conn.cursor()
    cur.execute('DELETE FROM readings WHERE created_at < ' + ph(), (cutoff,))
    conn.commit()
    cur.close()
    conn.close()

_last_cleanup = time.time()   # startup already cleaned; then repeat every few hours
CLEANUP_EVERY_SECONDS = 6 * 3600

def maybe_cleanup():
    """Keep the retention rule enforced even if the site never restarts.
    Fenced off: a cleanup problem must never block a reading."""
    global _last_cleanup
    if time.time() - _last_cleanup < CLEANUP_EVERY_SECONDS:
        return
    _last_cleanup = time.time()
    try:
        cleanup_old_readings()
    except Exception as e:
        print("Periodic cleanup failed: %s" % str(e))

def parse_recorded_at(value, now=None):
    """The Pi may resend a reading it saved during an outage and tell us when
    it was really taken (UTC, like 2026-10-18T21:30:00). Returns (datetime, status):
      ok       - use this time
      none     - not provided or unreadable: caller stamps it with the current time
      too_old  - older than we keep anyway: caller skips it
    A time in the future is treated as unreadable (a wrong clock must not
    put a reading ahead of real ones)."""
    if value is None:
        return None, 'none'
    now = now or datetime.utcnow()
    try:
        text = str(value).strip().rstrip('Z').replace('T', ' ').split('.')[0]
        when = datetime.strptime(text, '%Y-%m-%d %H:%M:%S')
    except (TypeError, ValueError):
        return None, 'none'
    if when > now + timedelta(minutes=10):
        return None, 'none'
    if when < now - timedelta(days=RETENTION_DAYS):
        return None, 'too_old'
    return when, 'ok'

def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS readings (
            id TEXT PRIMARY KEY,
            device_id TEXT NOT NULL,
            location TEXT NOT NULL,
            temperature REAL,
            humidity REAL,
            pressure REAL,
            dew_point REAL,
            alert_level TEXT,
            alert_message TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # Wind columns (added later). Additive only: old rows get NULL, and older
    # versions of this app simply ignore the extra columns, so a rollback of
    # the code never needs a database change.
    for col in ('wind_speed', 'wind_direction'):
        if is_pg():
            cur.execute('ALTER TABLE readings ADD COLUMN IF NOT EXISTS %s REAL' % col)
        else:
            cur.execute('PRAGMA table_info(readings)')
            existing = [row[1] for row in cur.fetchall()]
            if col not in existing:
                cur.execute('ALTER TABLE readings ADD COLUMN %s REAL' % col)
    conn.commit()
    cur.close()
    conn.close()

try:
    init_db()
except Exception as e:
    print("DB init failed: %s" % str(e))
try:
    cleanup_old_readings()
except Exception as e:
    print("Cleanup failed: %s" % str(e))

def get_alert(temp_c, humidity, pressure=None, wind_speed=None):
    temp_f = temp_c * 9/5 + 32
    wind = wind_speed if wind_speed else 0
    if humidity <= 15 and temp_f >= 85 and wind >= 25:
        return 'EXTREME', 'EXTREME - Every fire could become large. No burning. Call 911 immediately!'
    elif humidity <= 20 and temp_f >= 80:
        return 'VERY_HIGH', 'VERY HIGH - Fires start easily and spread rapidly. No outdoor burning!'
    elif humidity <= 30 and temp_f >= 70:
        return 'HIGH', 'HIGH - Wildfires ignite easily. Outdoor burning strongly discouraged!'
    elif humidity <= 50 and temp_f >= 60:
        return 'MODERATE', 'MODERATE - Wildfires may occur. Restrict burning to early morning or late evening.'
    else:
        return 'LOW', 'LOW - Wildfire ignitions unlikely. Outdoor burning is safest.'

def clean_wind(value, low, high):
    """Return value as a float if it is a sane number in [low, high], else None.
    A bad wind sensor must never block the temperature/humidity reading, so a
    bad or missing wind value is quietly stored as NULL instead of rejected."""
    if value is None or isinstance(value, bool):
        return None
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    if v != v or v < low or v > high:  # v != v catches NaN
        return None
    return v

@app.route('/api/reading', methods=['POST'])
def post_reading():
    if request.headers.get('X-API-Key') != API_KEY:
        return jsonify({'error': 'Unauthorized'}), 401
    d = request.json
    temp = d.get('temperature')
    humidity = d.get('humidity')
    pressure = d.get('pressure')
    dew_point = d.get('dew_point')
    wind_speed = clean_wind(d.get('wind_speed'), 0, 200)          # mph
    wind_direction = clean_wind(d.get('wind_direction'), 0, 360)  # degrees
    level, message = get_alert(temp, humidity, pressure, wind_speed)
    rid = str(uuid.uuid4())
    p = ph()
    device_id = d.get('device_id', 'unknown')
    taken_at, taken_status = parse_recorded_at(d.get('recorded_at'))
    # 'supports_recorded_at' tells the Pi this site understands saved-and-resent
    # readings, so the Pi never resends old data to an older site version.
    reply = {'success': True, 'alert_level': level, 'supports_recorded_at': True}
    if taken_status == 'too_old':
        reply['skipped'] = 'older than the retention period'
        return jsonify(reply), 201
    conn = get_db()
    cur = conn.cursor()
    if taken_at is not None:
        # A resent reading: if we already have it (the first reply was lost on
        # the way back), do not store it twice.
        stamp = utc_text(taken_at)
        cur.execute('SELECT 1 FROM readings WHERE device_id=' + p + ' AND created_at=' + p + ' AND temperature=' + p + ' LIMIT 1',
                    (device_id, stamp, temp))
        if cur.fetchone():
            cur.close()
            conn.close()
            reply['duplicate'] = True
            return jsonify(reply), 201
        cur.execute(
            'INSERT INTO readings (id,device_id,location,temperature,humidity,pressure,dew_point,alert_level,alert_message,wind_speed,wind_direction,created_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)' % tuple([p]*12),
            (rid, device_id, d.get('location','Unknown'), temp, humidity, pressure, dew_point, level, message, wind_speed, wind_direction, stamp)
        )
    else:
        cur.execute(
            'INSERT INTO readings (id,device_id,location,temperature,humidity,pressure,dew_point,alert_level,alert_message,wind_speed,wind_direction) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)' % tuple([p]*11),
            (rid, device_id, d.get('location','Unknown'), temp, humidity, pressure, dew_point, level, message, wind_speed, wind_direction)
        )
    conn.commit()
    cur.close()
    conn.close()
    maybe_cleanup()
    return jsonify(reply), 201

@app.route('/api/latest', methods=['GET'])
def get_latest():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT r.* FROM readings r
        INNER JOIN (
            SELECT location, MAX(created_at) as max_time
            FROM readings GROUP BY location
        ) latest ON r.location = latest.location AND r.created_at = latest.max_time
        ORDER BY r.location
    """)
    rows = [dict(r) for r in cur.fetchall()]
    cur.execute('SELECT COUNT(*) as c FROM readings')
    total = cur.fetchone()['c']
    # When did each location last report wind? Lets the dashboard tell "this
    # location has no wind sensor" apart from "its wind sensor stopped working".
    # Done last and fenced off: a problem here must never break the main readings.
    wind_seen = {}
    try:
        cur.execute('SELECT location, MAX(created_at) AS last_wind FROM readings '
                    'WHERE wind_speed IS NOT NULL GROUP BY location')
        wind_seen = {r['location']: r['last_wind'] for r in cur.fetchall()}
    except Exception as e:
        print("wind_last_seen lookup failed: %s" % str(e))
        try:
            conn.rollback()
        except Exception:
            pass
    for row in rows:
        row['wind_last_seen'] = wind_seen.get(row['location'])
    cur.close()
    conn.close()
    return jsonify({'readings': rows, 'total_readings': total})

@app.route('/api/history', methods=['GET'])
def get_history():
    location = request.args.get('location', '')
    p = ph()
    conn = get_db()
    cur = conn.cursor()
    if location:
        cur.execute('SELECT * FROM readings WHERE location=' + p + ' ORDER BY created_at DESC LIMIT 50', (location,))
    else:
        cur.execute('SELECT * FROM readings ORDER BY created_at DESC LIMIT 100')
    rows = [dict(r) for r in cur.fetchall()]
    cur.close()
    conn.close()
    return jsonify(rows)

@app.route('/api/stats', methods=['GET'])
def get_stats():
    conn = get_db()
    cur = conn.cursor()
    cur.execute('SELECT COUNT(*) as c FROM readings')
    total = cur.fetchone()['c']
    cur.execute('SELECT COUNT(DISTINCT location) as c FROM readings')
    locations = cur.fetchone()['c']
    cur.execute('SELECT created_at FROM readings ORDER BY created_at DESC LIMIT 1')
    latest = cur.fetchone()
    # Most recent reading that included wind (None if wind has never reported).
    # Used by check_heartbeat.py to warn when a wind sensor goes quiet. Fenced
    # off so it can never break the stats the heartbeat already relies on.
    wind_last = None
    try:
        cur.execute('SELECT created_at FROM readings WHERE wind_speed IS NOT NULL '
                    'ORDER BY created_at DESC LIMIT 1')
        w = cur.fetchone()
        wind_last = str(w['created_at']) if w else None
    except Exception as e:
        print("wind stats lookup failed: %s" % str(e))
        try:
            conn.rollback()
        except Exception:
            pass
    cur.close()
    conn.close()
    return jsonify({'total_readings': total, 'locations': locations,
                    'last_updated': str(latest['created_at']) if latest else None,
                    'wind_last_seen': wind_last,
                    'retention_days': RETENTION_DAYS})

@app.route('/api/clear', methods=['POST'])
def clear_readings():
    if request.headers.get('X-API-Key') != API_KEY:
        return jsonify({'error': 'Unauthorized'}), 401
    conn = get_db()
    cur = conn.cursor()
    cur.execute('DELETE FROM readings')
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({'success': True})

# Forecast cache: NWS only refreshes about hourly, and Render runs a single
# gunicorn worker, so an uncached upstream fetch would stall every viewer's
# live /api/latest polling while it runs.
_FORECAST_TTL_SECONDS = 30 * 60
_FORECAST_CACHE_MAX = 200
_forecast_cache = {}  # zip_code -> (fetched_at, payload)


@app.route('/api/forecast', methods=['GET'])
def get_forecast_route():
    import re, time
    from weather_forecast import get_forecast, get_hourly_projection

    zip_code = request.args.get('zip', '01949').strip()  # defaults to Middleton, MA
    if not re.fullmatch(r'\d{5}', zip_code):
        return jsonify({'error': 'ZIP code must be exactly 5 digits'}), 400

    now = time.time()
    cached = _forecast_cache.get(zip_code)
    if cached and now - cached[0] < _FORECAST_TTL_SECONDS:
        return jsonify(cached[1])

    try:
        daily = get_forecast(zip_code)
        hourly = get_hourly_projection(zip_code, hours=168)
    except Exception as e:
        if cached:
            return jsonify(cached[1])  # NWS unreachable: serve last good copy
        return jsonify({'error': f'Could not fetch forecast: {e}'}), 502

    for hour in hourly['hours']:
        level, message = get_alert(
            hour['temperature_c'], hour['humidity_pct'],
            wind_speed=hour['wind_speed_mph'],
        )
        hour['alert_level'] = level
        hour['alert_message'] = message

    payload = {
        'place_name': daily['place_name'],
        'daily': daily['periods'],
        'hourly': hourly['hours'],
    }

    if zip_code not in _forecast_cache and len(_forecast_cache) >= _FORECAST_CACHE_MAX:
        oldest = min(_forecast_cache, key=lambda z: _forecast_cache[z][0])
        del _forecast_cache[oldest]
    _forecast_cache[zip_code] = (now, payload)

    return jsonify(payload)

@app.route('/')
@app.route('/<path:path>')
def serve(path=''):
    return send_from_directory('static', 'index.html')

if __name__ == '__main__':
    print('\n✅ TriTown Monitor running at http://localhost:5000\n')
    app.run(debug=True, port=5000)
