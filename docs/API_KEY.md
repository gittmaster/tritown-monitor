# The API key (the Pi's password)

The Pi proves it is allowed to send readings by including a secret key. The website only accepts readings that carry the right key.

**The key is never stored in the repository.** It lives in exactly two places:

1. **Render:** the service's **Environment** setting `API_KEY`.
2. **Each Pi:** a private file, `/home/pi/.tritown_api_key` (only the `pi` user can read it).

If the website has no `API_KEY` set, it makes a random one on every start, so nobody can post, including us. Setting it is required.

Other secrets follow the same rule and live only in Render: `DATABASE_URL` and, for the email alerts, `SMTP_PASSWORD`. Never put any of them on GitHub.

## What someone could do with the key

They could post fake readings (so the dashboard shows wrong conditions), delete all stored readings (`/api/clear`, no undo), make the website send "TEST" emails, and fake the Pi's health reports. They could **not** read or change the database, change the code, see the Gmail app password, or touch the Pi. That is why we replace it if there is any chance it was seen.

## Make a new key

On any computer with Python (PowerShell on Windows):

```
python -c "import secrets; print(secrets.token_hex(24))"
```

This prints 48 letters and numbers. Keep it in a password manager. Do not paste it into chats, emails or GitHub.

## Change the key on the website and the first Pi (we did this on Oct 30, 2026)

Do these in order. Nothing is lost during the change: the Pi saves its readings while the website refuses it, then resends them.

1. **Render.** Service, **Environment**, click **Edit**, then add or change `API_KEY` to the new key. Click **Save, rebuild, and deploy**. Wait for "Live". From now on the website refuses the old key.
2. **The Pi.** Connect (`ssh pi@<the Pi's address>`) and run this, then paste the key when it waits (nothing shows as you paste, which is normal):

   ```
   read -s -p "Paste key then Enter: " K; echo "$K" > /home/pi/.tritown_api_key; chmod 600 /home/pi/.tritown_api_key; unset K; echo; awk '{print NR": "length($0)" characters"}' /home/pi/.tritown_api_key
   ```

   The last line must say `1: 48 characters`. If it says anything else, you pasted extra text; run it again, copying only the 48 letters and numbers. Using `read -s` keeps the key out of the shell history.
3. **Restart the sender** so it reads the file:

   ```
   sudo systemctl restart pi-sender
   ```
4. **Check the log** (about a minute later; the wind is measured for 30 seconds first):

   ```
   tail -n 5 /home/pi/sender.log
   ```

   You want an `[OK] Sent:` line. If the readings had been waiting, you also see `[QUEUE] resent ... 0 still waiting`.
5. **Confirm the dashboard** shows a fresh reading.

If the log shows errors about the key after a restart, check that the file has exactly one line of 48 characters, and that Render's `API_KEY` is the same value.

## Set up a new Pi (for example a second station)

The new Pi uses the **same key as the first Pi**, because the website has just one key.

1. Build the Pi as in [BUILD_FROM_SCRATCH.md](BUILD_FROM_SCRATCH.md) and copy the program files to it.
2. Save the key on the new Pi with the command in step 2 above.
3. Give the new Pi its own `DEVICE_ID` and `LOCATION` in `pi_sender.py` (see [EMAIL_AND_LOCATIONS.md](EMAIL_AND_LOCATIONS.md)).
4. Start it (`sudo systemctl restart pi-sender`) and check the log as in step 4 above.

The key is not part of `pi_sender.py`; the program reads it from the private file. If the file is missing, the log says `No API key found`, and the sender stops at the start of its main loop instead of sending with no key.

## Back-out plan

- The Pi's old program was saved on the first Pi as `/home/pi/pi_sender.py.before-key-change`.
- The git tag `pre-api-key-secret` is the code from just before this change.
- Because the key lives in Render and on the Pi, going back means setting the key again in both places; the old built-in key `tritown2024` is public (it is in the repository history) and must not be used again.

## Checking from the website side

`/api/stats` is public and does not show the key. A reading posted with the wrong key returns `401`.
