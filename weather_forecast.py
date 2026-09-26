"""
National Weather Service forecast lookup, by ZIP code.

NWS's API only accepts lat/lon, not ZIP codes, so this chains two lookups:
  1. ZIP code -> lat/lon           (Zippopotam.us, free, no API key)
  2. lat/lon  -> NWS grid/forecast (api.weather.gov, free, no API key)

Both external services are free and require no signup, but NWS asks that
every request set a real User-Agent identifying the app (not a browser
string) - see https://www.weather.gov/documentation/services-web-api
"""
import requests

USER_AGENT = "TriTownFireMonitor/1.0 (contact: reachapld@gmail.com)"
HEADERS = {"User-Agent": USER_AGENT, "Accept": "application/geo+json"}


def zip_to_coords(zip_code):
    """ZIP code -> (latitude, longitude, place_name) via Zippopotam.us."""
    resp = requests.get(f"https://api.zippopotam.us/us/{zip_code}", timeout=10)
    resp.raise_for_status()
    data = resp.json()
    place = data["places"][0]
    lat = float(place["latitude"])
    lon = float(place["longitude"])
    name = f'{place["place name"]}, {place["state abbreviation"]}'
    return lat, lon, name


def coords_to_grid(lat, lon):
    """lat/lon -> NWS grid info (office, gridX, gridY, forecast URLs)."""
    resp = requests.get(
        f"https://api.weather.gov/points/{lat},{lon}",
        headers=HEADERS, timeout=10,
    )
    resp.raise_for_status()
    props = resp.json()["properties"]
    return {
        "grid_id": props["gridId"],
        "grid_x": props["gridX"],
        "grid_y": props["gridY"],
        "forecast_url": props["forecast"],
        "forecast_hourly_url": props["forecastHourly"],
        "observation_stations_url": props["observationStations"],
        "grid_data_url": props["forecastGridData"],
        "fire_weather_zone": props.get("fireWeatherZone"),
    }


def zip_to_grid(zip_code):
    """Convenience: ZIP code straight to NWS grid info, in one call."""
    lat, lon, place_name = zip_to_coords(zip_code)
    grid = coords_to_grid(lat, lon)
    grid["place_name"] = place_name
    grid["latitude"] = lat
    grid["longitude"] = lon
    return grid


import re


def parse_wind_speed(wind_speed_str):
    """
    NWS wind speed strings look like "20 mph" or "13 to 16 mph" (a range).
    For fire-danger purposes we take the higher number - the worse-case
    wind is what matters for fire spread risk, not the average.
    Returns wind speed in mph as a float, or None if unparseable.
    """
    if not wind_speed_str:
        return None
    numbers = re.findall(r"\d+", wind_speed_str)
    if not numbers:
        return None
    return float(numbers[-1])


def parse_forecast_periods(forecast_json):
    """Turn a raw NWS /forecast response into a clean list of periods."""
    periods = []
    for p in forecast_json["properties"]["periods"]:
        precip = p.get("probabilityOfPrecipitation") or {}
        periods.append({
            "name": p["name"],
            "start_time": p["startTime"],
            "end_time": p["endTime"],
            "is_daytime": p["isDaytime"],
            "temperature_f": p["temperature"],
            "wind_speed_mph": parse_wind_speed(p.get("windSpeed")),
            "wind_speed_raw": p.get("windSpeed"),
            "wind_direction": p.get("windDirection"),
            "precip_chance_pct": precip.get("value"),
            "short_forecast": p.get("shortForecast"),
            "detailed_forecast": p.get("detailedForecast"),
            "icon": p.get("icon"),
        })
    return periods


def get_forecast(zip_code):
    """ZIP code -> place name + list of parsed forecast periods (~7 days)."""
    grid = zip_to_grid(zip_code)
    resp = requests.get(grid["forecast_url"], headers=HEADERS, timeout=10)
    resp.raise_for_status()
    periods = parse_forecast_periods(resp.json())
    return {"place_name": grid["place_name"], "periods": periods}


from datetime import datetime, timedelta


def parse_iso_duration(duration_str):
    """
    Parse a simple ISO 8601 duration (e.g. 'PT2H', 'P1D', 'PT30M') into a
    timedelta. NWS grid data only ever uses day/hour/minute/second parts.
    """
    match = re.match(
        r"^P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?)?$", duration_str
    )
    if not match:
        raise ValueError(f"Unrecognized duration format: {duration_str}")
    days, hours, minutes, seconds = (int(g) if g else 0 for g in match.groups())
    return timedelta(days=days, hours=hours, minutes=minutes, seconds=seconds)


def parse_valid_time(valid_time_str):
    """
    NWS grid data times look like '2026-09-26T10:00:00+00:00/PT2H': a start
    time and a duration joined by '/'. Returns (start, end) datetimes.
    """
    start_str, duration_str = valid_time_str.split("/")
    start = datetime.fromisoformat(start_str)
    duration = parse_iso_duration(duration_str)
    return start, start + duration


def sample_series(values, target_time):
    """
    Given a list of {'validTime': ..., 'value': ...} entries, return the
    value whose time interval contains target_time, or None if none match.
    """
    for entry in values:
        start, end = parse_valid_time(entry["validTime"])
        if start <= target_time < end:
            return entry["value"]
    return None


def kmh_to_mph(kmh):
    return kmh * 0.621371 if kmh is not None else None


def build_hourly_projection(grid_data_json, hours=72):
    """
    Combine temperature, humidity, and wind speed time series from a raw
    NWS gridpoint (/gridpoints/{office}/{x},{y}) response into a single
    hour-by-hour list of readings, starting from the first available data
    point. Deliberately does NOT compute a fire-danger alert level here -
    that's the caller's job (see get_alert() in app.py) - so this module
    stays focused purely on fetching and parsing NWS data.
    """
    props = grid_data_json["properties"]
    temp_values = props["temperature"]["values"]
    humidity_values = props["relativeHumidity"]["values"]
    wind_values = props["windSpeed"]["values"]

    start_time, _ = parse_valid_time(temp_values[0]["validTime"])
    start_time = start_time.replace(minute=0, second=0, microsecond=0)

    projection = []
    for i in range(hours):
        t = start_time + timedelta(hours=i)
        temp_c = sample_series(temp_values, t)
        humidity = sample_series(humidity_values, t)
        wind_kmh = sample_series(wind_values, t)

        if temp_c is None or humidity is None:
            continue  # no data available for this hour - skip rather than guess

        wind_mph = kmh_to_mph(wind_kmh)
        projection.append({
            "time": t.isoformat(),
            "temperature_c": round(temp_c, 1),
            "temperature_f": round(temp_c * 9 / 5 + 32, 1),
            "humidity_pct": humidity,
            "wind_speed_mph": round(wind_mph, 1) if wind_mph is not None else None,
        })
    return projection


def get_hourly_projection(zip_code, hours=72):
    """
    ZIP code -> place name + hour-by-hour list of temperature/humidity/wind
    readings for the next `hours` hours (default 72 = 3 days). Does not
    compute a fire-danger alert level - see get_alert() in app.py for that.
    """
    grid = zip_to_grid(zip_code)
    resp = requests.get(grid["grid_data_url"], headers=HEADERS, timeout=10)
    resp.raise_for_status()
    return {
        "place_name": grid["place_name"],
        "hours": build_hourly_projection(resp.json(), hours=hours),
    }
