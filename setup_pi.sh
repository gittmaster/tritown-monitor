#!/bin/bash
# One-step setup for a NEW Raspberry Pi (run from the folder holding the repo files).
# Installs the libraries, copies the files to /home/pi and starts the sender service.
# It does NOT touch your schedule (cron); add those lines by hand, see docs/BUILD_FROM_SCRATCH.md.
# Before running: edit DEVICE_ID, LOCATION, SERVER_URL and API_KEY at the top of pi_sender.py.
set -e
cd "$(dirname "$0")"

sudo apt update
sudo apt install -y python3-pip python3-dev libgpiod2
sudo pip3 install --break-system-packages -r requirements-pi.txt

cp pi_sender.py wind_sensor.py reading_queue.py check_heartbeat.py wind_probe.py wifi_watchdog.sh /home/pi/
chmod +x /home/pi/wifi_watchdog.sh

sudo cp pi-sender.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now pi-sender
sleep 3
sudo systemctl status pi-sender --no-pager || true

echo
echo "Next: add the cron lines (docs/BUILD_FROM_SCRATCH.md section 2.8) and check:"
echo "  tail -n 20 /home/pi/sender.log"
