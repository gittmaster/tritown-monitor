"""
Tests for weather_forecast.py using real API responses as fixtures
(captured 2026-09-26 for ZIP 01949 / Middleton, MA), so these run
fully offline - no live network call to Zippopotam or NWS needed.

Usage: python test_weather_forecast.py
"""
from unittest.mock import patch, Mock
from weather_forecast import zip_to_coords, coords_to_grid, zip_to_grid

ZIPPOPOTAM_RESPONSE = {
    "country": "United States",
    "country abbreviation": "US",
    "post code": "01949",
    "places": [{
        "place name": "Middleton",
        "longitude": "-71.013",
        "latitude": "42.5942",
        "state": "Massachusetts",
        "state abbreviation": "MA",
    }],
}

NWS_POINTS_RESPONSE = {
    "properties": {
        "gridId": "BOX",
        "gridX": 70,
        "gridY": 112,
        "forecast": "https://api.weather.gov/gridpoints/BOX/70,112/forecast",
        "forecastHourly": "https://api.weather.gov/gridpoints/BOX/70,112/forecast/hourly",
        "observationStations": "https://api.weather.gov/gridpoints/BOX/70,112/stations",
        "forecastGridData": "https://api.weather.gov/gridpoints/BOX/70,112",
        "fireWeatherZone": "https://api.weather.gov/zones/fire/MAZ006",
    }
}


def mock_response(json_data):
    resp = Mock()
    resp.json.return_value = json_data
    resp.raise_for_status.return_value = None
    return resp


passed = failed = 0


def check(label, condition):
    global passed, failed
    if condition:
        passed += 1
        print(f"[PASS] {label}")
    else:
        failed += 1
        print(f"[FAIL] {label}")


with patch("weather_forecast.requests.get") as mock_get:
    mock_get.return_value = mock_response(ZIPPOPOTAM_RESPONSE)
    lat, lon, name = zip_to_coords("01949")
    check("zip_to_coords returns correct latitude", lat == 42.5942)
    check("zip_to_coords returns correct longitude", lon == -71.013)
    check("zip_to_coords returns place name", name == "Middleton, MA")

with patch("weather_forecast.requests.get") as mock_get:
    mock_get.return_value = mock_response(NWS_POINTS_RESPONSE)
    grid = coords_to_grid(42.5942, -71.013)
    check("coords_to_grid returns gridId", grid["grid_id"] == "BOX")
    check("coords_to_grid returns gridX", grid["grid_x"] == 70)
    check("coords_to_grid returns gridY", grid["grid_y"] == 112)
    check("coords_to_grid returns forecast_url", grid["forecast_url"].endswith("/70,112/forecast"))
    check("coords_to_grid returns fire_weather_zone", grid["fire_weather_zone"] == "https://api.weather.gov/zones/fire/MAZ006")
check("coords_to_grid returns grid_data_url", grid["grid_data_url"] == "https://api.weather.gov/gridpoints/BOX/70,112")

with patch("weather_forecast.requests.get") as mock_get:
    mock_get.side_effect = [mock_response(ZIPPOPOTAM_RESPONSE), mock_response(NWS_POINTS_RESPONSE)]
    grid = zip_to_grid("01949")
    check("zip_to_grid chains both lookups (place_name)", grid["place_name"] == "Middleton, MA")
    check("zip_to_grid chains both lookups (grid_id)", grid["grid_id"] == "BOX")

print(f"\n{passed} passed, {failed} failed")

from weather_forecast import parse_wind_speed, parse_forecast_periods

