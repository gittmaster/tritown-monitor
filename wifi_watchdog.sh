#!/bin/bash
# WiFi watchdog (runs from cron every 5 minutes; see crontab.new).
# If the internet is unreachable, restart WiFi; if still unreachable, reboot.
if ! ping -c 2 -W 3 8.8.8.8 > /dev/null 2>&1; then
    echo "$(date): WiFi down, reconnecting..." >> /home/pi/wifi_watchdog.log
    sudo ip link set wlan0 down
    sleep 5
    sudo ip link set wlan0 up
    sleep 15
    if ping -c 2 -W 3 8.8.8.8 > /dev/null 2>&1; then
        echo "$(date): WiFi reconnected successfully" >> /home/pi/wifi_watchdog.log
    else
        echo "$(date): WiFi reconnect failed - rebooting" >> /home/pi/wifi_watchdog.log
        sudo reboot
    fi
fi
