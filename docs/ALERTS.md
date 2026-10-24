# How the fire danger level is calculated

The dashboard shows one of five levels: **LOW, MODERATE, HIGH, VERY HIGH, EXTREME**. There are two ways to calculate it. Which one the live website uses is the `ALERT_METHOD` setting.

| `ALERT_METHOD` | Method | Uses wind? |
|---|---|---|
| `legacy` (default) | The original simple temperature/humidity rule | Only for EXTREME |
| `class_day` | The fire chief's "class day" charts | Yes, always |

Switching is one setting; no code change and no data change. See "Switching" at the end.

---

## 1. The original rule (`legacy`)

From `get_alert()` in `app.py`. The first line that matches wins, checked from the top:

| Level | Condition |
|---|---|
| EXTREME | humidity at most 15 %, temperature at least 85 F, **and** wind at least 25 mph |
| VERY HIGH | humidity at most 20 % and temperature at least 80 F |
| HIGH | humidity at most 30 % and temperature at least 70 F |
| MODERATE | humidity at most 50 % and temperature at least 60 F |
| LOW | anything else |

This rule was our placeholder (based on common NFDRS-style bands) while we waited for the district's own thresholds. It has no idea how dry the grass is, and it ignores wind except to reach EXTREME.

---

## 2. The fire chief's method (`class_day`)

This is the paper method the department uses on a "class day". It has three steps, all in `class_day.py`.

### Step 1: Chart A gives the fine fuel moisture (FM)

Fine fuel moisture is how wet the fine, fast-drying fuels (dry grass, leaves, twigs) are. Lower means drier and more dangerous.

You need three things:

- **Air temperature** (picks a column of the chart, in 10-degree bands from 10 F up to 109 F).
- **Relative humidity** (picks a row; each row covers a humidity range, and every temperature column covers humidity 0 to 100 with no gaps).
- **The herbaceous (grass) stage**: `cured` (dead, dry), `transition`, or `green`. The stage picks which of three columns in the right-hand "Fine Fuel Moisture" window to read. Green grass holds a lot of water, so it gives a much higher FM than cured grass at the same temperature and humidity.

The chart prints some rows twice on purpose, and some boxes are marked **X**. The chart's own note says an X row uses the identical neighbouring row; `class_day.py` does the same.

### Step 2: Chart D gives the spread index (SI)

Chart D crosses the fine fuel moisture (rows) with the **wind speed** (columns) to give the **spread index**, a number from 1 to 100 for how fast a fire would spread.

Wind columns, in mph: `0-1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11-12, 13-15, 16-19, 20-24, 25-29, 30+`. We round the measured wind to a whole mph first (halves round up).

### Step 3: the spread index gives a class

| Spread index | Class | Level shown |
|---|---|---|
| 1 to 4 | 1 | LOW |
| 5 to 9 | 2 | MODERATE |
| 10 to 19 | 3 | HIGH |
| 20 to 39 | 4 | VERY HIGH |
| 40 to 100 | 5 | EXTREME |

The message under the level is the same text the original rule used for that level (`MESSAGES` in `class_day.py`).

### Wind in the calculation

- **Where it comes from:** the wind sensor on the Pi. The Pi takes samples for 30 seconds, averages them, and sends the average speed (mph) and direction (degrees) with each 5-minute reading. See [WIND_SENSOR.md](WIND_SENSOR.md).
- **Direction** is shown on the dashboard but is not used in the level (the chart has no direction input).
- **If wind is missing** (sensor unplugged, broken, or a station without one), the website cannot use the chart. It falls back to the original rule and puts "Wind data not available (estimated from temperature and humidity only)." in front of the message, so nobody mistakes it for a full calculation.
- **Wind height:** the chart assumes winds measured at 20 feet. A sensor mounted lower (ours is currently a few feet up for testing) reads lighter winds, so the level can come out lower than the chart's own standard on a windy day. Mount the sensor as high and open as practical.
- **No spin, no fire spread:** with calm wind the same temperature and humidity can read one or two levels lower. That is correct behavior, not a fault.

### Worked examples (all checked by `test_class_day.py`)

| Temperature | Humidity | Grass | Wind | Fine fuel moisture | Spread index | Class | Level |
|---|---|---|---|---|---|---|---|
| 82 F | 42 % | Transition | 14 mph | 10 | 42 | 5 | EXTREME |
| 63 F | 85 % | Green | 5 mph | 28 | 1 | 1 | LOW |
| 96 F | 30 % | Cured | 17 mph | 3.5 | 75 | 5 | EXTREME |

