from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import os, uuid
from datetime import datetime

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
    conn.commit()
    cur.close()
    conn.close()

init_db()

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

@app.route('/api/reading', methods=['POST'])
def post_reading():
    if request.headers.get('X-API-Key') != API_KEY:
        return jsonify({'error': 'Unauthorized'}), 401
    d = request.json
    temp = d.get('temperature')
    humidity = d.get('humidity')
    pressure = d.get('pressure')
    dew_point = d.get('dew_point')
    wind_speed = d.get('wind_speed')
    level, message = get_alert(temp, humidity, pressure, wind_speed)
    rid = str(uuid.uuid4())
    p = ph()
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        'INSERT INTO readings (id,device_id,location,temperature,humidity,pressure,dew_point,alert_level,alert_message) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)' % tuple([p]*9),
        (rid, d.get('device_id','unknown'), d.get('location','Unknown'), temp, humidity, pressure, dew_point, level, message)
    )
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({'success': True, 'alert_level': level}), 201

@app.route('/api/latest', methods=['GET'])
def get_latest():
    p = ph()
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
    cur.close()
    conn.close()
    return jsonify({'total_readings': total, 'locations': locations, 'last_updated': str(latest['created_at']) if latest else None})

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

@app.route('/')
@app.route('/<path:path>')
def serve(path=''):
    return send_from_directory('static', 'index.html')

if __name__ == '__main__':
    print('\n✅ TriTown Monitor running at http://localhost:5000\n')
    app.run(debug=True, port=5000)
