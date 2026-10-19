"""
Offline test for class_day.py (the fire chief's Chart A + Chart D method).
Usage: python test_class_day.py
"""
import copy

import class_day as cd

passed = failed = 0


def check(label, condition):
    global passed, failed
    if condition:
        passed += 1
        print(f"[PASS] {label}")
    else:
        failed += 1
        print(f"[FAIL] {label}")


def c_to_f_input(f):
    return (f - 32) * 5.0 / 9.0


def run(temp_f, rh, wind, stage):
    return cd.assess(c_to_f_input(temp_f), rh, wind, stage)


# ---- the typed-in charts are self-consistent
check("charts pass every self-check", cd.validate_tables() == [])
check("Chart A has 39 rows, same as the fuel moisture window", len(cd.CHART_A_ROWS) == len(cd.HERBACEOUS_ROWS) == 39)
check("Chart D has 32 rows and 16 wind columns", len(cd.CHART_D) == 32 and all(len(r) == 16 for r in cd.CHART_D))

# a typing mistake must be caught
saved = copy.deepcopy(cd.CHART_A_ROWS)
cd.CHART_A_ROWS[10][2] = '85-80'
cd._COLUMNS[:] = cd._column_cells()
check("a mistyped humidity range is caught", len(cd.validate_tables()) > 0)
cd.CHART_A_ROWS[:] = saved
cd._COLUMNS[:] = cd._column_cells()
d_saved = copy.deepcopy(cd.CHART_D)
cd.CHART_D[20][5] = 5
check("a mistyped Chart D number is caught", len(cd.validate_tables()) > 0)
cd.CHART_D[:] = d_saved
check("tables are back to normal after the checks", cd.validate_tables() == [])

# ---- the fire chief's own class-day examples
r = run(82, 42, 14, 'transition')
check("Ben #1 (82F, 42%, Transition, 13-15 mph): fuel moisture 10", r['fine_fuel_moisture'] == 10)
check("Ben #1: spread index 42 (his answer)", r['spread_index'] == 42)
check("Ben #1: class 5", r['fire_class'] == 5)
r = run(63, 85, 5, 'green')
check("Ben #2 (63F, 85%, Green, 5 mph): spread index 1 (his answer)", r['spread_index'] == 1)
check("Ben #2: class 1", r['fire_class'] == 1)
# NOTE: Ben wrote fuel moisture 29; the chart as printed gives 28. Same spread index.
check("Ben #2: fuel moisture comes out 28 on the printed chart (he wrote 29; same result)",
      r['fine_fuel_moisture'] == 28)
r = run(96, 30, 17, 'cured')
check("Ben #3 (96F, 30%, Cured, 17 mph): fuel moisture 3.5 (X row rule)", r['fine_fuel_moisture'] == 3.5)
check("Ben #3: spread index 75, class 5", r['spread_index'] == 75 and r['fire_class'] == 5)

# ---- temperature boxes
for t, col in [(109, 0), (100, 0), (110, 0), (140, 0), (99, 1), (90, 1), (89, 2), (82.9, 2), (80, 2),
               (79, 3), (60, 4), (50, 5), (40, 6), (30, 7), (29, 8), (20, 8), (19, 9), (10, 9), (5, 9), (-10, 9)]:
    check("%sF falls in temperature box %d" % (t, col), cd.temp_column(t) == col)

# ---- every temperature and humidity has an answer, for every stage
bad = []
for t in range(-20, 131):
    for rh in range(0, 101):
        for stage in cd.STAGES:
            try:
                cd.fine_fuel_moisture(t, rh, stage)
            except Exception as e:
                bad.append((t, rh, stage, str(e)))
check("every temperature 0-130F x humidity 0-100% x stage has an answer", bad == [])
check("fractional humidity rounds (42.4 -> 42, 42.6 -> 43)",
      cd.chart_a_rows(82, 42.4) == cd.chart_a_rows(82, 42) and cd.chart_a_rows(82, 42.6) == cd.chart_a_rows(82, 43))
check("humidity above 100 or below 0 is held to the chart", cd.chart_a_rows(82, 104) == cd.chart_a_rows(82, 100)
      and cd.chart_a_rows(82, -3) == cd.chart_a_rows(82, 0))

# ---- the X rule gives a real number everywhere
odd = []
for t in range(10, 111, 5):
    for rh in range(0, 101):
        for stage in cd.STAGES:
            fm = cd.fine_fuel_moisture(t, rh, stage)
            if fm != '30+' and not (0.5 <= fm <= 30):
                odd.append((t, rh, stage, fm))