The first example matches the fire chief's own answer. In the second, our copy of Chart A gives fuel moisture 28 where the chief wrote 29; the class is the same either way.

How wind changes one set of conditions (51.8 F, 46.8 % humidity, Transition, so fuel moisture 14):

| Wind | Spread index | Level |
|---|---|---|
| 0 mph | 9 | MODERATE |
| 3 mph | 12 | HIGH |
| 5 mph | 16 | HIGH |
| 7 mph | 20 | VERY HIGH |
| 10 mph | 23 | VERY HIGH |

The same mild afternoon reads LOW under the original rule and anywhere from MODERATE to VERY HIGH under the chief's method, depending on wind. The class-day method is deliberately more sensitive.

### How we know the charts were typed in correctly

`class_day.py` holds both charts as plain tables, typed in as printed so they can be compared with the paper copy row by row. `validate_tables()` proves the typing is self-consistent: every temperature column covers humidity 0 to 100 with no gaps or overlaps, humidity falls as you go down the chart, every X has an identical neighbouring row to use, Chart D has the right shape, and the spread index never falls as wind rises or as the fuel gets drier. The tests run it, so a typing slip fails the tests. A flatter, clearer scan of Chart D from the department would allow a final side-by-side check; it is not required.

---

## 3. When and where the level is calculated

- **Live readings:** the level is calculated **when a reading arrives** and stored with it. Changing `ALERT_METHOD` affects new readings; readings already stored keep the level they were saved with. After a switch, the dashboard banner updates at the next reading (up to 5 minutes).
- **Forecast panel:** calculated each time the forecast is fetched (cached 30 minutes). It takes the National Weather Service's hourly temperature, humidity and wind for the next 7 days, runs the **same method on every hour**, and shows the **highest level of any hour that day**. So the forecast panel changes immediately when the setting changes, and it does not use the local sensor.
- The 30-minute cache means a forecast edit can take up to half an hour to show.
- **How it is labelled on the dashboard.** The panel says each day shows the highest-risk hour, and that it is a projection, not a measurement. Days 4 to 7 are placed under an "Outlook, less certain" divider with softer styling. We chose this because the National Weather Service itself gives detail only for the first two days and a short outlook for days 3 to 7, and because showing the worst hour is the cautious reading. The official warning is the National Weather Service Red Flag Warning (in our area: humidity at most 30 %, winds above 25 mph, little recent rain, and input from state fire managers), which is separate from our levels. Our levels come from the chief's more sensitive method, so a day can read Very High here without a Red Flag Warning in effect.

---

## 4. Assumptions (all listed for the fire department)

| Assumption | Why | Setting |
|---|---|---|
| Grass stage is **Transition** | We did not know the current season stage. Late autumn may really be Cured, which reads higher. | `HERBACEOUS_STAGE` |
| Wind rounded to whole mph and averaged over 30 seconds at each 5-minute reading | Chart D columns are whole mph; a single instant is too gusty | `WIND_WINDOW_SECONDS` in `pi_sender.py` |
| Wind used as measured, not corrected to 20 feet | No height-correction rule was given | none |
| Classes 1 to 5 shown as Low, Moderate, High, Very High, Extreme | Matches the five levels already on the dashboard | none |
| No wind reading falls back to the original rule and says so | Better a labeled estimate than a blank | none |
| X rows use the repeated neighbouring row | The chart's own note | none |
| Our Chart A gives FM 28 where the chief wrote 29 for 63 F / 85 % / Green | Same class either way | none |

If the department wants any of these changed, it is a small edit.

---

## 5. Switching

On Render, open the service, then **Environment**:

- Turn the chief's method **on**: add `ALERT_METHOD` = `class_day`, then **Save, rebuild, and deploy**.
- Turn it **off** (back to the original rule): set `ALERT_METHOD` to `legacy`, or delete the row, then save.
- Change the grass stage: set `HERBACEOUS_STAGE` to `cured`, `transition` or `green`, then save.

To confirm which method is live, open `/api/stats` on the website and read `alert_method` and `herbaceous_stage`.

If `class_day.py` is missing or throws an error, the website falls back to the original rule on its own and logs the reason, so a problem in the new method can never take the dashboard down.
