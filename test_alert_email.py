"""
Offline test for the spring "fire danger reached HIGH" email.

No real email is sent: the sending step is replaced by a stand-in that just
records what would have gone out. Uses a throwaway database.
Usage: python test_alert_email.py
"""
import os
import tempfile
import time
from datetime import datetime, timedelta

_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp.close()
os.environ["DB_PATH"] = _tmp.name
os.environ.pop("DATABASE_URL", None)
os.environ["API_KEY"] = "test-key"
os.environ["ALERT_EMAIL_TO"] = "one@example.com, two@example.com"
os.environ["SMTP_USER"] = "sender@example.com"
os.environ["SMTP_PASSWORD"] = "not-a-real-password"

import alert_email as ae  # noqa: E402
import app as app_module  # noqa: E402

passed = failed = 0


def check(label, condition):
    global passed, failed
    if condition:
        passed += 1
        print(f"[PASS] {label}")
    else:
        failed += 1
        print(f"[FAIL] {label}")


# ---- the decision rule on its own -------------------------------------------
now = datetime(2026, 3, 10, 12, 0, 0)
march = datetime(2026, 3, 10, 8, 0, 0)
july = datetime(2026, 7, 10, 8, 0, 0)

check("rises to HIGH in March: send", ae.should_send("MODERATE", "HIGH", None, now, march))
check("already HIGH, then VERY HIGH: no new email", ae.should_send("HIGH", "VERY_HIGH", None, now, march) is False)
check("jumps LOW to EXTREME: send", ae.should_send("LOW", "EXTREME", None, now, march))
check("first ever reading is HIGH: send", ae.should_send(None, "HIGH", None, now, march))
check("MODERATE does not send", ae.should_send("LOW", "MODERATE", None, now, march) is False)
check("still HIGH does not send again", ae.should_send("HIGH", "HIGH", None, now, march) is False)
check("July: no email", ae.should_send("LOW", "HIGH", None, now, july) is False)
check("January 1 counts", ae.should_send("LOW", "HIGH", None, now, datetime(2026, 1, 1, 0, 5)))
check("May 31 counts", ae.should_send("LOW", "HIGH", None, now, datetime(2026, 5, 31, 23, 55)))
check("June 1 does not", ae.should_send("LOW", "HIGH", None, now, datetime(2026, 6, 1, 0, 5)) is False)
check("December does not", ae.should_send("LOW", "HIGH", None, now, datetime(2026, 12, 31, 12, 0)) is False)
check("sent 1 hour ago: wait (cooldown)", ae.should_send("LOW", "HIGH", now - timedelta(hours=1), now, march) is False)
check("sent 7 hours ago: send again", ae.should_send("LOW", "HIGH", now - timedelta(hours=7), now, march))
check("old resent reading: no email", ae.should_send("LOW", "HIGH", None, now, march, reading_age_minutes=120) is False)
check("custom season 3-4, March: send", ae.should_send("LOW", "HIGH", None, now, march, months=(3, 4)))
check("custom season 3-4, January: no", ae.should_send("LOW", "HIGH", None, now, datetime(2026, 1, 5), months=(3, 4)) is False)
check("season setting 1-5 read", ae.parse_months("1-5") == (1, 5))
check("silly season setting falls back", ae.parse_months("banana") == (1, 5))
check("backwards season setting falls back", ae.parse_months("5-1") == (1, 5))

# ---- the message ------------------------------------------------------------
msg = ae.build_message("Middleton Fire Station", "HIGH", 25.0, 28.0, 8.0, 225.0,
                       "sender@example.com", ["one@example.com", "two@example.com"],
                       "https://tritown-monitor.onrender.com", "Mar 10, 8:00 AM")
body = msg.get_content()
check("subject names level and place", msg["Subject"] == "Fire danger HIGH at Middleton Fire Station")
check("both people are addressed", "one@example.com" in msg["To"] and "two@example.com" in msg["To"])
check("temperature shown in Fahrenheit", "77 F" in body)
check("humidity shown", "28%" in body)
check("wind speed and direction shown", "8 mph from the SW" in body)
check("dashboard link is at the bottom", body.strip().endswith("https://tritown-monitor.onrender.com"))
check("plain words only (no 'Spread Index')", "Spread Index" not in body and "class" not in body.lower())
calm = ae.build_message("Home", "EXTREME", 30.0, 10.0, 0.0, 10.0, "s@example.com", ["a@example.com"]).get_content()
check("calm wind says calm", "Wind: calm" in calm)

