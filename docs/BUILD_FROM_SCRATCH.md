# Build it from scratch

This guide takes you from an empty box of parts to a working station and dashboard. Do the parts in order. Each part ends with a check so you know it worked before you move on.

You will set up four things:

1. The **website and database** (Render for the website, about $7 a month; Supabase free plan for the database; code on GitHub).
2. The **Raspberry Pi** with its sensors.
3. The **phone alerts**.
4. The **backup watchdogs**.

Allow a weekend. Use your own passwords and keys everywhere; the ones in the repository are placeholders.

---

## 0. Parts

| Part | Notes |
|---|---|
| Raspberry Pi (any model with WiFi, e.g. Pi Zero 2 W, 3 or 4) + power supply + microSD card (16 GB or more) | Official power supply recommended |
| DHT22 temperature and humidity sensor (the 3-pin board version has a built-in resistor) | If yours has 4 bare pins, add a 10 k ohm resistor between the data pin and 3.3 V |
| Veinasa XS-WSDS01 wind sensor (RS485 version) | See [WIND_SENSOR.md](WIND_SENSOR.md) |
| USB-to-RS485 adapter | Plugs into the Pi |
| 12 V DC power supply, 1 A or more | Powers the wind sensor only |
| Screw terminal strip, small flat screwdriver, multimeter | |
| 3 jumper wires (female-to-female) for the DHT22 | |
| Weatherproof box(es), cable glands, and Cat6 cable if the wind sensor sits far from the Pi | See WIND_SENSOR.md |
| A phone | For the ntfy app |

Accounts needed: GitHub (free), Render (about $7 a month for an always-on web service; a free plan exists but sleeps when idle), Supabase (free plan), UptimeRobot (optional, free), and the free ntfy app. See "What it costs" in the [README](../README.md).

---

## 1. The website and database

### 1.1 Get the code

1. Create a GitHub account if you do not have one.
2. Open the project page, <https://github.com/gittmaster/tritown-monitor>, and press **Fork** (this makes your own copy), or download the code and push it to a new repository of your own.

### 1.2 Create the database (Supabase)

Render's web host forgets files when it restarts, so readings live in a separate database.

1. Create a project at <https://supabase.com>. Choose a strong database password and save it somewhere safe.
2. In the project, press **Connect** and copy the **Session pooler** connection string. It looks like `postgresql://postgres.xxxx:[YOUR-PASSWORD]@aws-0-us-east-1.pooler.supabase.com:5432/postgres`. Put your password in place of `[YOUR-PASSWORD]`.
3. **Use the pooler, not the "Direct connection".** The direct address only works over IPv6 and Render cannot reach it; the symptom is the website failing to start with a "network is unreachable" error.

The website creates its own tables the first time it starts. You do not need to run any SQL.

### 1.3 Put the website on Render

1. Create an account at <https://render.com> and choose **New, Web Service**, then connect your GitHub repository.
2. Render reads `render.yaml`. If it asks, use: build command `pip install -r requirements.txt`, start command `gunicorn app:app`, branch `master`. Plan: the paid "Starter" instance (about $7 a month) keeps the site always on; the free plan also works but sleeps when idle.
3. Open **Environment** and add:

