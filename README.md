# TriTown Fire Danger Monitor

A low-cost, neighborhood fire-weather station. A Raspberry Pi with a temperature/humidity sensor and a wind sensor sits outside the Middleton (MA) Fire Station and sends a reading every 5 minutes to a small website. The website turns each reading into a fire danger level (Low to Extreme) using the fire department's own "class day" method, and shows it, plus a 7-day National Weather Service forecast run through the same method, on a public dashboard.

Built by a high-school student as a community capstone project for the Middleton Fire Department. Live dashboard: <https://tritown-monitor.onrender.com>

> For awareness only. Always follow official Fire Marshal guidance.

---

## How it works

```
 Wind sensor ──RS485──► USB adapter ─┐
                                      ├──► Raspberry Pi ──internet──► Website (Flask on Render) ──► Database (Supabase Postgres)
 Temp/humidity sensor (DHT22) ───────┘     pi_sender.py                  app.py                              │
                                                                          │                                  │
                                                       Public dashboard ◄─┘   National Weather Service ──────┘ (forecast, fetched on demand)
```

1. **Pi** (`pi_sender.py`) reads the DHT22 (temperature + humidity) and the wind sensor (30-second average speed and direction) every 5 minutes and posts them to the website.
2. **Website** (`app.py`) stores the reading, works out the fire danger level, and serves the dashboard (`static/index.html`) and a small JSON API.
3. **Alerts** are calculated by one of two methods (see [docs/ALERTS.md](docs/ALERTS.md)): the original simple rule (`legacy`) or the fire chief's class-day charts (`class_day`).
4. **Watchdogs** tell the owner by phone notification when anything stops working, and say which part failed (see [docs/RELIABILITY.md](docs/RELIABILITY.md)).

## Documentation

| Guide | What is in it |
|---|---|
| [docs/BUILD_FROM_SCRATCH.md](docs/BUILD_FROM_SCRATCH.md) | Parts list, wiring, Pi setup, website + database setup, going live. Start here to build your own. |
| [docs/ALERTS.md](docs/ALERTS.md) | How the fire danger level is calculated, how wind is included, worked examples, every assumption. |
| [docs/WIND_SENSOR.md](docs/WIND_SENSOR.md) | The wind sensor, wiring (including a long cable run), testing, mounting. |
| [docs/RELIABILITY.md](docs/RELIABILITY.md) | Every failure we planned for: what you are told, how long it takes to fix, data kept during outages. |
| [docs/API.md](docs/API.md) | The website's endpoints. |

## What is in this repository

| File | Runs on | Purpose |
|---|---|---|
| `app.py` | Website | Flask app: API, alert calculation, data retention, serves the dashboard |
| `class_day.py` | Website | The fire chief's Chart A + Chart D method (typed in as printed, with a self-check) |
| `weather_forecast.py` | Website | National Weather Service forecast lookup by ZIP code |
| `static/index.html` | Browser | The dashboard (single page; works on phones) |
| `pi_sender.py` | Pi | Reads sensors, sends readings, saves them when the internet is down, reports its own health |
| `wind_sensor.py` | Pi | Reads the RS485 wind sensor; never raises, so a bad wind sensor cannot stop temperature readings |
| `reading_queue.py` | Pi | Saves unsent readings to disk (60 days, size and SD-card limits) and resends them in order |
| `check_heartbeat.py` | Pi (cron) | Every 15 minutes: sends a plain-language phone alert if data stops, and an all-clear when it recovers |
| `outside_check.py` + `.github/workflows/outside-check.yml` | GitHub | Backup watchdog that runs off the Pi, so it can warn you even if the Pi loses power or WiFi |
| `wind_probe.py` | Pi or PC | Read-only test of the wind sensor; never changes a sensor setting |
| `pi-sender.service` | Pi | systemd service that starts `pi_sender.py` at boot and restarts it if it stops |
| `crontab.new` | Pi | Reference crontab (keep-awake ping and WiFi watchdog) |
| `render.yaml`, `requirements.txt` | Render | Deployment settings and Python packages |
| `test_*.py` | Any PC | Offline tests (see Testing below) |

## Quick start (run the website on your own computer)

```bash
git clone https://github.com/gittmaster/tritown-monitor.git
cd tritown-monitor
python -m venv venv
venv\Scripts\activate          # Windows;  macOS/Linux: source venv/bin/activate
pip install -r requirements.txt
python app.py                  # opens at http://localhost:5000
```

With no `DATABASE_URL` set, the app uses a local SQLite file (`monitor_v2.db`), so you do not need Postgres to try it. To see something on the dashboard, send a test reading from a second terminal:

```bash
python -c "import requests; r = requests.post('http://localhost:5000/api/reading', headers={'X-API-Key': 'tritown2024'}, json={'device_id': 'test', 'location': 'Test', 'temperature': 11, 'humidity': 47, 'wind_speed': 7.2, 'wind_direction': 220}); print(r.status_code, r.json())"
```

It should print `201` and the alert level. Temperature is in degrees Celsius (11 C is about 52 F); wind speed is in mph. The built-in test API key is only for local testing; see Security.

## Settings

Website settings are environment variables (on Render: your service, **Environment**).