# Trimmed real forecast response for Middleton, MA (BOX/70,112),
# captured 2026-09-26 - includes a single-value wind case and a
# range wind case ("13 to 16 mph") to check the parser handles both.
NWS_FORECAST_RESPONSE = {
    "properties": {
        "periods": [
            {
                "number": 1, "name": "This Afternoon",
                "startTime": "2026-09-26T12:00:00-04:00",
                "endTime": "2026-09-26T18:00:00-04:00",
                "isDaytime": True, "temperature": 59, "temperatureUnit": "F",
                "probabilityOfPrecipitation": {"unitCode": "wmoUnit:percent", "value": 100},
                "windSpeed": "20 mph", "windDirection": "NE",
                "icon": "https://api.weather.gov/icons/land/day/tsra,100?size=medium",
                "shortForecast": "Patchy Fog",
                "detailedForecast": "Rain showers and patchy fog before 2pm...",
            },
            {
                "number": 5, "name": "Monday",
                "startTime": "2026-09-28T06:00:00-04:00",
                "endTime": "2026-09-28T18:00:00-04:00",
                "isDaytime": True, "temperature": 61, "temperatureUnit": "F",
                "probabilityOfPrecipitation": {"unitCode": "wmoUnit:percent", "value": 100},
                "windSpeed": "13 to 16 mph", "windDirection": "NE",
                "icon": "https://api.weather.gov/icons/land/day/tsra,100/tsra,70?size=medium",
                "shortForecast": "Patchy Fog",
                "detailedForecast": "Patchy fog and showers and thunderstorms...",
            },
            {
                "number": 9, "name": "Wednesday",
                "startTime": "2026-09-30T06:00:00-04:00",
                "endTime": "2026-09-30T18:00:00-04:00",
                "isDaytime": True, "temperature": 72, "temperatureUnit": "F",
                "probabilityOfPrecipitation": {"unitCode": "wmoUnit:percent", "value": 1},
                "windSpeed": "2 mph", "windDirection": "SW",
                "icon": "https://api.weather.gov/icons/land/day/bkn?size=medium",
                "shortForecast": "Partly Sunny",
                "detailedForecast": "Partly sunny, with a high near 72...",
            },
        ]
    }
}

check("parse_wind_speed handles plain value", parse_wind_speed("20 mph") == 20.0)
check("parse_wind_speed handles range (takes higher end)", parse_wind_speed("13 to 16 mph") == 16.0)
check("parse_wind_speed handles missing value", parse_wind_speed(None) is None)
check("parse_wind_speed handles empty string", parse_wind_speed("") is None)

periods = parse_forecast_periods(NWS_FORECAST_RESPONSE)
check("parse_forecast_periods returns all periods", len(periods) == 3)
check("parse_forecast_periods keeps temperature", periods[0]["temperature_f"] == 59)
check("parse_forecast_periods parses range wind to upper bound", periods[1]["wind_speed_mph"] == 16.0)
check("parse_forecast_periods keeps raw wind string too", periods[1]["wind_speed_raw"] == "13 to 16 mph")
check("parse_forecast_periods keeps precip chance", periods[0]["precip_chance_pct"] == 100)
check("parse_forecast_periods keeps short forecast text", periods[2]["short_forecast"] == "Partly Sunny")

print(f"\n{passed} passed, {failed} failed")

from weather_forecast import (
    parse_iso_duration, parse_valid_time, sample_series,
    kmh_to_mph, build_hourly_projection,
)
from datetime import datetime, timedelta

check("parse_iso_duration handles hours", parse_iso_duration("PT2H") == timedelta(hours=2))
check("parse_iso_duration handles days", parse_iso_duration("P1D") == timedelta(days=1))
check("parse_iso_duration handles minutes", parse_iso_duration("PT30M") == timedelta(minutes=30))

start, end = parse_valid_time("2026-09-26T13:00:00+00:00/PT1H")
check("parse_valid_time returns correct start", start == datetime.fromisoformat("2026-09-26T13:00:00+00:00"))
check("parse_valid_time returns correct end", end == datetime.fromisoformat("2026-09-26T14:00:00+00:00"))

check("kmh_to_mph converts correctly", abs(kmh_to_mph(24.076) - 14.96) < 0.01)
check("kmh_to_mph handles None", kmh_to_mph(None) is None)

