# TriTown Environmental Fire Danger Monitor

A real-time environmental monitoring system for the TriTown community (Middleton, Topsfield & Boxford, MA).

## 🌐 Live Dashboard
**https://tritown-monitor.onrender.com**

## 📋 Project Overview
This system monitors outdoor temperature and humidity using a Raspberry Pi sensor and displays a fire danger alert level for the TriTown community based on the **National Fire Danger Rating System (NFDRS)** — the same standard used by Essex County Fire Chiefs.

---

## 🚨 Alert Levels (NFDRS)

| Level | Humidity | Temperature | Wind | Action |
|---|---|---|---|---|
| 🟢 LOW | > 50% | Any | Any | Normal activities permitted |
| 🟡 MODERATE | 30-50% | > 60°F | Any | Caution advised for open flames |
| 🟠 HIGH | < 30% | > 70°F | Any | No outdoor burning permitted |
| 🔴 VERY HIGH | < 20% | > 80°F | Any | Emergency conditions — full ban |
| 🚨 EXTREME | < 15% | > 85°F | > 25mph | Red Flag Warning — Call 911 if fire spotted! |

---

## 🛠️ Hardware
- Raspberry Pi 3 Model B V1.2
- DHT22 Temperature & Humidity Sensor
- Micro USB 5V 2.5A Power Supply
- SatelliteSale 9x9x4" Weatherproof Junction Box (installed outside)
- Jumper wires secured with hot glue

## 💻 Tech Stack
- **Backend:** Python Flask
- **Database:** Neon.tech PostgreSQL (free forever — no expiry, no paid dependencies)
- **Frontend:** HTML/CSS/JavaScript
- **Hosting:** Render.com
- **Uptime Monitoring:** UptimeRobot (free — pings every 5 minutes)
- **Sensors:** Raspberry Pi with DHT22

---

## 📍 Current Installation
- **Location:** Middleton Fire Station, Middleton MA
- **Status:** Live and sending data every 5 minutes
- **Box:** SatelliteSale 9x9x4" weatherproof junction box mounted outside in shade

---

## 🛡️ Resilience Features

| Feature | Description |
|---|---|
| **Auto-boot** | systemd starts the sender on every reboot, after the network is up |
| **Crash restart** | systemd `Restart=always` — relaunches the sender 10s after any exit |
| **Error capture** | stdout *and* stderr both land in `sender.log` — tracebacks are no longer lost |
| **WiFi Watchdog** | Checks WiFi every 5 minutes — reconnects if dropped |
| **Render Keepalive** | Pi pings Render every 3 minutes to prevent spin-down |
| **UptimeRobot** | External monitoring pings Render every 5 minutes |
| **Retry Logic** | Sender retries failed requests 3 times before giving up |
| **Timestamped Logs** | All logs include date/time for easy debugging |
| **Log Rotation** | Logs rotate daily, keep 7 days, compressed automatically |
| **Neon Database** | Data persists permanently — never lost on Render restart |

---

## 🚀 Setting Up on a New Laptop

### Step 1 — Install Git
Download and install from: https://git-scm.com

### Step 2 — Configure Git
```powershell
git config --global user.name "gittmaster"
git config --global user.email "your@email.com"
```

### Step 3 — Clone the repo
```powershell
cd C:\Users\[username]\Documents
mkdir PI_Fire_Monitor
cd PI_Fire_Monitor
git clone -b master https://github.com/gittmaster/tritown-monitor.git
cd tritown-monitor
```