check("fuel moisture is always a sensible number (never X, never out of range)", odd == [])

# ---- sense checks: drier air never gives wetter fuel; more wind never lowers the index
def fm_num(v):
    return 31.0 if v == '30+' else v


violations = []
for t in (15, 25, 35, 45, 55, 65, 75, 85, 95, 105):
    for stage in cd.STAGES:
        previous = None
        for rh in range(100, -1, -1):
            fm = fm_num(cd.fine_fuel_moisture(t, rh, stage))
            if previous is not None and fm > previous + 0.51:
                violations.append((t, stage, rh, previous, fm))
            previous = fm
check("drier air never gives wetter fuel (any temperature, any stage)", violations == [])
check("a warmer day never gives wetter fuel at the same humidity (cured, 40%)",
      all(fm_num(cd.fine_fuel_moisture(t + 10, 40, 'cured')) <= fm_num(cd.fine_fuel_moisture(t, 40, 'cured')) + 0.01
          for t in range(15, 100, 10)))
check("greener fuel is never drier than cured (same air)",
      all(fm_num(cd.fine_fuel_moisture(t, rh, 'green')) >= fm_num(cd.fine_fuel_moisture(t, rh, 'cured')) - 0.01
          for t in range(15, 106, 10) for rh in range(0, 101, 5)))
check("spread index never falls as wind rises",
      all(cd.spread_index(fm, w) <= cd.spread_index(fm, w + 1) for fm in ('30+', 25, 15, 10, 5, 1) for w in range(0, 40)))

# ---- Chart D row and column lookups
for fm, label in [('30+', '30+'), (30, '29-30'), (29, '29-30'), (28, '27-28'), (27, '27-28'), (26, '25-26'),
                  (25, '25-26'), (24, '23-24'), (22, '21-22'), (20, '19-20'), (18, '17-18'), (16, '15-16'),
                  (15, '15-16'), (14, '14'), (13, '13'), (12, '12'), (11, '11'), (10, '10'), (9.5, '9.5'),
                  (9, '9'), (8.5, '8.5'), (5, '5'), (3.5, '3.5'), (1, '1')]:
    check("fuel moisture %s uses Chart D row %s" % (fm, label), cd.CHART_D_LABELS[cd.chart_d_row(fm)] == label)
for w, label in [(0, '0-1'), (1, '0-1'), (1.4, '0-1'), (1.5, '2'), (2, '2'), (5, '5'), (10, '10'), (10.4, '10'),
                 (11, '11-12'), (12, '11-12'), (13, '13-15'), (15, '13-15'), (16, '16-19'), (19, '16-19'),
                 (20, '20-24'), (24, '20-24'), (25, '25-29'), (29, '25-29'), (30, '30+'), (80, '30+')]:
    check("wind %s mph uses column %s" % (w, label), cd.WIND_COLUMNS[cd.wind_column(w)] == label)
for fm, wind, si in [(13, 8, 23), (10, 14, 42), (29, 5, 1), (3, 17, 77)]:
    check("Chart D: fuel moisture %s at %s mph = %s (checked against Ben's paper)" % (fm, wind, si),
          cd.spread_index(fm, wind) == si)

# ---- classes
for si, cls in [(1, 1), (4, 1), (5, 2), (9, 2), (10, 3), (19, 3), (20, 4), (39, 4), (40, 5), (100, 5)]:
    check("spread index %d is class %d" % (si, cls), cd.fire_class(si) == cls)
check("class 1-5 map to LOW..EXTREME",
      [cd.CLASS_LEVELS[i] for i in range(1, 6)] == ['LOW', 'MODERATE', 'HIGH', 'VERY_HIGH', 'EXTREME'])
check("every level has a dashboard message", all(cd.CLASS_LEVELS[i] in cd.MESSAGES for i in range(1, 6)))

# ---- no wind data
r = cd.assess(20.0, 40, None, 'transition')
check("no wind: fuel moisture still worked out", r['fine_fuel_moisture'] is not None)
check("no wind: no spread index, no class, no level", r['spread_index'] is None and r['fire_class'] is None and r['level'] is None)
check("no wind: flagged as needing wind data", r['needs_wind'] is True)
check("calm wind (0 mph) is NOT 'no wind data'", cd.assess(20.0, 40, 0, 'transition')['needs_wind'] is False)
try:
    cd.assess(20.0, 40, 5, 'sprouting')
    refused = False
except ValueError:
    refused = True
check("an unknown herbaceous stage is refused", refused)

print(f"\n{passed} passed, {failed} failed")
raise SystemExit(1 if failed else 0)
