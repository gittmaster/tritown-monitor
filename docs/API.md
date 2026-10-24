# Website API

Base address: your website (ours is `https://tritown-monitor.onrender.com`). All bodies and replies are JSON. Endpoints that **change** data need the header `X-API-Key: <your API key>`; reading is public.

Units: temperature in **degrees Celsius**, humidity in percent, wind speed in **mph**, wind direction in degrees (0 to 360, the direction the wind comes **from**), times in UTC.

## `POST /api/reading` (key required)

The Pi sends one reading.

```json
{
  "device_id": "pi-library",
  "location": "Middleton Fire Station",
  "temperature": 11.0,
  "humidity": 46.8,
  "dew_point": 0.3,
  "wind_speed": 7.2,
  "wind_direction": 220.0
}
```

- `temperature` and `humidity` are the real readings; `pressure` is accepted but not used.
- `wind_speed` (0 to 200) and `wind_direction` (0 to 360) are optional. A missing or nonsense wind value is stored as empty and **never** rejects the reading.
- `recorded_at` (UTC, `YYYY-MM-DDTHH:MM:SS`) is only sent by the Pi when it is resending a reading it had to save; live readings omit it and the website stamps them on arrival.

Reply (`201`):

```json
{"success": true, "alert_level": "VERY_HIGH", "supports_recorded_at": true}
```

Extra fields: `"duplicate": true` (an identical resent reading was already stored) or `"skipped"` (older than the retention period). A wrong or missing key returns `401`.

The fire danger level is calculated here, with the method chosen by `ALERT_METHOD`; see [ALERTS.md](ALERTS.md).

## `POST /api/status` (key required)

The Pi reports its own health.

```json
{
  "device_id": "pi-library",
  "location": "Middleton Fire Station",
  "problems": [{"part": "wind_sensor", "detail": "The wind sensor has not answered for 3 readings in a row. Check the USB adapter and cable."}],
  "disk_free_mb": 20123.4,
  "queue_waiting": 0
}
```

`part` must be `temperature_sensor` or `wind_sensor`. An empty `problems` list clears earlier problems. Problems older than 180 minutes are not shown. Reply: `{"success": true, "problems": 1}`.

## `GET /api/latest`

The newest reading for each location, plus `total_readings`. Each reading includes its alert level and message, wind fields, `wind_last_seen` (when that location last reported wind) and `device_problems` (current problems the Pi reported for it). The dashboard calls this every 5 seconds.

## `GET /api/history`

The last 50 readings (add `?location=<name>` to filter), or the last 100 across all locations, newest first. Used for the humidity trend chart.

## `GET /api/stats`

Small health summary used by the watchdogs:

```json
{
  "alert_method": "class_day",
  "device_problems": [],
  "herbaceous_stage": "transition",
  "last_updated": "2026-10-24 16:39:37.412609",
  "locations": 1,
  "retention_days": 60,
  "total_readings": 11899,
  "wind_last_seen": "2026-10-24 16:39:37.412609"
}
```

`last_updated` is UTC. `wind_last_seen` is empty until a wind reading has ever arrived. This is also the quickest way to confirm which alert method is live.

## `GET /api/forecast?zip=01949`

The 7-day National Weather Service forecast for a five-digit ZIP code (default 01949, Middleton MA), with a fire danger level for every forecast hour, calculated with the same method as live readings. The dashboard shows the highest level of any hour in each day and marks days 4 to 7 as "Outlook, less certain"; the API itself returns every hour. Replies are cached for 30 minutes. A ZIP that is not exactly five digits returns `400`; if the weather service cannot be reached it returns the last good copy, or `502`.

## `POST /api/clear` (key required)

Deletes **all** readings. For testing only; there is no undo.

## Everything else

Any other path returns the dashboard page (`static/index.html`).
