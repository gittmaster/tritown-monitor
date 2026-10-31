"""Email burn-permit holders when the fire danger reaches HIGH (or worse) in burning season.

The list is the people who have a burn permit. The message is a warning: a permit does
not make a HIGH day a safe day to burn.

Rules (all easy to change with settings on the website host):
  * Only in burning season, January 15 to April 30 (Massachusetts time).
  * Only when a station's level RISES to HIGH, VERY HIGH or EXTREME. It does not
    repeat on every 5-minute reading.
  * At most one email per station every COOLDOWN_HOURS (default 6), so a level
    that flickers up and down around the line does not flood anyone's inbox.
  * Never for old readings that a Pi resends after an outage.

Settings (set on the website host, never in the code or on GitHub):
  ALERT_EMAIL_TO        who gets it: one or more addresses separated by commas.
                        Everyone is sent a hidden ("Bcc") copy, so nobody sees anyone else's address.
  SMTP_USER             the sending account (for Gmail: the full address)
  SMTP_PASSWORD         that account's app password
  SMTP_HOST / SMTP_PORT default smtp.gmail.com / 587
  ALERT_EMAIL_FROM      optional "from" address (defaults to SMTP_USER)
  ALERT_EMAIL_LOCATIONS optional: only these stations send email (names separated by commas, exactly as
                        they appear on the dashboard). Not set = every station sends. Set it to the real
                        station(s) so a test unit never emails the list.
  ALERT_SEASON          optional, default "1/15-4/30" (January 15 to April 30), month/day-month/day
  ALERT_COOLDOWN_HOURS  optional, default 6
  DASHBOARD_URL         optional, default the TriTown dashboard

If ALERT_EMAIL_TO or the sending account is not set, nothing is sent and
nothing else changes.
"""
import os
import re
import smtplib
import ssl
from datetime import datetime, timedelta
from email.message import EmailMessage

DASHBOARD_URL_DEFAULT = "https://tritown-monitor.onrender.com"
COMMUNITY_CONNECT_URL = "https://www.communityconnect.io/info/ma-middleton"

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


DEFAULT_SEASON = ((1, 15), (4, 30))
MONTH_NAMES = ["", "January", "February", "March", "April", "May", "June", "July",
               "August", "September", "October", "November", "December"]


def parse_season(raw, default=DEFAULT_SEASON):
    """'1/15-4/30' means January 15 to April 30. Anything unreadable (or backwards, or an
    impossible date) falls back to the default."""
    m = re.fullmatch(r"\s*(\d{1,2})/(\d{1,2})\s*-\s*(\d{1,2})/(\d{1,2})\s*", str(raw))
    if not m:
        return default
    m1, d1, m2, d2 = (int(x) for x in m.groups())
    try:
        datetime(2001, m1, d1)
        datetime(2001, m2, d2)
    except ValueError:
        return default
    if (m1, d1) > (m2, d2):
        return default
    return (m1, d1), (m2, d2)


def season_text(season=DEFAULT_SEASON):
    (m1, d1), (m2, d2) = season
    return "%s %d to %s %d" % (MONTH_NAMES[m1], d1, MONTH_NAMES[m2], d2)


def local_now():
    """The current time in Massachusetts (so January 1 starts at local midnight)."""
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("America/New_York"))
    except Exception:
        return datetime.utcnow() - timedelta(hours=5)


def location_allowed(location, allowed):
    """allowed is the list from ALERT_EMAIL_LOCATIONS. Empty means every station may send.
    Names match ignoring capital letters and extra spaces."""
    if not allowed:
        return True
    norm = lambda x: " ".join(str(x).lower().split())
    return norm(location) in {norm(a) for a in allowed}


def in_season(when, season=DEFAULT_SEASON):
    """True when the date (year ignored) falls inside the season, both ends included."""
    return season[0] <= (when.month, when.day) <= season[1]


def should_send(prev_level, new_level, last_sent_utc, now_utc, local_when,
                reading_age_minutes=0, season=DEFAULT_SEASON, cooldown_hours=6):
    """Decide if this reading should trigger an email. Pure function, easy to test."""
    if level_rank(new_level) < level_rank("HIGH"):
        return False
    if not in_season(local_when, season):
        return False
    if reading_age_minutes > 30:          # an old reading resent after an outage
        return False
    if level_rank(prev_level) >= level_rank("HIGH"):
        return False                      # it was already that high; no new news
    if last_sent_utc is not None and now_utc - last_sent_utc < timedelta(hours=cooldown_hours):
        return False
    return True


def build_message(location, level, temp_c, humidity, wind_mph, wind_deg,
                  sender, recipients, dashboard_url=DASHBOARD_URL_DEFAULT, when_text="",
                  season=DEFAULT_SEASON):
    """Plain-language warning for people who hold a burn permit. No jargon.

    The visible "To" line is the sender, so the people on the list never see each other's
    addresses; send() delivers to the real list in small hidden batches."""
    word = LEVEL_WORDS.get(level, level.title())
    temp_f = temp_c * 9 / 5 + 32 if temp_c is not None else None
    lines = ["Burning warning: the fire danger at %s has reached %s." % (location, word.upper()), ""]
    lines.append("You are getting this because you hold a burn permit. A permit does not make a "
                 "%s fire danger day a safe day to burn. Please use extra caution today." % word.upper())
    lines.append("")
    lines.append("What it means: %s" % WHAT_IT_MEANS.get(level, ""))
    lines.append("")
    lines.append("The Middleton Fire Department posts the burning status for the day on Community Connect. "
                 "Please check it before you burn, and call the fire department with any questions:")
    lines.append(COMMUNITY_CONNECT_URL)
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
              "You get this message when the fire danger rises to High or higher during burning season (%s)." % season_text(season),
              "It is sent once per rise, not every few minutes.",
              "",
              "See the live dashboard:",
              dashboard_url]
    msg = EmailMessage()
    msg["Subject"] = "Burning warning: fire danger %s at %s" % (word.upper(), location)
    msg["From"] = sender
    msg["To"] = sender
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
        "locations": [a.strip() for a in str(env.get("ALERT_EMAIL_LOCATIONS", "")).split(",") if a.strip()],
        "season": parse_season(env.get("ALERT_SEASON", "1/15-4/30")),
        "cooldown_hours": cooldown,
        "dashboard_url": str(env.get("DASHBOARD_URL", DASHBOARD_URL_DEFAULT)).strip() or DASHBOARD_URL_DEFAULT,
    }


def configured(s):
    return bool(s["to"] and s["user"] and s["password"])


BATCH_SIZE = 50    # recipients per delivery, so one huge list never trips the mail server's limits


def send(msg, s):
    """Deliver one message to everyone on the list, in hidden batches of BATCH_SIZE.
    Nobody's address appears in the message itself. Raises on failure; callers decide
    how to handle it."""
    recipients = list(s["to"])
    context = ssl.create_default_context()
    with smtplib.SMTP(s["host"], s["port"], timeout=15) as server:
        server.starttls(context=context)
        server.login(s["user"], s["password"])
        for i in range(0, len(recipients), BATCH_SIZE):
            server.send_message(msg, from_addr=s["sender"], to_addrs=recipients[i:i + BATCH_SIZE])
