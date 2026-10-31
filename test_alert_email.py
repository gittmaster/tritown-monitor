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
SEASON = ae.DEFAULT_SEASON

check("rises to HIGH in March: send", ae.should_send("MODERATE", "HIGH", None, now, march))
check("already HIGH, then VERY HIGH: no new email", ae.should_send("HIGH", "VERY_HIGH", None, now, march) is False)
check("jumps LOW to EXTREME: send", ae.should_send("LOW", "EXTREME", None, now, march))
check("first ever reading is HIGH: send", ae.should_send(None, "HIGH", None, now, march))
check("MODERATE does not send", ae.should_send("LOW", "MODERATE", None, now, march) is False)
check("still HIGH does not send again", ae.should_send("HIGH", "HIGH", None, now, march) is False)
check("July: no email", ae.should_send("LOW", "HIGH", None, now, july) is False)
check("January 14 is before burning season: no email", ae.should_send("LOW", "HIGH", None, now, datetime(2026, 1, 14, 23, 55)) is False)
check("January 15 counts", ae.should_send("LOW", "HIGH", None, now, datetime(2026, 1, 15, 0, 5)))
check("April 30 counts", ae.should_send("LOW", "HIGH", None, now, datetime(2026, 4, 30, 23, 55)))
check("May 1 does not", ae.should_send("LOW", "HIGH", None, now, datetime(2026, 5, 1, 0, 5)) is False)
check("May 31 does not", ae.should_send("LOW", "HIGH", None, now, datetime(2026, 5, 31, 12, 0)) is False)
check("December does not", ae.should_send("LOW", "HIGH", None, now, datetime(2026, 12, 31, 12, 0)) is False)
check("leap day does not matter (Feb 29 2028 counts)", ae.should_send("LOW", "HIGH", None, now, datetime(2028, 2, 29, 9, 0)))
check("sent 1 hour ago: wait (cooldown)", ae.should_send("LOW", "HIGH", now - timedelta(hours=1), now, march) is False)
check("sent 7 hours ago: send again", ae.should_send("LOW", "HIGH", now - timedelta(hours=7), now, march))
check("old resent reading: no email", ae.should_send("LOW", "HIGH", None, now, march, reading_age_minutes=120) is False)
custom = ae.parse_season("3/1-4/15")
check("custom season 3/1-4/15, March: send", ae.should_send("LOW", "HIGH", None, now, march, season=custom))
check("custom season 3/1-4/15, January: no", ae.should_send("LOW", "HIGH", None, now, datetime(2026, 1, 5), season=custom) is False)
check("season setting 1/15-4/30 read", ae.parse_season("1/15-4/30") == ((1, 15), (4, 30)))
check("spaces allowed in the season setting", ae.parse_season(" 1/15 - 4/30 ") == ((1, 15), (4, 30)))
check("silly season setting falls back", ae.parse_season("banana") == ae.DEFAULT_SEASON)
check("backwards season setting falls back", ae.parse_season("5/1-1/1") == ae.DEFAULT_SEASON)
check("impossible date falls back", ae.parse_season("2/30-4/30") == ae.DEFAULT_SEASON)
check("season text is readable", ae.season_text(ae.DEFAULT_SEASON) == "January 15 to April 30")

# ---- the message ------------------------------------------------------------
msg = ae.build_message("Middleton Fire Station", "HIGH", 25.0, 28.0, 8.0, 225.0,
                       "sender@example.com", ["one@example.com", "two@example.com"],
                       "https://tritown-monitor.onrender.com", "Mar 10, 8:00 AM")
body = msg.get_content()
check("subject names level and place", msg["Subject"] == "Fire danger HIGH at Middleton Fire Station")
check("addresses are hidden: not in any header", "one@example.com" not in msg.as_string() and "two@example.com" not in msg.as_string())
check("the visible To line is the sender", msg["To"] == "sender@example.com")
check("it is a burn-permit warning", "burn permit" in body and "does not make" in body)
check("it points to Community Connect", "https://www.communityconnect.io/info/ma-middleton" in body)
check("it names the burning season", "January 15 to April 30" in body)
check("temperature shown in Fahrenheit", "77 F" in body)
check("humidity shown", "28%" in body)
check("wind speed and direction shown", "8 mph from the SW" in body)
check("dashboard link is at the bottom", body.strip().endswith("https://tritown-monitor.onrender.com"))
check("plain words only (no 'Spread Index')", "Spread Index" not in body and "class day" not in body.lower())
calm = ae.build_message("Home", "EXTREME", 30.0, 10.0, 0.0, 10.0, "s@example.com", ["a@example.com"]).get_content()
check("calm wind says calm", "Wind: calm" in calm)

# ---- settings ---------------------------------------------------------------
s = ae.settings_from_env({"ALERT_EMAIL_TO": " a@x.com ,b@x.com,, ", "SMTP_USER": "u@x.com", "SMTP_PASSWORD": "pw"})
check("addresses split and trimmed", s["to"] == ["a@x.com", "b@x.com"])
check("sender defaults to the account", s["sender"] == "u@x.com")
check("season defaults to Jan 15 to Apr 30", s["season"] == ((1, 15), (4, 30)))
check("Gmail is the default mail server", s["host"] == "smtp.gmail.com" and s["port"] == 587)
check("configured when all three are set", ae.configured(s))
check("not configured without a password", not ae.configured(ae.settings_from_env({"ALERT_EMAIL_TO": "a@x.com", "SMTP_USER": "u@x.com"})))
check("not configured with nothing set", not ae.configured(ae.settings_from_env({})))

# ---- sending in hidden batches ------------------------------------------------
import smtplib
many = ["p%d@example.com" % i for i in range(120)]
delivered = []


class FakeSMTP:
    def __init__(self, host, port, timeout=0): pass
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def starttls(self, context=None): pass
    def login(self, u, p): pass
    def send_message(self, m, from_addr=None, to_addrs=None):
        delivered.append((m.as_string(), from_addr, list(to_addrs)))


real_smtp = smtplib.SMTP
smtplib.SMTP = FakeSMTP
real_send = ae.send
big = {"to": many, "user": "u@x.com", "password": "pw", "host": "h", "port": 587, "sender": "u@x.com"}
big_msg = ae.build_message("Home", "HIGH", 20.0, 30.0, 5.0, 90.0, "u@x.com", many)
real_send(big_msg, big)
smtplib.SMTP = real_smtp
check("120 people go out in 3 batches", len(delivered) == 3)
check("each batch is at most 50", all(len(d[2]) <= 50 for d in delivered))
check("everyone is reached exactly once", sorted(a for d in delivered for a in d[2]) == sorted(many))
check("no address appears inside any message", not any("@example.com" in d[0] for d in delivered))

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