### Step 4 — Create the automated test script
```powershell
$script = @'
Write-Host "======================================" -ForegroundColor Cyan
Write-Host "  TriTown NFDRS Alert Level Tests" -ForegroundColor Cyan
Write-Host "======================================" -ForegroundColor Cyan

$base = "https://tritown-monitor.onrender.com"
$headers = @{"Content-Type"="application/json"; "X-API-Key"="tritown2024"}
$passed = 0
$failed = 0

$tests = @(
    @{level="LOW";       temp=10.0; humidity=70.0; wind=0;  label="LOW      | 50F  70% hum"},
    @{level="MODERATE";  temp=18.0; humidity=45.0; wind=0;  label="MODERATE | 64F  45% hum"},
    @{level="HIGH";      temp=23.0; humidity=28.0; wind=0;  label="HIGH     | 73F  28% hum"},
    @{level="VERY_HIGH"; temp=28.0; humidity=18.0; wind=0;  label="VERY HIGH| 82F  18% hum"},
    @{level="EXTREME";   temp=30.0; humidity=14.0; wind=26; label="EXTREME  | 86F  14% hum 26mph"}
)

foreach ($test in $tests) {
    Invoke-WebRequest -Uri "$base/api/clear" -Method POST -Headers $headers -UseBasicParsing | Out-Null
    $body = "{""device_id"":""test"",""location"":""TriTown Library"",""temperature"":" + $test.temp + ",""humidity"":" + $test.humidity + ",""wind_speed"":" + $test.wind + "}"
    $response = Invoke-WebRequest -Uri "$base/api/reading" -Method POST -Headers $headers -Body $body -UseBasicParsing | Select-Object -ExpandProperty Content
    $expected = """alert_level"":""" + $test.level + """"
    if ($response -match [regex]::Escape($expected)) {
        Write-Host "PASS - $($test.label)" -ForegroundColor Green
        $passed++
    } else {
        Write-Host "FAIL - $($test.label)" -ForegroundColor Red
        Write-Host "       Got: $response" -ForegroundColor Yellow
        $failed++
    }
    Start-Sleep -Seconds 15
}

Write-Host ""
Write-Host "Results: $passed PASSED  $failed FAILED" -ForegroundColor Cyan
Invoke-WebRequest -Uri "$base/api/clear" -Method POST -Headers $headers -UseBasicParsing | Out-Null
Write-Host "Test data cleared!" -ForegroundColor Yellow
'@
Set-Content ..\test_alerts.ps1 $script -Encoding UTF8
Write-Host "Test script saved to PI_Fire_Monitor folder!"
```

### Step 5 — Run the tests
```powershell
powershell -ExecutionPolicy Bypass -File ..\test_alerts.ps1
```

---

## 🔄 Daily Workflow

### Push changes to GitHub
```powershell
cd C:\Users\[username]\Documents\PI_Fire_Monitor\tritown-monitor
git add .
git commit -m "Your change description"
git push origin master
```

### Always run automated tests after pushing!
```powershell
powershell -ExecutionPolicy Bypass -File ..\test_alerts.ps1
```

---

## 🥧 Raspberry Pi Commands

### Check Pi is sending data
```bash
tail -f /home/pi/sender.log
```

### Check Pi crontab (all resilience tasks)
```bash
crontab -l
```

### Restart Pi sender manually
```bash
sudo systemctl restart pi-sender
sudo systemctl status pi-sender
```

### Check the sender service
```bash
sudo systemctl status pi-sender          # is it running?
journalctl -u pi-sender -n 50            # service events / restart history
pgrep -af pi_sender.py                   # confirm exactly ONE sender
```

### Check WiFi watchdog log
```bash
cat /home/pi/wifi_watchdog.log
```

### Check sensor is connected
```bash
sudo i2cdetect -y 1
```

---

## 🔑 API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/api/reading` | POST | Send sensor reading (requires X-API-Key header) |
| `/api/latest` | GET | Get latest reading per location |
| `/api/history` | GET | Get last 100 readings |
| `/api/stats` | GET | Get total readings and locations |
| `/api/clear` | POST | Clear all readings (requires X-API-Key header) |

**API Key:** `tritown2024`

---

## 📁 Project Structure
```
tritown-monitor/
├── app.py                                  # Flask backend + alert logic
├── requirements.txt                        # Python dependencies
├── render.yaml                             # Render deployment config
├── pi_sender.py                            # Raspberry Pi sensor script
├── pi-sender.service                       # systemd unit for the Pi sender
├── crontab.new                             # Pi crontab (keepalive + wifi watchdog)
├── README.md                               # This file
├── FireMarshall_TriTown_Presentation.pptx  # Fire Marshall presentation
└── static/
    └── index.html                          # Dashboard frontend
```

---

## 📦 Hardware Shopping List
- ✅ SatelliteSale 9x9x4" Weatherproof Junction Box (~$32) — installed
- ✅ Mini Hot Glue Gun with sticks (~$9) — used to secure wires
- ✅ USB to RS485 Adapter (~$15) — for future wind sensor
- 🔲 XS-WSDS01-RS485 Wind Sensor (~$39) — Version 2

---