# Real (trimmed) series from the actual BOX/70,112 gridpoint response,
# captured 2026-09-26. Deliberately misaligned time boundaries across
# the three series, to prove sampling finds the right bucket in each.
TEMP_VALUES = [
    {"validTime": "2026-09-26T10:00:00+00:00/PT2H", "value": 15},
    {"validTime": "2026-09-26T12:00:00+00:00/PT1H", "value": 14.444444444444445},
    {"validTime": "2026-09-26T13:00:00+00:00/PT1H", "value": 13.88888888888889},
    {"validTime": "2026-09-26T14:00:00+00:00/PT2H", "value": 14.444444444444445},
    {"validTime": "2026-09-26T16:00:00+00:00/PT1H", "value": 13.88888888888889},
]
HUMIDITY_VALUES = [
    {"validTime": "2026-09-26T10:00:00+00:00/PT2H", "value": 78},
    {"validTime": "2026-09-26T12:00:00+00:00/PT1H", "value": 77},
    {"validTime": "2026-09-26T13:00:00+00:00/PT1H", "value": 83},
    {"validTime": "2026-09-26T14:00:00+00:00/PT2H", "value": 80},
    {"validTime": "2026-09-26T16:00:00+00:00/PT1H", "value": 86},
]
WIND_VALUES = [
    {"validTime": "2026-09-26T10:00:00+00:00/PT3H", "value": 24.076},
    {"validTime": "2026-09-26T13:00:00+00:00/PT1H", "value": 27.78},
    {"validTime": "2026-09-26T14:00:00+00:00/PT1H", "value": 29.632},
    {"validTime": "2026-09-26T15:00:00+00:00/PT5H", "value": 31.484},
]

# Sample at 13:00 exactly (a boundary shared by all three series)
t = datetime.fromisoformat("2026-09-26T13:00:00+00:00")
check("sample_series finds temp at exact boundary", sample_series(TEMP_VALUES, t) == 13.88888888888889)
check("sample_series finds humidity at exact boundary", sample_series(HUMIDITY_VALUES, t) == 83)
check("sample_series finds wind at exact boundary", sample_series(WIND_VALUES, t) == 27.78)

# Sample at 14:30 - not aligned to any series' boundary, and each series
# is mid-interval at a DIFFERENT point (temp/humidity mid a 2hr block
# starting 14:00, wind mid a 1hr block starting 14:00) - real-world case.
t2 = datetime.fromisoformat("2026-09-26T14:30:00+00:00")
check("sample_series handles misaligned time (temp)", sample_series(TEMP_VALUES, t2) == 14.444444444444445)
check("sample_series handles misaligned time (humidity)", sample_series(HUMIDITY_VALUES, t2) == 80)
check("sample_series handles misaligned time (wind)", sample_series(WIND_VALUES, t2) == 29.632)

# Sample outside all known ranges
t3 = datetime.fromisoformat("2026-09-30T00:00:00+00:00")
check("sample_series returns None past known data", sample_series(TEMP_VALUES, t3) is None)

GRID_DATA_FIXTURE = {
    "properties": {
        "temperature": {"uom": "wmoUnit:degC", "values": TEMP_VALUES},
        "relativeHumidity": {"uom": "wmoUnit:percent", "values": HUMIDITY_VALUES},
        "windSpeed": {"uom": "wmoUnit:km_h-1", "values": WIND_VALUES},
    }
}
projection = build_hourly_projection(GRID_DATA_FIXTURE, hours=6)
check("build_hourly_projection produces hourly entries", len(projection) == 6)
check("build_hourly_projection starts at first data point", projection[0]["time"].startswith("2026-09-26T10:00:00"))
check("build_hourly_projection converts temp C to F correctly", projection[0]["temperature_f"] == round(15 * 9/5 + 32, 1))
check("build_hourly_projection keeps humidity as-is", projection[0]["humidity_pct"] == 78)
check("build_hourly_projection converts wind km/h to mph", abs(projection[0]["wind_speed_mph"] - 14.96) < 0.05)

print(f"\n{passed} passed, {failed} failed")

from weather_forecast import get_hourly_projection

with patch("weather_forecast.requests.get") as mock_get:
    mock_get.side_effect = [
        mock_response(ZIPPOPOTAM_RESPONSE),
        mock_response(NWS_POINTS_RESPONSE),
        mock_response(GRID_DATA_FIXTURE),
    ]
    result = get_hourly_projection("01949", hours=6)
    check("get_hourly_projection returns place_name", result["place_name"] == "Middleton, MA")
    check("get_hourly_projection returns hourly data", len(result["hours"]) == 6)
    check("get_hourly_projection hourly data has real values", result["hours"][0]["temperature_f"] == round(15 * 9/5 + 32, 1))

print(f"\n{passed} passed, {failed} failed")
