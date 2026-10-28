# The wind sensor

We use a **Veinasa XS-WSDS01** integrated wind speed and direction sensor (ABS plastic, RS485 output) on a **USB-to-RS485 adapter** (Jhoinrch). It measures both wind speed (cups) and wind direction (vane) in one unit.

## What you need

- XS-WSDS01 wind sensor (RS485 / Modbus version)
- USB-to-RS485 adapter
- 12-volt DC power supply, 1 amp or more (ours is 12 V, 2 A)
- Cable between the sensor and the Pi (see "Longer cable" below)
- A small screw terminal strip, a small flat screwdriver, and a multimeter
- A weatherproof box for the adapter and any wire joints

## Wiring

The sensor has four bare wires:

| Sensor wire | Goes to |
|---|---|
| **Red** | + (plus) of the 12 V supply |
| **Black** | - (minus) of the 12 V supply |
| **Yellow** | RS485 **A** (adapter terminal A+) |
| **Green** | RS485 **B** (adapter terminal B-) |

On the adapter's green screw block, the **top slot is A+** and the **second slot is B-**; the bottom two (NC) stay empty. Loosen the screw, push the bare tip in all the way, tighten, and tug gently to check.

Power and data are separate: the adapter carries only data (it is powered by the Pi's USB port), and the 12 V supply powers only the sensor. Join the sensor's red/black to the supply's two wires on a screw terminal strip (the two screws in one block of the strip are connected to each other).

**Check polarity before powering.** Many cheap supplies have two identical white wires. With the supply plugged in, set a multimeter to DC volts (the "20" setting), touch the red probe to one wire and the black probe to the other (keep the bare tips apart), and read the display. A positive number (about 12) means the wire under the red probe is **+**. A negative number means it is the other way round. On our supply the wire with the dashed gray pattern is +. Never connect it from the stripe alone; always measure.

Unplug the supply while you work on any wiring.

### Sensor settings (from the manual)

Standard Modbus-RTU, 9600 baud, 8 data bits, no parity, 1 stop bit, device address 1.

| Register | Meaning | Scaling |
|---|---|---|
| 0x0000 | Wind speed | m/s, value / 10 |
| 0x0001 | Wind level | whole number |
| 0x0002 | Wind speed | km/h, value / 100 |
| 0x0003 | Wind direction angle | degrees, value / 10 |
| 0x0004 | Compass bearing code | 0 = N ... 15 = NNW (16 points) |

Our code only **reads** these. It never writes a setting to the sensor. The sensor also has a heating option (register 0x006B); we never switch it on.

## Test it before installing it

`wind_probe.py` is a read-only test. It looks for the adapter, asks the sensor for its numbers, and prints about 30 seconds of live readings.

**On a Windows laptop** (nothing live is touched):

```
python -m pip install pyserial
python wind_probe.py
```

**On the Pi:**

```
ls /dev/ttyUSB*            # should list /dev/ttyUSB0
python3 wind_probe.py
```

Plug in the adapter first, then the 12 V supply, then run it. You should see `SENSOR ANSWERED`. Spin the cups by hand and turn the vane: the speed should rise, then fall to 0.0 as the cups slow down, and the direction should change. If you only see `No answer`, work through the troubleshooting table below.

> The probe can be run on the Pi while the sender is running (we did). If you ever see odd or missing numbers, the two programs may be asking the sensor at the same moment: stop the sender (`sudo systemctl stop pi-sender`), run the probe, then start it again (`sudo systemctl start pi-sender`). The sender reads the wind automatically; you do not need the probe in normal use.

## How the Pi uses it

`wind_sensor.py` is used by `pi_sender.py`. Before each 5-minute send it samples the sensor about every 2 seconds for 30 seconds and sends the **average** speed (mph) and direction (degrees). Settings at the top of `pi_sender.py`:

| Setting | Meaning | Default |
|---|---|---|
| `WIND_ENABLED` | Turn the wind sensor on or off | `True` |
| `WIND_PORT` | Serial device of the adapter | `/dev/ttyUSB0` |
| `WIND_WINDOW_SECONDS` | How long to average before each send | 30 |

Safety rules built in:

- A missing, unplugged or broken wind sensor **never** stops temperature and humidity from being sent. The wind part is fenced off and returns nothing on trouble.
- Readings above 60 m/s (the sensor tops out at 30) are treated as garbage and ignored.
- At least 3 good samples are needed in the window, or wind is skipped for that round.
- After 3 silent rounds in a row (about 15 minutes), the Pi reports "wind sensor not answering" to the website, which shows a warning and sends a phone alert; see [RELIABILITY.md](RELIABILITY.md).

When it is calm (0.0 mph), the dashboard shows "calm (last from S)": the last direction the vane read, in small print, so the card never looks empty. With no wind the vane can point anywhere, so treat that letter as "last seen", not as a measurement.

## Mounting

- **Height and openness matter.** The fire chart assumes winds measured at **20 feet**. Mount the sensor as high and in as open a spot as is practical, away from walls, trees and roof edges that block or swirl the wind. A sensor a few feet off the ground reads lighter winds, so the fire danger level may come out lower than the chart's standard on a windy day.
- **North.** The sensor has a north mark. Point it at true north (use a compass, then correct for local magnetic declination if you want exact degrees) so the direction on the dashboard is right.
- **Level.** The sensor should stand upright with the cups free to spin.
- **Bracket.** The sensor's own black mounting tube bolts to a flat surface or under a railing with the supplied bolts. A separate 1.25-inch mast kit (a 35-inch smooth mast, a 35-inch swaged mast that slides into it, two clamps and four lag screws) can lift it higher if you also have a tube or clamp that fits the sensor's base.

## Longer cable (10 to 30 feet or more)

The sensor's own cable is short (a few feet). RS485 is built for long runs (hundreds of feet), and the sensor draws very little power, so extending it is easy.

**Recommended layout:**

```
Sensor (outside) -- short sensor cable -- [waterproof joint] -- Cat6 cable -- [weatherproof box next to the Pi]
                                                                                 white screw strip, USB adapter, 12 V supply
```

- Keep the **USB adapter next to the Pi**. USB itself should not be extended much beyond a few feet; the long run is the RS485 and power wires.
- One run of plain network cable (Cat6) carries everything. It has four twisted pairs (eight wires):

| Cat6 wires | Use | Joins sensor wire |
|---|---|---|
| White/orange | RS485 **A** | Yellow |
| Orange | RS485 **B** | Green |
| Blue pair (both wires together) | **+** 12 V | Red |
| Brown pair (both wires together) | **-** 12 V | Black |
| Green pair | not used | |

Using both wires of a pair for each power line costs nothing and keeps the voltage steady over a long run.

- **Outdoor use:** use cable rated for outdoor/UV or direct burial; ordinary indoor Cat6 will crack in the sun over time.
- **Weatherproofing:** every wire joint must be sealed. Use either a small weatherproof box with a sealing cable gland on each side and a terminal strip inside (easy to open later), or glue-lined heat-shrink butt connectors. Let the cable hang in a small loop just before each box so rain drips off before it reaches the entry.
- Measure twice: cut the cable only after you have chosen the sensor's permanent spot and measured the route.
- Test the full path with `wind_probe.py` before sealing anything.

(The long-cable layout is our plan for the permanent mounting. The first working tests used the sensor's own short cable.)

## Troubleshooting

| What you see | Likely cause | What to do (supply unplugged while working) |
|---|---|---|
| `No USB serial adapter found` | Adapter not plugged in or not recognised | Re-plug it; on the Pi `ls /dev/ttyUSB*`; on Windows check Device Manager, Ports |
| Adapter found, `No answer from the sensor` | No power, or yellow/green wrong | Check the 12 V supply is plugged in and red/black polarity; check yellow in A+ and green in B-; then try swapping yellow and green |
| Speed stays 0.0 while spinning | Cups blocked, or the reading is between samples | Spin freely; remember the dashboard shows a 30-second average once every 5 minutes |
| Direction is jumpy when calm | Normal: no wind means no steady direction | Ignore; the dashboard shows "calm (last from ...)" |
| Direction is off by a fixed amount | North mark not aimed at north | Re-aim the sensor |
| Works on a laptop but not on the Pi | pyserial missing, or the sender is asking the sensor at the same moment | `pip3 install pyserial`; stop `pi-sender` while running the probe |
| Dashboard says "Wind sensor not reporting" | The Pi stopped getting wind (loose plug, power, adapter) | Check the USB adapter, its screw block, the 12 V supply and the joints |
