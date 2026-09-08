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
| **Auto-boot** | Pi sender starts automatically on every reboot |
| **Watchdog** | Checks every minute if sender is running — restarts if crashed |
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
pkill -f pi_sender.py
python3 /home/pi/pi_sender.py &
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

## 👤 Project By
Akhil Deshpande | 10th Grade Capstone Project | TriTown Community, Massachusetts
