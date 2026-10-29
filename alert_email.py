"""Email people when the fire danger reaches HIGH (or worse) during the spring season.

Rules (all easy to change with settings on the website host):
  * Only from January 1 to May 31 (Massachusetts time).
  * Only when a station's level RISES to HIGH, VERY HIGH or EXTREME. It does not
    repeat on every 5-minute reading.
  * At most one email per station every COOLDOWN_HOURS (default 6), so a level
    that flickers up and down around the line does not flood anyone's inbox.
  * Never for old readings that a Pi resends after an outage.

Settings (set on the website host, never in the code or on GitHub):
  ALERT_EMAIL_TO        who gets it: one or more addresses separated by commas
  SMTP_USER             the sending account (for Gmail: the full address)
  SMTP_PASSWORD         that account's app password
  SMTP_HOST / SMTP_PORT default smtp.gmail.com / 587
  ALERT_EMAIL_FROM      optional "from" address (defaults to SMTP_USER)
  ALERT_SEASON_MONTHS   optional, default "1-5" (January to May)
  ALERT_COOLDOWN_HOURS  optional, default 6
  DASHBOARD_URL         optional, default the TriTown dashboard

If ALERT_EMAIL_TO or the sending account is not set, nothing is sent and
nothing else changes.
"""
import os
import smtplib
import ssl
from datetime import datetime, timedelta
from email.message import EmailMessage

DASHBOARD_URL_DEFAULT = "https://tritown-monitor.onrender.com"

LEVEL_ORDER = ["LOW", "MODERATE", "HIGH", "VERY_HIGH", "EXTREME"]
LEVEL_WORDS = {"LOW": "Low", "MODERATE": "Moderate", "HIGH": "High",
               "VERY_HIGH": "Very High", "EXTREME": "Extreme"}
WHAT_IT_MEANS = {
    "HIGH": "Fires can start easily and be hard to control in the wind. Outdoor burning is strongly discouraged.",
    "VERY_HIGH": "Fires start easily and can spread faster than crews can respond. No outdoor burning.",
    "EXTREME": "Fires start and spread very quickly. No outdoor burning at all.",
}
COMPASS = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
           "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]


def level_rank(level):
    try:
        return LEVEL_ORDER.index(level)
    except ValueError:
        return -1


def parse_months(raw, default=(1, 5)):
    """'1-5' means January to May. Anything unreadable falls back to the default."""
    try:
        first, last = str(raw).split("-")
        first, last = int(first), int(last)
        if 1 <= first <= last <= 12:
            return first, last
    except (ValueError, AttributeError):
        pass
    return default


def local_now():
    """The current time in Massachusetts (so January 1 starts at local midnight)."""
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("America/New_York"))
    except Exception:
        return datetime.utcnow() - timedelta(hours=5)


def in_season(when, months=(1, 5)):
    return months[0] <= when.month <= months[1]


def should_send(prev_level, new_level, last_sent_utc, now_utc, local_when,
                reading_age_minutes=0, months=(1, 5), cooldown_hours=6):
    """Decide if this reading should trigger an email. Pure function, easy to test."""
    if level_rank(new_level) < level_rank("HIGH"):
        return False
    if not in_season(local_when, months):
        return False
    if reading_age_minutes > 30:          # an old reading resent after an outage
        return False
    if level_rank(prev_level) >= level_rank("HIGH"):
        return False                      # it was already that high; no new news
    if last_sent_utc is not None and now_utc - last_sent_utc < timedelta(hours=cooldown_hours):
        return False
    return True


def build_message(location, level, temp_c, humidity, wind_mph, wind_deg,
                  sender, recipients, dashboard_url=DASHBOARD_URL_DEFAULT, when_text=""):
    """Plain-language email. No jargon."""
    word = LEVEL_WORDS.get(level, level.title())
    temp_f = temp_c * 9 / 5 + 32 if temp_c is not None else None
    lines = ["The fire danger at %s has reached %s." % (location, word.upper()), ""]
    lines.append("What it means: %s" % WHAT_IT_MEANS.get(level, ""))
    lines.append("")
    lines.append("Right now at %s:" % location)
    if temp_f is not None:
        lines.append("  Temperature: %.0f F" % temp_f)
    if humidity is not None:
        lines.append("  Humidity: %.0f%%" % humidity)
    if wind_mph is not None:
        if wind_mph == 0:
            lines.append("  Wind: calm")
        elif wind_deg is not None:
            lines.append("  Wind: %.0f mph from the %s" % (wind_mph, COMPASS[int(round(wind_deg / 22.5)) % 16]))
        else:
            lines.append("  Wind: %.0f mph" % wind_mph)
    if when_text:
        lines.append("  Time: %s" % when_text)
    lines += ["",
              "You get this message when the level rises to High or higher between January and May.",
              "It is sent once per rise, not every few minutes.",
              "",
              "See the live dashboard:",
              dashboard_url]
    msg = EmailMessage()
    msg["Subject"] = "Fire danger %s at %s" % (word.upper(), location)
    msg["From"] = sender
    msg["To"] = ", ".join(recipients)
    msg.set_content("\n".join(lines))
    return msg


def settings_from_env(env=None):
    env = os.environ if env is None else env
    to = [a.strip() for a in str(env.get("ALERT_EMAIL_TO", "")).split(",") if a.strip()]
    user = str(env.get("SMTP_USER", "")).strip()
    password = str(env.get("SMTP_PASSWORD", "")).strip()
    try:
        port = int(env.get("SMTP_PORT", 587))
    except (TypeError, ValueError):
        port = 587
    try:
        cooldown = float(env.get("ALERT_COOLDOWN_HOURS", 6))
    except (TypeError, ValueError):
        cooldown = 6
    return {
        "to": to, "user": user, "password": password,
        "host": str(env.get("SMTP_HOST", "smtp.gmail.com")).strip() or "smtp.gmail.com",
        "port": port,
        "sender": str(env.get("ALERT_EMAIL_FROM", "")).strip() or user,
        "months": parse_months(env.get("ALERT_SEASON_MONTHS", "1-5")),
        "cooldown_hours": cooldown,
        "dashboard_url": str(env.get("DASHBOARD_URL", DASHBOARD_URL_DEFAULT)).strip() or DASHBOARD_URL_DEFAULT,
    }


def configured(s):
    return bool(s["to"] and s["user"] and s["password"])


def send(msg, s):
    """Send one message. Raises on failure; callers decide how to handle it."""
    context = ssl.create_default_context()
    with smtplib.SMTP(s["host"], s["port"], timeout=15) as server:
        server.starttls(context=context)
        server.login(s["user"], s["password"])
        server.send_message(msg)
