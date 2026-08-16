# TriTown Environmental Monitor

A community environmental monitoring system for Middleton, Topsfield and Boxford MA.

## Live Dashboard
https://tritown-monitor.onrender.com

## What It Does
Monitors outdoor temperature and humidity using Raspberry Pi sensors and displays
a fire danger alert level for the TriTown community.

## Alert Levels
- LOW - Good air quality. Safe conditions today.
- MODERATE - Drying conditions developing. Avoid burning outdoors.
- HIGH - Hot and dry conditions. Stop all outdoor burning now!
- VERY HIGH - Extremely hot and dry! No burning, call 911 if fire spotted!

## Hardware
- Raspberry Pi 3 Model B V1.2
- DHT22 Temperature and Humidity Sensor
- BME280 Barometric Pressure Sensor

## Tech Stack
- Backend: Python Flask
- Database: PostgreSQL (Render)
- Frontend: HTML/CSS/JavaScript
- Hosting: Render.com
- Sensors: Raspberry Pi with DHT22 and BME280

## Setup
1. Install dependencies: pip install -r requirements.txt
2. Set environment variables: DATABASE_URL, API_KEY
3. Run: gunicorn app:app

## Project by
Akhil - 10th Grade Capstone Project
TriTown Community, Massachusetts
