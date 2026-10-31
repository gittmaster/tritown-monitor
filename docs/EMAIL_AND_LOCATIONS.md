# Email alerts and more than one location

Two features added after the first demo, both asked for by the Fire Marshal:

1. An **email** goes out to people who hold a burn permit when the fire danger reaches HIGH (or worse) during burning season. It is a warning: a permit does not make a High day a safe day to burn.
2. The dashboard can show **several stations**, with a **Location** drop-down.

---

## 1. Email when the fire danger reaches HIGH (burn-permit warning)

### The rules

| Rule | Value | Setting |
|---|---|---|
| Season | **January 15 to April 30** (the town's burning season, Massachusetts time) | `ALERT_SEASON` (default `1/15-4/30`, month/day-month/day) |
| What sends an email | A station's level **rises** to HIGH, VERY HIGH or EXTREME from below HIGH | none |
| Repeats | At most one email per station every 6 hours, even if the level goes up and down | `ALERT_COOLDOWN_HOURS` (default `6`) |
| Old readings | A reading the Pi re-sends after an outage (older than 30 minutes) never sends an email | none |
| Moving from HIGH to VERY HIGH | No new email (it was already HIGH or worse) | none |

If anything goes wrong with email (wrong password, Gmail down, nobody set up), the **reading is still saved** and the dashboard is unaffected. The email is sent in the background and any error is only written to the website's log.

### Who gets it, and what it says

The list is the people who hold a burn permit (the Fire Marshal provides the addresses). The email says, in plain words, that they are getting it because they hold a permit, that a permit does not make a High day a safe day to burn, what the level means, the temperature, humidity and wind right now, a link to the town's Community Connect page (<https://www.communityconnect.io/info/ma-middleton>, where the fire department posts the day's burning status), and the dashboard link on the last line.

**Privacy:** every address is a hidden ("Bcc") recipient. The visible "To" line is only the sending address, so nobody sees anyone else's email. Long lists are sent in hidden batches of 50.

**Sending from Gmail:** an ordinary Gmail account limits how many messages it can send per day (about 500 recipients), and a long list from a personal address can be marked as spam. This is fine for testing and a short list. For the full permit-holder list, ask the town whether the fire department can send from an official address or mail service; only `SMTP_USER`, `SMTP_PASSWORD` and (for another provider) `SMTP_HOST` change.

The code is `alert_email.py`. The code is `alert_email.py`; the tests are `test_alert_email.py` (49 checks, nothing real is sent).

### Settings (Render, your service, **Environment**; never GitHub)

| Setting | What to put |
|---|---|
| `ALERT_EMAIL_TO` | Who gets it. One address, or several separated by commas. |
| `SMTP_USER` | The Gmail address that sends the message. |
| `SMTP_PASSWORD` | That account's **app password** (16 letters; see below). Never your normal password. |
| `SMTP_HOST`, `SMTP_PORT` | Optional. Default `smtp.gmail.com` and `587`. |
| `ALERT_EMAIL_FROM` | Optional "from" address. Default: `SMTP_USER`. |
| `ALERT_EMAIL_LOCATIONS` | Which stations may send email, names separated by commas and written exactly as on the dashboard. **Set it to `Middleton Fire Station`** so the "Home" test unit never emails the permit holders. If it is not set, every station sends. |
| `ALERT_SEASON` | Optional. Default `1/15-4/30` (January 15 to April 30). |
| `ALERT_COOLDOWN_HOURS` | Optional. Default `6`. |
| `DASHBOARD_URL` | Optional. Default `https://tritown-monitor.onrender.com`. |

If `ALERT_EMAIL_TO`, `SMTP_USER` or `SMTP_PASSWORD` is missing, the feature is simply off.

Email needs a Render **paid** instance (ours is); free instances block outgoing mail.

### Setting it up (one step at a time)

1. **Create an app password.** Sign in to the sending Gmail account. 2-Step Verification must be on. Open <https://myaccount.google.com/apppasswords>, type the name `Middleton Fire Alerts`, click **Create**, and copy the 16 letters. You can delete it there at any time.
2. **Put the three settings in Render.** Service, **Environment**, add `ALERT_EMAIL_TO`, `SMTP_USER`, `SMTP_PASSWORD`, then **Save, rebuild, and deploy**.
3. **Send a test message.** From PowerShell (use your own API key):

   ```
   curl.exe -X POST https://tritown-monitor.onrender.com/api/test-email -H "X-API-Key: YOUR-KEY"   (YOUR-KEY is the one saved in Render; see API_KEY.md)
   ```

   The reply `{"success": true, "sent_to": 1}` means it went out. The subject starts with `TEST - ` so nobody mistakes it for a real alert.
4. **Add more people** by adding their addresses to `ALERT_EMAIL_TO` with commas, then save and deploy. Test first with your own address only; add the fire department's list once it works.

