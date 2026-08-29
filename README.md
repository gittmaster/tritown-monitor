# TriTown Environmental Fire Danger Monitor

A real-time environmental monitoring system for the TriTown community (Middleton, Topsfield \& Boxford, MA).

## 🌐 Live Dashboard

**https://tritown-monitor.onrender.com**

## 📋 Project Overview

This system monitors outdoor temperature and humidity using a Raspberry Pi sensor and displays a fire danger alert level for the TriTown community based on the **National Fire Danger Rating System (NFDRS)** — the same standard used by Essex County Fire Chiefs.

\---

## 🚨 Alert Levels (NFDRS)

|Level|Humidity|Temperature|Wind|Action|
|-|-|-|-|-|
|🟢 LOW|> 50%|Any|Any|Normal activities permitted|
|🟡 MODERATE|30-50%|> 60°F|Any|Caution advised for open flames|
|🟠 HIGH|< 30%|> 70°F|Any|No outdoor burning permitted|
|🔴 VERY HIGH|< 20%|> 80°F|Any|Emergency conditions — full ban|
|🚨 EXTREME|< 15%|> 85°F|> 25mph|Red Flag Warning — Call 911 if fire spotted!|

\---

## 🛠️ Hardware

* Raspberry Pi 3 Model B V1.2
* DHT22 Temperature \& Humidity Sensor
* Micro USB 5V 2.5A Power Supply
* SatelliteSale 9x9x4" Weatherproof Junction Box
* Jumper wires

## 💻 Tech Stack

* **Backend:** Python Flask
* **Database:** Neon.tech PostgreSQL (free forever)
* **Frontend:** HTML/CSS/JavaScript
* **Hosting:** Render.com
* **Sensors:** Raspberry Pi with DHT22

\---

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
cd C:\\Users\\\[username]\\Documents
mkdir PI\_Fire\_Monitor
cd PI\_Fire\_Monitor
git clone https://github.com/gittmaster/tritown-monitor.git
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
    @{level="VERY\_HIGH"; temp=28.0; humidity=18.0; wind=0;  label="VERY HIGH| 82F  18% hum"},
    @{level="EXTREME";   temp=30.0; humidity=14.0; wind=26; label="EXTREME  | 86F  14% hum 26mph"}
)

foreach ($test in $tests) {
    Invoke-WebRequest -Uri "$base/api/clear" -Method POST -Headers $headers -UseBasicParsing | Out-Null
    $body = "{""device\_id"":""test"",""location"":""TriTown Library"",""temperature"":" + $test.temp + ",""humidity"":" + $test.humidity + ",""wind\_speed"":" + $test.wind + "}"
    $response = Invoke-WebRequest -Uri "$base/api/reading" -Method POST -Headers $headers -Body $body -UseBasicParsing | Select-Object -ExpandProperty Content
    $expected = """alert\_level"":""" + $test.level + """"
    if ($response -match \[regex]::Escape($expected)) {
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
Set-Content ..\\test\_alerts.ps1 $script -Encoding UTF8
Write-Host "Test script saved to PI\_Fire\_Monitor folder!"
```

### Step 5 — Run the tests

```powershell
powershell -ExecutionPolicy Bypass -File ..\\test\_alerts.ps1
```

\---

## 🔄 Daily Workflow

### Push changes to GitHub

```powershell
cd C:\\Users\\\[username]\\Documents\\PI\_Fire\_Monitor\\tritown-monitor
git add .
git commit -m "Your change description"
git push origin master
```

### Run automated tests (always after pushing!)

```powershell
powershell -ExecutionPolicy Bypass -File ..\\test\_alerts.ps1
```

\---

## 🥧 Raspberry Pi Setup

### Check sensor is connected

```bash
sudo i2cdetect -y 1
# Should show 76 for BME280
```

### Check Pi is sending data

```bash
tail -f /home/pi/sender.log
```

### Restart Pi sender

```bash
pkill -f pi\_sender.py
python3 /home/pi/pi\_sender.py \&
```

### Pi sender auto-starts on boot via crontab

```bash
crontab -l
# Should show: @reboot /home/pi/start\_sender.sh
```

\---

## 🔑 API Endpoints

|Endpoint|Method|Description|
|-|-|-|
|`/api/reading`|POST|Send sensor reading (requires X-API-Key header)|
|`/api/latest`|GET|Get latest reading per location|
|`/api/history`|GET|Get last 100 readings|
|`/api/stats`|GET|Get total readings and locations|
|`/api/clear`|POST|Clear all readings (requires X-API-Key header)|

**API Key:** `tritown2024`

\---

## 📁 Project Structure

```
tritown-monitor/
├── app.py              # Flask backend + alert logic
├── requirements.txt    # Python dependencies
├── render.yaml         # Render deployment config
├── pi\_sender.py        # Raspberry Pi sensor script
├── static/
│   └── index.html      # Dashboard frontend
└── README.md           # This file
```

\---

## 🔗 Links

* **Live Dashboard:** https://tritown-monitor.onrender.com
* **GitHub:** https://github.com/gittmaster/tritown-monitor
* **PeerBridge:** https://github.com/gittmaster/peerbridge

\---

## 📦 Hardware Shopping List

* SatelliteSale 9x9x4" Weatherproof Junction Box (\~$32) — Amazon/Walmart
* Mini Hot Glue Gun with sticks (\~$9) — Amazon
* USB to RS485 Adapter (\~$15) — Amazon (for future wind sensor)
* XS-WSDS01-RS485 Wind Sensor (\~$39) — Amazon (Version 2)

\---

## 👤 Project By

Akhil Deshpande | 10th Grade Capstone Project | TriTown Community, Massachusetts