## 🔗 Links
- **Live Dashboard:** https://tritown-monitor.onrender.com
- **GitHub:** https://github.com/gittmaster/tritown-monitor
- **PeerBridge:** https://github.com/gittmaster/peerbridge
- **Essex County Fire:** https://essexcountyfire.org/fire-prevention/
- **UptimeRobot:** https://uptimerobot.com

---

## ⚙️ Running the Sender (systemd)

`pi_sender.py` runs on the Pi as a **systemd service**, not from cron.

File: `/etc/systemd/system/pi-sender.service`

```ini
[Unit]
Description=TriTown Pi Sender
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi
ExecStart=/usr/bin/python3 /home/pi/pi_sender.py
Restart=always
RestartSec=10
StandardOutput=append:/home/pi/sender.log
StandardError=append:/home/pi/sender.log

[Install]
WantedBy=multi-user.target
```

Install:

```bash
sudo systemctl daemon-reload
sudo systemctl enable pi-sender
sudo systemctl start pi-sender
```

### Crontab (sender removed)

Cron no longer starts or watches the sender. Only two jobs remain:

```cron
*/3 * * * * curl -s https://tritown-monitor.onrender.com/api/stats > /dev/null
*/5 * * * * /home/pi/wifi_watchdog.sh
```

Backup of the previous crontab: `/home/pi/crontab.backup.txt`

---

## 🐛 Incident: sender stopped overnight (Sep 10, 2026)

**Symptom.** Dashboard froze at 03:49 AM. Recurring over several weeks.

**Original (wrong) diagnosis.** Assumed WiFi was dropping overnight.

**Actual cause of the sender staying dead.** The cron watchdog was:

```cron
* * * * * pgrep -f pi_sender.py > /dev/null || python3 /home/pi/pi_sender.py &
```

`pgrep -f` matches against the full command line of every process — including the
cron shell running that very command, whose command line contains the text
`pi_sender.py`. So `pgrep` always found a match (itself), always exited 0, and the
`||` restart never fired. **The watchdog never worked, not once.**

A second bug in the same line: no `2>&1` redirect, so Python tracebacks went to
stderr and were discarded. The log showed clean `[OK]` lines followed by silence
with no error — which is why the real cause stayed invisible.

**Fix.** Migrated to systemd (above). `Restart=always` actually restarts on crash,
`After=network-online.target` fixes the boot race, and stderr is now captured.

**Lesson.** `pgrep -f <pattern>` matching its own invocation is a classic trap, and
it fails in the worst direction — silently reporting health while doing nothing.
Test any monitor by actually killing the thing it is supposed to watch.

### ⚠️ STILL OPEN: why did it die at 03:49?

systemd now restarts the sender, but **the underlying cause is undiagnosed.**
Automatic recovery is not the same as a fix.

Suspects:

1. **OOM kill** — 1GB RAM on a Pi 3 running a long-lived Python process.
2. **Under-voltage brownout** — the Pi now lives outdoors in a junction box, possibly
   on a different power run than when it was on the bench. A brownout stops the
   process with no clean crash and no log entry, which matches the symptom exactly.
3. **Process hang** — blocked on an HTTP call with no timeout.

Diagnostics to run the morning after any stop:

```bash
uptime
dmesg | grep -i -E "killed process|out of memory|Under-voltage"
journalctl -u pi-sender | grep -iE "Started|Stopped|Main process"
```

- `uptime` under a few hours → the Pi rebooted; boot-order or power problem.
- OOM lines in `dmesg` → memory leak in the sender.
- Under-voltage lines → power supply or cable run.
- Uptime in days with no `dmesg` hits → process hang; fix is an HTTP timeout plus
  systemd `WatchdogSec`, which kills on *silence* rather than only on crash.

### Also open

- **No local buffering.** When a POST fails, that reading is lost permanently. The
  Sep 10 outage cost roughly 64 readings (03:49–09:12). Fix: write each reading to a
  local queue file first, POST it, delete on success, and flush the backlog when the
  connection returns — turning an outage into a delayed upload instead of a hole in
  the dataset.
- **BME280 removed** after intermittent connection failures. Second unit untested.
- **Wind sensors not ordered** (XS-WSDS01-RS485) — requested by the Fire Marshall.

---

## 👤 Project By
Akhil Deshpande | 10th Grade Capstone Project | TriTown Community, Massachusetts