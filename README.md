
---

## 📊 Traffic Monitoring
- **Google Analytics** — tracks visitors, devices and locations
- View real-time visitors at: https://analytics.google.com
- Key reports: Realtime (who's on now), Engagement (daily visits), Demographics (visitor location)
- **UptimeRobot** — monitors dashboard uptime with SMS and email alerts
- **ntfy.sh** — push notifications when Pi stops sending data

---

## 📈 Dashboard Features
- **5 NFDRS Alert Levels** — LOW, MODERATE, HIGH, VERY HIGH, EXTREME
- **Live temperature and humidity** — updates every 5 minutes
- **Humidity trend line graph** — Y-axis labels, grid lines, time stamps
- **Works on iPhone and web browser**
- **Disclaimer bar** — "For awareness only. Always follow official Fire Marshall guidance."

## 🔔 Observability & Alerting
- **UptimeRobot** — monitors dashboard uptime, sends SMS and email alerts
- **ntfy.sh** — push notifications to phone when Pi stops sending data
  - Topic: `tritown-mfs-monitor-2024`
  - Heartbeat check every 15 minutes via `/home/pi/check_heartbeat.py`
- **Google Analytics** — tracks visitor count, location and device type
- **Render keepalive** — Pi pings Render every 3 minutes to prevent spin-down

## 🔐 Security
- Raspberry Pi password changed from default
- API key required for all write operations
- Google Analytics Measurement ID stored securely

## Settings (set on Render, under Environment)

| Setting | What it does | Default |
|---|---|---|
| `RETENTION_DAYS` | Days of readings the website keeps (1 to 3650). | 60 |
| `ALERT_METHOD` | `legacy` = original rule. `class_day` = the fire chief's method (Chart A + Chart D). | legacy |
| `HERBACEOUS_STAGE` | `cured`, `transition` or `green`. Only used by `class_day`. Change when the district changes the season. | transition |
| `NTFY_TOPIC` (GitHub secret) | Phone-alert topic for the outside check. Optional. | the standard topic |

To switch back to the original alert rule, set `ALERT_METHOD` to `legacy` (or delete it). Nothing else changes.

## Installing the wind / resilience update (in this order)

1. Merge the feature branch and let Render deploy. Check the dashboard right away. The new database columns/tables are additions only, so rolling back needs no database change (rollback tag: `pre-class-day`).
2. Back up the Pi's schedule (`crontab -l > ~/crontab.backup`), then copy `pi_sender.py`, `wind_sensor.py`, `reading_queue.py` and `check_heartbeat.py` to `/home/pi/`, `pip3 install pyserial`, and restart with `sudo systemctl restart pi-sender`.
3. Remove the two redundant lines from the Pi's crontab (`@reboot ... pi_sender.py` and the `pgrep` watchdog). The `pi-sender` system service already starts and restarts the sender.
4. Leave `ALERT_METHOD` on `legacy` until the fire department has confirmed the chart answers.

Always install the website first, then the Pi: the Pi only resends saved readings to a website that says it understands them.

## Assumptions we made (also in the presentation)

We did not wait for answers on these; we picked the most sensible option and listed it for the fire department. If they want something different, we change it.

- Grass stage: Transition until the district announces a change (`HERBACEOUS_STAGE`).
- Wind: rounded to whole mph, averaged over 30 seconds every 5 minutes, used as measured (the chart assumes 20-foot winds).
- Classes 1 to 5 are shown as Low, Moderate, High, Very High, Extreme.
- No wind reading: the original rule is used and the message says wind is missing.
- Our copy of the chart gives fuel moisture 28 (the chief wrote 29) for 63F, 85%, Green; the class is the same.
- Readings are kept 60 days (`RETENTION_DAYS`).
