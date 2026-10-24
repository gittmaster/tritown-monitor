# Reliability: what can fail, what you are told, and what is kept

The goal: if anything stops working, the owner is told **which part** failed and **roughly how long it takes to fix**, and no readings are lost while it is down.

## Layers of protection

| Layer | Runs on | What it watches | How it tells you |
|---|---|---|---|
| `pi-sender` service (systemd) | Pi | The sender program | Restarts it within 10 seconds if it stops; also starts it at boot |
| WiFi watchdog (`wifi_watchdog.sh`, cron every 5 min) | Pi | The Pi's WiFi | Reconnects; reboots the Pi if it cannot |
| Pi self-report (`pi_sender.py` -> `/api/status`) | Pi | Temperature sensor, wind sensor, SD card space, readings waiting to send | Shown on the dashboard and used by the heartbeat message |
| Heartbeat (`check_heartbeat.py`, cron every 15 min) | Pi | Whether the website is still getting readings | Phone notification (ntfy), plain language, with likely cause and fix time |
| Outside check (GitHub Actions, every 30 min) | GitHub (not the Pi) | The same, from outside, so it works when the Pi is dead | Phone notification |
| UptimeRobot | Internet | Whether the dashboard answers | SMS and email |
| Render keep-awake (cron every 3 min) | Pi | Keeps the free web host from sleeping | none |

Why two watchers for "no data"? The heartbeat runs on the Pi, so it cannot speak if the Pi loses power or WiFi. The outside check runs somewhere else and can. The heartbeat speaks first for small problems (15 minutes); the outside check only speaks after 45 minutes of silence so you are not told twice for a hiccup.

## Failure table

| What fails | What the dashboard shows | What you get on your phone | Typical fix time |
|---|---|---|---|
| Pi loses power or WiFi | After 15 minutes: an amber "No new readings for N minutes" box on the card | Outside check, after about 45+ minutes: "No sensor data for N minutes... may have lost power or WiFi... is the Pi powered with its lights on?" | 5 to 10 minutes if it is a restart |
| Temperature sensor comes loose | Amber box naming the temperature sensor and "check its three wires and plug" | Heartbeat: "The Pi is on and online, but its temperature sensor is not answering..." | About 10 minutes |
| Wind sensor stops (loose plug, power, adapter) | "Wind sensor not reporting" warning on the card; danger level falls back to the original rule | Heartbeat: "Wind sensor has stopped reporting... check the wind sensor cable and its USB adapter" | About 10 minutes |
| Website or host (Render) down | Dashboard does not load | UptimeRobot SMS/email; heartbeat and outside check say "The website did not answer... often just waking up, wait 15 minutes" | Usually within 30 minutes |
| Database empty or broken | Dashboard shows no readings | Heartbeat: "No data in database!... Check that the Pi is on and the database is working" | Under an hour |
| Internet down at the station but the Pi is running | Old readings, then amber box | Outside check; readings are saved on the Pi and arrive later (see below) | When the internet returns |
| Sender program crashes | Brief gap | none (it restarts itself within 10 seconds) | Automatic |
| SD card filling up | none | Pi reports free space; the saved-readings file drops its oldest readings first rather than fill the card | Replace/clean the card |

Alerts repeat at most **once an hour** while a problem lasts, and a **RESOLVED** message is sent when readings return. If a phone alert fails to send, the heartbeat tries again on its next run.

## Data kept during an outage

If the Pi cannot reach the website, `pi_sender.py` saves each reading (with its **original time**) to `/home/pi/unsent_readings.jsonl` and resends them in order when the website is back (`reading_queue.py`).

Limits, so the SD card can never fill up:

- Nothing older than **60 days** (`QUEUE_DAYS`).
- The file never grows past **20 MB** (about 80,000 readings; 60 days is about 17,000).
- If the SD card has less than **200 MB** free, the oldest half is dropped first. The newest reading is always kept.

Safeguards on the website side:

- The website tells the Pi it understands resent readings (`supports_recorded_at` in its reply). The Pi **never resends** to a website version that does not say this, so an old website cannot be fed old data wrongly.
- Duplicates are skipped: a reading with the same device, time and temperature is not stored twice (the first reply may have been lost).
- Readings older than the retention period are ignored.
- The website keeps **60 days** by default (`RETENTION_DAYS`, 1 to 3650) and cleans up every 6 hours.

Known limit: after a power cut with no internet, the Pi's clock may run behind until it can reach a time server, so readings saved in that window can carry slightly early times. The Pi ignores a clock earlier than 2025 (not yet set).

## Where to look when something is wrong

On the Pi:

```bash
tail -n 20 /home/pi/sender.log                 # recent sends; look for [OK] Sent: ... lines
sudo systemctl status pi-sender --no-pager     # is the sender running?
pgrep -af pi_sender                            # should show exactly ONE line
tail -n 20 /home/pi/heartbeat.log              # what the heartbeat checked
wc -l /home/pi/unsent_readings.jsonl           # readings waiting to be sent (file may not exist)
crontab -l                                     # keep-awake, wifi watchdog and heartbeat lines
```

Two copies of the sender running (`pgrep` shows two lines) makes every reading arrive twice. The cause is a leftover `@reboot` or `pgrep` line in the crontab next to the systemd service. Remove those lines (the service is the only thing that should start the sender), stop the stray copy with `sudo kill <number>`, and leave the one started by `systemctl`.

On the website, `/api/stats` shows the last reading time, when wind last reported, the retention days, the alert method and any problems the Pi reported.

## Rolling back an update

- The website: redeploy the previous commit in Render, or `git revert` the merge. Our database changes are additions only (new columns and a new table), so a code rollback never needs a database change.
- The Pi: copy the previous files back (we keep a dated backup folder such as `~/backup-2026-10-19/`) and `sudo systemctl restart pi-sender`.
- The alert method: set `ALERT_METHOD` back to `legacy` on Render; no redeploy of code is needed beyond the settings save.

## Tests

Each protection above has an offline test: `test_reading_queue.py`, `test_retention_backfill.py`, `test_outage_end_to_end.py` (a full outage and recovery with a pretend website), `test_device_status.py`, `test_heartbeat_alerts.py`, `test_heartbeat_wind.py`, `test_outside_check.py`, `test_pi_sender_resilience.py`, `test_pi_sender_wind.py`. Run them all with `python run_tests.py`.