# ---- settings ---------------------------------------------------------------
s = ae.settings_from_env({"ALERT_EMAIL_TO": " a@x.com ,b@x.com,, ", "SMTP_USER": "u@x.com", "SMTP_PASSWORD": "pw"})
check("addresses split and trimmed", s["to"] == ["a@x.com", "b@x.com"])
check("sender defaults to the account", s["sender"] == "u@x.com")
check("Gmail is the default mail server", s["host"] == "smtp.gmail.com" and s["port"] == 587)
check("configured when all three are set", ae.configured(s))
check("not configured without a password", not ae.configured(ae.settings_from_env({"ALERT_EMAIL_TO": "a@x.com", "SMTP_USER": "u@x.com"})))
check("not configured with nothing set", not ae.configured(ae.settings_from_env({})))

# ---- through the real website code ------------------------------------------
sent = []
ae.send = lambda m, settings: sent.append(m)           # stand-in: nothing leaves this computer
client = app_module.app.test_client()
HEAD = {"X-API-Key": "test-key"}


def post(location, temp_c, humidity, wind=None, **extra):
    payload = {"device_id": "t-" + location, "location": location, "temperature": temp_c, "humidity": humidity}
    if wind is not None:
        payload["wind_speed"] = wind
    payload.update(extra)
    r = client.post("/api/reading", json=payload, headers=HEAD)
    time.sleep(0.3)                                    # the email goes out in the background
    return r


ae.local_now = lambda: datetime(2026, 3, 10, 9, 0, 0)  # pretend it is a March morning
LOW = (10.0, 60.0)
MOD = (25.0, 40.0)
HIGH = (25.0, 25.0)

r = post("Home", *LOW)
check("a low reading stores fine", r.status_code == 201)
check("low reading: no email", len(sent) == 0)
post("Home", *MOD)
check("moderate: no email", len(sent) == 0)
r = post("Home", *HIGH)
check("rising to HIGH still stores the reading", r.status_code == 201 and r.get_json()["alert_level"] == "HIGH")
check("rising to HIGH sends one email", len(sent) == 1)
check("email names the station", "Home" in sent[0]["Subject"])
post("Home", *HIGH)
check("still HIGH: no second email", len(sent) == 1)
post("Home", *MOD)
post("Home", *HIGH)
check("dropped and rose again within the cooldown: no second email", len(sent) == 1)
post("Middleton Fire Station", *LOW)
post("Middleton Fire Station", *HIGH)
check("a different station gets its own email", len(sent) == 2 and "Middleton Fire Station" in sent[1]["Subject"])

ae.local_now = lambda: datetime(2026, 7, 10, 9, 0, 0)  # now pretend it is July
post("Library", *LOW)
post("Library", *HIGH)
check("July: no email even at HIGH", len(sent) == 2)

ae.local_now = lambda: datetime(2026, 3, 10, 9, 0, 0)
old = (datetime.utcnow() - timedelta(hours=3)).strftime("%Y-%m-%dT%H:%M:%S")
post("Old Pi", *LOW)
post("Old Pi", *HIGH, recorded_at=old)
check("an old resent reading does not email", len(sent) == 2)

# a broken mail server must not break readings
def boom(m, settings):
    raise RuntimeError("mail server down")
ae.send = boom
post("Third", *LOW)
r = post("Third", *HIGH)
check("mail server down: reading still saved", r.status_code == 201)

# nothing is sent when email is not set up
os.environ.pop("SMTP_PASSWORD")
ae.send = lambda m, settings: sent.append(m)
before = len(sent)
post("Fourth", *LOW)
r = post("Fourth", *HIGH)
check("email not set up: reading saved, nothing sent", r.status_code == 201 and len(sent) == before)

# ---- the test-email button --------------------------------------------------
os.environ["SMTP_PASSWORD"] = "not-a-real-password"
before = len(sent)
r = client.post("/api/test-email", headers={"X-API-Key": "wrong"})
check("test email needs the key", r.status_code == 401 and len(sent) == before)
r = client.post("/api/test-email", headers=HEAD)
check("test email sends one message", r.status_code == 200 and len(sent) == before + 1)
check("test email is marked TEST", sent[-1]["Subject"].startswith("TEST - "))

print(f"\n{passed} passed, {failed} failed")
