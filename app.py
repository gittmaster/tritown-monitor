from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import sqlite3, os, uuid
from datetime import datetime

app = Flask(__name__, static_folder='static', static_url_path='/static')
CORS(app)
DB_PATH = os.environ.get('DB_PATH', 'monitor.db')
API_KEY = os.environ.get('API_KEY', 'tritown2024')

# ── Database ──────────────────────────────────────────────────────

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as db:
        db.executescript('''
            CREATE TABLE IF NOT EXISTS readings (
                id TEXT PRIMARY KEY,
                device_id TEXT NOT NULL,
                location TEXT NOT NULL,
                temperature REAL,
                humidity REAL,
                alert_level TEXT,
                alert_message TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            );
        ''')
        db.commit()

# ── Alert logic ───────────────────────────────────────────────────

def get_alert(temp_c, humidity, pressure=None):
    temp_f = temp_c * 9/5 + 32
    pressure_falling = pressure is not None and pressure < 1013
    if temp_f > 95 and humidity < 20:
        return 'VERY_HIGH', 'VERY HIGH FIRE RISK � Very hot and dry! No burning, call 911 if fire spotted!'
    elif humidity < 30 and temp_f > 82:
        return 'RED', 'NO BURNING TODAY — Unusually dry and hot for TriTown! Do NOT light fires or burn leaves!'
    elif humidity < 40 and temp_f > 75:
        return 'YELLOW', 'CAUTION — Drier than normal for TriTown. Avoid burning outdoors. Keep water nearby.'
    elif humidity < 55 and temp_f > 70:
        return 'YELLOW', 'LOW CAUTION — Slightly dry for TriTown. Be mindful of open flames.'
    else:
        return 'GREEN', 'SAFE TODAY — Good air quality. Great day to be outside!'

# ── API routes ────────────────────────────────────────────────────

@app.route('/api/reading', methods=['POST'])
def post_reading():
    if request.headers.get('X-API-Key') != API_KEY:
        return jsonify({'error': 'Unauthorized'}), 401
    d = request.json
    temp     = d.get('temperature')
    humidity = d.get('humidity')
    level, message = get_alert(temp, humidity)
    rid = str(uuid.uuid4())
    with get_db() as db:
        db.execute("INSERT INTO readings VALUES (?,?,?,?,?,?,?,datetime('now'))",
                   (rid, d.get('device_id','unknown'), d.get('location','Unknown'),
                    temp, humidity, level, message))
        db.commit()
    return jsonify({'success': True, 'alert_level': level}), 201

@app.route('/api/latest', methods=['GET'])
def get_latest():
    with get_db() as db:
        rows = db.execute('''
            SELECT r.* FROM readings r
            INNER JOIN (
                SELECT location, MAX(created_at) as max_time
                FROM readings GROUP BY location
            ) latest ON r.location = latest.location AND r.created_at = latest.max_time
            ORDER BY r.location
        ''').fetchall()
        total = db.execute("SELECT COUNT(*) as c FROM readings").fetchone()['c']
    return jsonify({'readings': [dict(r) for r in rows], 'total_readings': total})

@app.route('/api/history', methods=['GET'])
def get_history():
    location = request.args.get('location', '')
    with get_db() as db:
        if location:
            rows = db.execute(
                "SELECT * FROM readings WHERE location=? ORDER BY created_at DESC LIMIT 50",
                (location,)).fetchall()
        else:
            rows = db.execute(
                "SELECT * FROM readings ORDER BY created_at DESC LIMIT 100").fetchall()
    return jsonify([dict(r) for r in rows])

@app.route('/api/stats', methods=['GET'])
def get_stats():
    with get_db() as db:
        total    = db.execute("SELECT COUNT(*) as c FROM readings").fetchone()['c']
        locations = db.execute("SELECT COUNT(DISTINCT location) as c FROM readings").fetchone()['c']
        latest   = db.execute("SELECT created_at FROM readings ORDER BY created_at DESC LIMIT 1").fetchone()
    return jsonify({
        'total_readings': total,
        'locations': locations,
        'last_updated': latest['created_at'] if latest else None
    })

# ── Frontend ──────────────────────────────────────────────────────

@app.route('/')
@app.route('/<path:path>')
def serve(path=''):
    return send_from_directory('static', 'index.html')

init_db()

if __name__ == '__main__':
    init_db()
    print("\n✅ TriTown Monitor running at http://localhost:5000\n")
    app.run(debug=True, port=5000)