| Name | Value |
|---|---|
| `DATABASE_URL` | The Supabase pooler string from 1.2 |
| `API_KEY` | A long random secret you make up (this is the Pi's password; write it down) |
| `ALERT_METHOD` | `class_day` (the fire chief's method) or leave unset for the original rule |
| `HERBACEOUS_STAGE` | `transition`, `cured` or `green` |
| `RETENTION_DAYS` | Optional. Default 60 |

4. Press **Save, rebuild, and deploy**. Wait for the log to say the service is live.

**Check:** open your Render address (for example `https://your-name.onrender.com`). You should see the dashboard with no readings yet. Open `/api/stats` on the same address; it should show `total_readings: 0` and your `alert_method`.

On the free plan, the first request after it has slept takes up to a minute. That is normal and is why we add a keep-awake ping later. On a paid instance this does not happen.

### 1.4 Try it on your own computer first (optional)

See "Quick start" in the [README](../README.md). It needs no database and no Render.

---

## 2. The Raspberry Pi

### 2.1 Install the system

1. On your computer, install **Raspberry Pi Imager**. Choose **Raspberry Pi OS Lite (32-bit)** and your microSD card.
2. In the imager's settings (the gear or "Edit settings"), set: hostname `raspberrypi`, user name `pi` and **your own password**, your WiFi name and password, your country, and turn **SSH on**.
3. Write the card, put it in the Pi and power it up. Wait about two minutes.
4. Find the Pi on your network: from a command prompt try `ssh pi@raspberrypi.local`. If that name does not work (it often does not on Windows), look up the Pi's number in your router's list of devices (ours was `10.0.0.97`) and use that instead, for example with PuTTY.

**Check:** you can log in and see a prompt like `pi@raspberrypi:~ $`.

Then update it:

```bash
sudo apt update && sudo apt upgrade -y
```

### 2.2 Wire the DHT22

With the Pi powered **off**, connect the three pins:

| DHT22 pin | Pi pin |
|---|---|
| + (VCC) | Pin 1 (3.3 V) |
| OUT (data) | Pin 11 (GPIO 17) |
| - (GND) | Pin 9 (ground) |

Pin numbers count along the Pi's two rows of pins; pin 1 is the corner pin nearest the SD-card end. `pi_sender.py` reads GPIO 17 (`DHT_PIN = 17`). If you use a different pin, change that constant.

### 2.3 Install the libraries

```bash
sudo apt install -y python3-pip python3-dev libgpiod2
sudo pip3 install --break-system-packages -r requirements-pi.txt
```

Note: `Adafruit_DHT` is an older library. If it will not install on your Pi OS version, tell me; the code would need the newer `adafruit_dht` library, which is a small change in `pi_sender.py`.

(All the Pi's libraries are listed in `requirements-pi.txt`. After copying the repository files to the Pi you can instead run `bash setup_pi.sh`, which does 2.3, 2.5's copying and 2.7 in one go; you still edit the settings in `pi_sender.py` first and add the cron lines in 2.8.)

### 2.4 Wire and test the wind sensor

Follow [WIND_SENSOR.md](WIND_SENSOR.md): wiring, polarity check, and the `wind_probe.py` test. Come back here when the probe says `SENSOR ANSWERED`.

### 2.5 Copy the program files to the Pi

Copy these files from the repository into `/home/pi/` (WinSCP, `scp`, or `git clone` on the Pi):

```
pi_sender.py  wind_sensor.py  reading_queue.py  check_heartbeat.py  wind_probe.py  wifi_watchdog.sh
```

Example from a Windows PowerShell window in the project folder:

```
scp pi_sender.py wind_sensor.py reading_queue.py check_heartbeat.py wind_probe.py wifi_watchdog.sh pi@10.0.0.97:/home/pi/
```

Now open `pi_sender.py` on the Pi (`nano /home/pi/pi_sender.py`) and edit the settings at the top:

| Setting | Set it to |
|---|---|
| `DEVICE_ID` | A short name for this Pi, e.g. `pi-library` |
| `LOCATION` | The name shown on the dashboard, e.g. `Middleton Fire Station` |
| `SERVER_URL` | Your website address plus `/api/reading` |
| `API_KEY` | The same secret you put in Render |

Save (Ctrl+O, Enter) and exit (Ctrl+X). Do the same for `API` in `check_heartbeat.py` (your address plus `/api/stats`).

### 2.6 First run by hand

```bash
python3 /home/pi/pi_sender.py
```

Within about a minute you should see a line like `[OK] Sent: ...`. Press Ctrl+C to stop it. Open your dashboard: the card shows your first reading. If it says `Wind: no data`, check section 2.4.

### 2.7 Make it start by itself

Copy the service file and switch it on:

```bash
sudo cp pi-sender.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now pi-sender
sudo systemctl status pi-sender --no-pager
```

(If you copied only the Python files, create `pi-sender.service` from the repository first.) The status should say **active (running)**. The log is `/home/pi/sender.log`:

```bash
tail -n 20 /home/pi/sender.log
```

Run exactly **one** sender. Never also start it from cron or `rc.local`; two copies send every reading twice.

### 2.8 Schedules (cron)

```bash
crontab -e
```

Add these lines (replace the website address with yours):

```
# Keep a free Render plan awake (harmless on a paid plan)
*/3 * * * * curl -s https://YOUR-NAME.onrender.com/api/stats > /dev/null

# WiFi watchdog: reconnect, reboot if it cannot (script below)
*/5 * * * * /home/pi/wifi_watchdog.sh

# Heartbeat: phone alert if readings stop
*/15 * * * * /usr/bin/python3 /home/pi/check_heartbeat.py >> /home/pi/heartbeat.log 2>&1
```

`crontab.new` in the repository is a reference copy of the first two.

**WiFi watchdog script.** The Pi's WiFi can drop and stay down. `wifi_watchdog.sh` in the repository is the one we run: copy it to the Pi and make it runnable.

```bash
scp wifi_watchdog.sh pi@YOUR-PI:/home/pi/     # from your computer
chmod +x /home/pi/wifi_watchdog.sh            # on the Pi
```

It pings the internet; if that fails it restarts WiFi, and if that fails too it reboots the Pi. It logs to `/home/pi/wifi_watchdog.log`.

**Check:** wait 15 minutes, then `tail /home/pi/heartbeat.log`. It should show it checked and found data.

---

## 3. Phone alerts (ntfy)

1. Install the free **ntfy** app on your phone.
2. Choose a topic name nobody will guess, for example `yourtown-fire-monitor-8f3k2` (anyone who knows the name can read it; do not put private information in it).
3. In the app, subscribe to that topic.
4. In `check_heartbeat.py` and `outside_check.py`, set `NTFY_TOPIC` to your topic name (and on GitHub, the optional `NTFY_TOPIC` secret, see section 4).
5. Test it from any computer: `python -c "import requests; requests.post('https://ntfy.sh/YOUR-TOPIC', data='test alert')"` and confirm the phone buzzes.

The repository's topic belongs to the original owner. Replace it with your own, or the alerts will go to the wrong phone.

---

## 4. Backup watchdogs

### 4.1 Outside check (GitHub Actions)

`outside_check.py` runs every 30 minutes on GitHub's computers and warns you when the Pi has been silent for 45 minutes, even if the Pi has lost power.

1. Make sure `.github/workflows/outside-check.yml` is in your repository on the **default branch** (scheduled runs only start from there).
2. In GitHub: **Settings, Secrets and variables, Actions, New repository secret**, name `NTFY_TOPIC`, value your topic. (Optional; without it the code's built-in topic is used.)
3. Open the **Actions** tab, choose **Outside check**, press **Run workflow** to test it once.
4. Change the website address inside `outside_check.py` to yours.

### 4.2 UptimeRobot (optional)

Create a free account at <https://uptimerobot.com>, add an HTTP(s) monitor for your dashboard address with a 5-minute interval, and add your email or phone for alerts.

---

## 5. Final end-to-end check

| Step | You should see |
|---|---|
| `sudo systemctl status pi-sender` | active (running) |
| `tail -n 5 /home/pi/sender.log` | `[OK] Sent:` lines every 5 minutes |
| Dashboard | Temperature, humidity, wind, danger level; "last updated" less than 5 minutes ago |
| `/api/stats` | `wind_last_seen` is filled in, `alert_method` is what you chose |
| Spin the wind cups by hand and wait for the next reading | Wind speed rises on the dashboard |
| Unplug the wind sensor's adapter for 20 minutes | A phone alert and a dashboard warning; replug and a RESOLVED message follows |
| Run `python run_tests.py` on your computer | `All as expected.` |

Everything about what happens when something breaks is in [RELIABILITY.md](RELIABILITY.md). How the danger level is worked out is in [ALERTS.md](ALERTS.md).

---

## 6. Hardening before you call it finished

- Set your own `API_KEY` on Render and in `pi_sender.py`. Do not leave `tritown2024` anywhere that matters. Remove the value from `render.yaml` (or change it) so your real key is not in the repository.
- Change the Pi's password and keep SSH off the open internet (do not forward port 22 on your router).
- Keep a copy of the Pi's SD card image (Imager or `dd`) once everything works.
- Never commit `DATABASE_URL`, passwords or `.env` files.

## 7. Updating later

Follow "Installing an update" in the [README](../README.md): website first, then the Pi, then switch settings.
