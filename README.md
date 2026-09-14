
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