| Setting | What it does | Default |
|---|---|---|
| `DATABASE_URL` | Postgres connection string (Supabase). Leave unset to use local SQLite. | unset |
| `DB_PATH` | SQLite file name when `DATABASE_URL` is unset. | `monitor_v2.db` |
| `API_KEY` | Secret the Pi must send to post readings. **Set your own.** | built-in test key |
| `RETENTION_DAYS` | Days of readings the website keeps (1 to 3650). Old readings are removed every 6 hours. | 60 |
| `ALERT_METHOD` | `legacy` = original rule. `class_day` = the fire chief's method. | `legacy` |
| `HERBACEOUS_STAGE` | `cured`, `transition` or `green`. Only used by `class_day`. Change it when the district announces the season changed. | `transition` |
| `NTFY_TOPIC` (GitHub secret) | Phone-alert topic for the outside check. Optional. | the standard topic |

To go back to the original alert rule, set `ALERT_METHOD` to `legacy` (or delete it). Nothing else changes.

The Pi's settings are constants at the top of `pi_sender.py` (device name, location, website address, API key, 5-minute interval, DHT22 pin, wind port, queue file and days).

## Testing

All tests are plain Python scripts that run offline (no internet, no real database):

```bash
python test_class_day.py        # the fire chief's charts and the three worked examples
python test_wind_sensor.py      # wind sensor reading, with a pretend sensor
python test_reading_queue.py    # saving and resending readings
python test_device_status.py    # the Pi's self-report and the dashboard messages
```

To run everything: `python run_tests.py`. Each script prints `N passed, M failed`.

Notes:

- `test_alerts.py` has one **known failure** (a case marked "known bug"): with no wind data, the *original* rule cannot reach EXTREME because it needs wind of 25 mph or more. That is the reason the `class_day` method falls back to the original rule with a "wind data not available" message. It is left in as documentation of the old behavior.
- `test_live_forecast.py` talks to the real National Weather Service and needs the internet, so `run_tests.py` skips it.
- The scripts exit with success even when a check fails; read the `passed/failed` line (the runner does this for you).
- Run the tests after every change to the dashboard or the alert logic.

## Security

- Posting readings, posting Pi status and clearing data all require the `X-API-Key` header. Reading data is public.
- The repository contains a placeholder API key (in `app.py`, `pi_sender.py` and `render.yaml`) so the project runs out of the box. **For a real deployment, set your own `API_KEY` on Render and put the same value in `pi_sender.py` on the Pi, and do not commit it.** If the repository is public, treat the placeholder as already known.
- Change the Pi's default password, and keep SSH access limited to people you trust.
- Never commit `DATABASE_URL` or any password. `.env` and database files are already in `.gitignore`.
- The dashboard is a read-only public page. The one input it accepts (a forecast ZIP code) is checked to be exactly five digits.

## Monitoring and traffic

- **UptimeRobot**: pings the dashboard every 5 minutes and sends SMS/email if the website is down.
- **ntfy.sh**: phone notifications (topic in `check_heartbeat.py` and `outside_check.py`). Install the free ntfy app and subscribe to your own topic.
- **Render keep-awake**: the free Render plan sleeps when idle, so the Pi calls the website every 3 minutes (see `crontab.new`).
- **Google Analytics**: optional visitor statistics on the dashboard.

## Installing an update (in this order)

1. Merge the branch to `master` and let Render deploy. Open the dashboard and `/api/stats` right away to check it. Database changes in our updates are additions only (new columns/tables), so rolling the code back never needs a database change.
2. On the Pi: back up the schedule (`crontab -l > ~/crontab.backup`), copy the changed files to `/home/pi/`, then `sudo systemctl restart pi-sender`.
3. Check the log: `tail -n 15 /home/pi/sender.log` should show `[OK] Sent:` lines.
4. Switch settings (such as `ALERT_METHOD`) last, one at a time.

Always update the website before the Pi: the Pi only resends saved readings to a website that says it understands them.

## Known limits

- One station, one location (the system supports several, but only one is deployed).
- The wind sensor is mounted lower than the 20 feet the fire chart assumes, so it reads lighter winds than the chart's standard. See [docs/WIND_SENSOR.md](docs/WIND_SENSOR.md).
- The forecast panel uses National Weather Service forecasts, not the local sensor.
- The free hosting tiers (Render, Supabase) can pause or sleep; the keep-awake ping and the outside check exist for that reason.

## Assumptions we made (also listed in the presentation)

We did not wait for answers on these; we picked the most sensible option and listed it for the fire department. If they want something different, we change it. Full detail is in [docs/ALERTS.md](docs/ALERTS.md).

- Grass stage is **Transition** until the district announces a change (`HERBACEOUS_STAGE`).
- Wind is averaged over 30 seconds at each 5-minute reading and rounded to whole mph. It is used as measured, even though the chart assumes 20-foot winds.
- Classes 1 to 5 are shown as Low, Moderate, High, Very High, Extreme.
- With no wind reading, the original rule is used and the message says wind is missing.
- Our copy of Chart A gives fuel moisture 28 (the chief wrote 29) for 63 F, 85 %, Green; the class is the same.
- Readings are kept 60 days (`RETENTION_DAYS`).
- The method is stricter than the original rule: breezy days can read Very High where the original rule said Low.