The sending address is the dedicated account `middleton.fire.alerts@gmail.com` (not a personal one; the sender name is "Middleton Fire Danger Alerts"). Create its app password the same way, signed in to that account. If the town later provides its own address or mail service, only `SMTP_USER`, `SMTP_PASSWORD` and (for another provider) `SMTP_HOST` change.

### What is set up now (Oct 31, 2026)

- **Sending account:** `middleton.fire.alerts@gmail.com`, with 2-Step Verification on (a passkey) and an app password named `Middleton Fire Alerts`. Only the 16-letter app password is used by the website; the account's own password is never stored anywhere in the system.
- **Render settings:** `SMTP_USER` = the address above, `SMTP_PASSWORD` = the app password, `ALERT_EMAIL_TO` = our own Gmail for testing, `ALERT_EMAIL_LOCATIONS` = `Middleton Fire Station`. Nothing else is needed: the mail server defaults to Gmail.
- **Test:** the "TEST - " message arrived, with the recipients hidden (the visible "To" line is the sending address only).
- **To go live with the real list:** put the Fire Marshal's addresses in `ALERT_EMAIL_TO` (commas between them), save, and send one more test. Real warnings can only go out between January 15 and April 30.
- **If the app password is ever lost or leaked:** in the account, open <https://myaccount.google.com/apppasswords>, delete it, make a new one, and put the new value in Render's `SMTP_PASSWORD`.

### Switching it off or on

Delete `SMTP_PASSWORD` (or `ALERT_EMAIL_TO`) in Render to turn it off. Put it back to turn it on. Nothing else changes.

### Seeing what was sent

The website keeps one row per email sent in the `alert_emails` table (place, level, time). It is also how the 6-hour limit is remembered.

---

## 2. More than one location

### What the dashboard does

- **One location reporting:** the page looks exactly as before; there is no drop-down.
- **Two or more reporting:** a **Location** drop-down appears above the readings: "All locations" plus each place by name.
  - *All locations:* one card per place; the colored banner shows the **worst** level among them.
  - *One place chosen:* only that card, that banner and that place's humidity trend.
  - The choice is remembered on that browser.
- The forecast panel is separate: it uses its own ZIP code box (default 01949) and is not tied to the drop-down.

A "location" is just the `LOCATION` text each Pi sends. A new name appears on the dashboard the first time that Pi reports; nothing needs to be added to the website.

### Names we are using

| Unit | `DEVICE_ID` | `LOCATION` |
|---|---|---|
| The first unit (our test setup) | `pi-library` | `Home` |
| The new unit at the fire station | a different name, e.g. `pi-firestation` | `Middleton Fire Station` |

Each Pi needs its **own** `DEVICE_ID`, or the website cannot tell them apart.

### Building the second unit

1. Build it exactly as in [BUILD_FROM_SCRATCH.md](BUILD_FROM_SCRATCH.md), sections 2 and 3 (parts list, wiring, wind sensor, program files, start at boot, schedules).
2. In `pi_sender.py` on the new Pi set `DEVICE_ID = 'pi-firestation'` and `LOCATION = 'Middleton Fire Station'`; `SERVER_URL` is the same as on the first Pi. The API key is **not** in this file: save the same key in the new Pi's private file, as described in [API_KEY.md](API_KEY.md).
3. Do the same in `check_heartbeat.py`'s settings if it names the device (it reads the website's `/api/stats`, which covers every location).
4. Start it. The new card and the drop-down appear within 5 minutes.

The wind sensor on each unit should be mounted high and in the open (see [WIND_SENSOR.md](WIND_SENSOR.md)).

### Renaming the first unit from "Middleton Fire Station" to "Home"

Old readings are stored under the old name. **Do these in order, before the new fire-station unit starts reporting**, so the two places do not get mixed:

1. On the first Pi, edit `pi_sender.py`: `LOCATION = 'Home'`, then `sudo systemctl restart pi-sender`.
2. In Supabase, **SQL Editor**, run once:

   ```sql
   UPDATE public.readings      SET location = 'Home' WHERE location = 'Middleton Fire Station';
   UPDATE public.device_status SET location = 'Home' WHERE location = 'Middleton Fire Station';
   UPDATE public.alert_emails  SET location = 'Home' WHERE location = 'Middleton Fire Station';
   ```

   Undo (if you run it by mistake): the same three lines with the two names swapped.
3. Only then start the new unit with `LOCATION = 'Middleton Fire Station'`.

If you skip step 2, the old readings simply stay under the old name and the history chart for "Home" starts empty. Nothing is lost.

### Known limits

- The forecast ZIP code is per browser, not per location. If two places are in different towns, type the other ZIP.
- Each place is alerted on its own readings; there is no combined "town" level.
