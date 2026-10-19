"""
The fire chief's "class day" fire danger method, as used on paper.

  1. Chart A  - air temperature + relative humidity + herbaceous stage
                (Cured / Transition / Green) give the FINE FUEL MOISTURE.
  2. Chart D  - fine fuel moisture + wind speed (20-foot standard) give the
                SPREAD INDEX.
  3. Spread index -> class 1 to 5.

The two charts are typed in below exactly as printed, row by row, so they can
be checked against the paper copy. validate_tables() proves the typing is
self-consistent (used by the tests). Nothing here touches the network or the
database, and nothing in the live site uses it unless ALERT_METHOD=class_day.

ASSUMPTIONS (decided by us; listed in the presentation; easy to change):
  * grass stage is Transition until the district announces a change (HERBACEOUS_STAGE)
  * wind is rounded to the nearest whole mph and averaged over 30 seconds
  * the chart expects 20-foot winds; the sensor reading is used as is
  * classes 1 to 5 are shown as Low, Moderate, High, Very High, Extreme
  * with no wind reading, the original rule is used and the message says so
  * a printed row marked X uses the repeated row next to it, as the chart note says
"""

# ---------------------------------------------------------------- Chart A
# Temperature columns, left to right as printed (degrees F).
TEMP_BANDS = [(100, 109), (90, 99), (80, 89), (70, 79), (60, 69),
              (50, 59), (40, 49), (30, 39), (20, 29), (10, 19)]

# 39 printed rows, top to bottom. One entry per temperature column; '' is an
# empty box on the paper. "95+" means 95 to 100. Rows that are printed twice
# on purpose (see the X rule) are listed twice.
CHART_A_ROWS = [
    ['100', '100', '100', '100', '100', '100', '95+', '95+', '95+', '90+'],            # 1
    ['', '', '95-99', '95-99', '95-99', '95-99', '90-94', '90-94', '85-94', '80-89'],   # 2
    ['', '95-99', '', '', '', '', '', '85-89', '80-84', '75-79'],                       # 3
    ['', '', '', '', '', '90-94', '', '', '', '70-74'],                                 # 4
    ['', '', '', '', '', '', '85-89', '80-84', '75-79', '65-69'],                       # 5
    ['95-99', '', '', '', '90-94', '', '', '', '', '60-64'],                            # 6
    ['', '', '', '90-94', '', '85-89', '', '75-79', '70-74', ''],                       # 7
    ['', '', '90-94', '', '85-89', '', '80-84', '', '65-69', '55-59'],                  # 8
    ['', '', '', '', '', '80-84', '75-79', '70-74', '', ''],                            # 9
    ['', '90-94', '', '85-89', '', '', '', '65-69', '60-64', '50-54'],                  # 10
    ['', '', '85-89', '', '80-84', '75-79', '70-74', '', '55-59', '45-49'],             # 11
    ['90-94', '', '', '80-84', '75-79', '70-74', '65-69', '60-64', '50-54', '40-44'],   # 12
    ['', '85-89', '', '', '', '65-69', '60-64', '55-59', '45-49', '35-39'],             # 13
    ['', '', '80-84', '75-79', '70-74', '', '55-59', '50-54', '40-44', '30-34'],        # 14
    ['', '', '75-79', '70-74', '65-69', '60-64', '', '45-49', '', ''],                  # 15
    ['85-89', '80-84', '', '', '60-64', '55-59', '50-54', '40-44', '35-39', '25-29'],   # 16
    ['', '75-79', '70-74', '65-69', '', '50-54', '45-49', '35-39', '30-34', '20-24'],   # 17
    ['', '75-79', '70-74', '65-69', '', '50-54', '45-49', '35-39', '30-34', '20-24'],   # 18 (repeat of 17)
    ['80-84', '', '', '60-64', '55-59', '45-49', '40-44', '30-34', '25-29', '15-19'],   # 19
    ['', '70-74', '65-69', '', '50-54', '40-44', '35-39', '25-29', '20-24', '10-14'],   # 20
    ['75-79', '', '60-64', '55-59', '45-49', '', '30-34', '', '15-19', ''],             # 21
    ['', '65-69', '', '50-54', '40-44', '35-39', '25-29', '20-24', '', '5-9'],          # 22
    ['70-74', '', '55-59', '45-49', '', '30-34', '', '15-19', '10-14', ''],             # 23
    ['', '60-64', '50-54', '', '35-39', '25-29', '20-24', '', '', ''],                  # 24
    ['', '60-64', '50-54', '', '35-39', '25-29', '20-24', '', '', ''],                  # 25 (repeat of 24)
    ['65-69', '55-59', '45-49', '40-44', '30-34', '', '15-19', '10-14', '5-9', '0-4'],  # 26
    ['60-64', '', '', '35-39', '25-29', '20-24', '', '', '', ''],                       # 27
    ['55-59', '45-54', '35-44', '30-34', '20-24', '15-19', '10-14', '5-9', '0-4', ''],  # 28
    ['50-54', '40-44', '30-34', '25-29', '15-19', '10-14', '', '', '', ''],             # 29
    ['50-54', '40-44', '30-34', '25-29', '15-19', '10-14', '', '', '', ''],             # 30 (repeat of 29)
    ['45-49', '35-39', '25-29', '20-24', '10-14', '', '5-9', '0-4', '', ''],            # 31
    ['35-44', '30-34', '20-24', '15-19', '', '5-9', '', '', '', ''],                    # 32
    ['35-44', '30-34', '20-24', '15-19', '', '5-9', '', '', '', ''],                    # 33 (repeat of 32)
    ['25-34', '20-29', '15-19', '10-14', '5-9', '', '0-4', '', '', ''],                 # 34
    ['20-24', '15-19', '10-14', '5-9', '', '0-4', '', '', '', ''],                      # 35
    ['20-24', '15-19', '10-14', '5-9', '', '0-4', '', '', '', ''],                      # 36 (repeat of 35)
    ['10-19', '10-14', '5-9', '', '0-4', '', '', '', '', ''],                           # 37
    ['5-9', '5-9', '', '0-4', '', '', '', '', '', ''],                                  # 38
    ['0-4', '0-4', '0-4', '', '', '', '', '', '', ''],                                  # 39
]

# The right-hand "Fine Fuel Moisture" window: one entry per row above.
# ('30+' means 30 or more; 'X' means "no value here, use the repeated row".)
STAGES = ('cured', 'transition', 'green')
HERBACEOUS_ROWS = [
    ('30+', '30+', '30+'), ('25', '30', '30+'), ('23', '28', '30+'), ('22', '27', '30+'),
    ('21', '26', '30+'), ('20', '25', '30'), ('19', '24', '29'), ('18', '23', '28'),
    ('17', '22', '27'), ('16', '21', '26'), ('15', '20', '25'), ('14', '19', '24'),
    ('13', '18', '23'), ('12', '17', '22'), ('11', '16', '21'), ('10', '15', '20'),
    ('X', '15', '20'), ('9.5', 'X', 'X'), ('9', '14', '19'), ('8.5', '14', '19'),
    ('8', '13', '18'), ('7.5', '13', '18'), ('7', '12', '17'), ('X', '12', '17'),
    ('6.5', 'X', 'X'), ('6', '11', '16'), ('5.5', '11', '16'), ('5', '10', '15'),
    ('X', 'X', '15'), ('4.5', '9.5', 'X'), ('4', '9', '14'), ('X', 'X', '14'),
    ('3.5', '8.5', 'X'), ('3', '8', '13'), ('X', 'X', '13'), ('2.5', '7.5', 'X'),
    ('2', '7', '12'), ('1.5', '6.5', '12'), ('1', '6', '11'),
]

# ---------------------------------------------------------------- Chart D
# Wind columns as printed (mph): 0-1, 2..10 one by one, then ranges.
WIND_COLUMNS = ['0-1', '2', '3', '4', '5', '6', '7', '8', '9', '10',
                '11-12', '13-15', '16-19', '20-24', '25-29', '30+']

# Fuel moisture rows as printed (top to bottom) and their spread indexes.
CHART_D_LABELS = ['30+', '29-30', '27-28', '25-26', '23-24', '21-22', '19-20', '17-18',
                  '15-16', '14', '13', '12', '11', '10'] + \
                 ['%g' % (9.5 - 0.5 * i) for i in range(18)]      # 9.5 down to 1
CHART_D = [
    [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],              # 30+
    [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2, 3, 4, 5, 6],              # 29-30
    [1, 1, 1, 1, 1, 1, 1, 1, 1, 2, 3, 4, 5, 6, 8, 9],              # 27-28
    [1, 1, 1, 1, 2, 2, 2, 3, 3, 4, 6, 7, 8, 9, 11, 13],            # 25-26
    [1, 2, 3, 3, 4, 4, 5, 6, 7, 7, 8, 10, 11, 13, 15, 17],         # 23-24
    [2, 3, 4, 5, 6, 7, 8, 8, 9, 10, 11, 13, 15, 17, 20, 22],       # 21-22
    [4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 15, 17, 19, 22, 25, 29],    # 19-20
    [6, 8, 9, 10, 11, 12, 13, 14, 15, 16, 18, 21, 24, 28, 32, 36],  # 17-18
    [8, 10, 11, 12, 14, 15, 17, 18, 19, 20, 22, 26, 30, 34, 39, 44],  # 15-16
    [9, 11, 12, 14, 16, 18, 20, 21, 22, 23, 26, 30, 34, 39, 44, 51],  # 14
    [10, 12, 14, 16, 18, 20, 21, 23, 25, 26, 28, 33, 37, 43, 48, 56],  # 13
    [11, 13, 15, 17, 19, 21, 23, 25, 27, 28, 31, 36, 41, 47, 53, 62],  # 12
    [12, 15, 17, 19, 21, 23, 25, 27, 29, 31, 34, 39, 44, 51, 58, 68],  # 11
    [13, 16, 18, 20, 22, 25, 27, 29, 31, 33, 37, 42, 48, 56, 63, 73],  # 10
    [14, 17, 19, 21, 23, 26, 28, 30, 33, 35, 38, 44, 50, 58, 66, 76],  # 9.5
    [14, 17, 20, 22, 24, 27, 29, 32, 34, 36, 40, 46, 52, 60, 68, 79],  # 9
    [15, 18, 21, 23, 25, 28, 30, 33, 36, 38, 42, 47, 54, 63, 71, 83],  # 8.5
    [15, 19, 22, 24, 26, 29, 31, 34, 37, 39, 43, 49, 56, 65, 74, 86],  # 8
    [16, 19, 22, 25, 28, 30, 33, 35, 38, 40, 45, 51, 58, 67, 76, 89],  # 7.5
    [17, 20, 23, 25, 28, 31, 34, 37, 39, 42, 46, 53, 60, 69, 79, 93],  # 7
    [17, 21, 24, 26, 29, 32, 35, 38, 40, 43, 48, 54, 62, 72, 82, 96],  # 6.5
    [18, 22, 25, 27, 30, 34, 37, 39, 42, 45, 50, 56, 64, 74, 85, 99],  # 6
    [18, 22, 25, 28, 31, 35, 38, 41, 44, 47, 51, 58, 66, 77, 88, 100],  # 5.5
    [19, 23, 26, 29, 32, 36, 39, 42, 46, 48, 53, 60, 69, 79, 91, 100],  # 5
    [20, 24, 27, 30, 33, 37, 40, 43, 47, 50, 55, 62, 71, 82, 94, 100],  # 4.5
    [21, 24, 28, 31, 34, 38, 41, 45, 48, 51, 57, 64, 73, 84, 97, 100],  # 4
    [21, 25, 29, 32, 35, 39, 42, 46, 49, 53, 58, 66, 75, 87, 100, 100],  # 3.5
    [22, 26, 30, 33, 36, 40, 43, 47, 50, 54, 60, 68, 77, 89, 100, 100],  # 3
    [23, 27, 31, 34, 38, 42, 45, 49, 52, 56, 62, 70, 80, 92, 100, 100],  # 2.5
    [24, 28, 32, 35, 39, 43, 46, 50, 54, 58, 64, 72, 82, 94, 100, 100],  # 2
    [24, 28, 32, 36, 40, 44, 48, 52, 56, 60, 65, 74, 84, 97, 100, 100],  # 1.5
    [25, 29, 33, 37, 41, 45, 49, 53, 57, 61, 67, 76, 86, 100, 100, 100],  # 1
]

# Spread index -> class (1 to 5), as the fire chief gave them.
CLASS_LIMITS = [(1, 4, 1), (5, 9, 2), (10, 19, 3), (20, 39, 4), (40, 100, 5)]
# Names used by the dashboard. ASSUMPTION until the fire department confirms.
CLASS_LEVELS = {1: 'LOW', 2: 'MODERATE', 3: 'HIGH', 4: 'VERY_HIGH', 5: 'EXTREME'}


def _parse_range(text):
    """'35-44' -> (35, 44);  '95+' -> (95, 100);  '100' -> (100, 100)."""
    if text.endswith('+'):
        return int(text[:-1]), 100
    if '-' in text:
        lo, hi = text.split('-')
        return int(lo), int(hi)
    return int(text), int(text)


def _column_cells():
    """For each temperature column: [(low RH, high RH, printed row index), ...]."""
    columns = [[] for _ in TEMP_BANDS]
    for row_index, row in enumerate(CHART_A_ROWS):
        for col, text in enumerate(row):
            if text:
                lo, hi = _parse_range(text)
                columns[col].append((lo, hi, row_index))
    return columns


_COLUMNS = _column_cells()


def temp_column(temp_f):
    """Which of the ten printed temperature columns a temperature falls in."""
    t = int(temp_f // 1)                      # 82.9 is still in the 80-89 box
    if t >= 100:
        return 0                              # 100-109, and anything hotter
    if t < 20:
        return len(TEMP_BANDS) - 1            # 10-19, and anything colder
    return (109 - t) // 10


def _round_half_up(x):
    return int(x + 0.5)


def chart_a_rows(temp_f, rh):
    """The printed row number(s) (0-based) for this temperature and humidity.
    Two numbers when the box is printed twice (the X-row pairs)."""
    col = temp_column(temp_f)
    humidity = min(100, max(0, _round_half_up(rh)))
    rows = [r for lo, hi, r in _COLUMNS[col] if lo <= humidity <= hi]
    if not rows:
        raise ValueError('humidity %s not on chart for temperature %s' % (rh, temp_f))
    return rows


def _fm_value(text):
    return text if text == '30+' else float(text)


def fine_fuel_moisture(temp_f, rh, stage):
    """Chart A. Returns '30+' or a number such as 10 or 3.5."""
    if stage not in STAGES:
        raise ValueError('stage must be one of %s' % (STAGES,))
    s = STAGES.index(stage)
    row = chart_a_rows(temp_f, rh)[0]
    value = HERBACEOUS_ROWS[row][s]
    if value == 'X':
        # "Move one line up or down, holding the same humidity": the box is
        # printed twice, so the neighbouring row with the same boxes has the answer.
        for neighbour in (row + 1, row - 1):
            if 0 <= neighbour < len(CHART_A_ROWS) and CHART_A_ROWS[neighbour] == CHART_A_ROWS[row]:
                value = HERBACEOUS_ROWS[neighbour][s]
                break
    if value == 'X':
        raise ValueError('no fuel moisture on chart at row %d' % (row + 1))
    return _fm_value(value)


def chart_d_row(fm):
    """Index of the Chart D row for a fuel moisture value."""
    if fm == '30+':
        return 0
    fm = float(fm)
    for index, floor in enumerate((29, 27, 25, 23, 21, 19, 17, 15, 14, 13, 12, 11, 10), start=1):
        if fm >= floor:
            return index
    fm = max(1.0, fm)
    return 14 + int(round((9.5 - round(fm * 2) / 2.0) * 2))


def wind_column(wind_mph):
    """Chart D column for a wind speed (rounded to the nearest whole mph)."""
    w = _round_half_up(max(0.0, float(wind_mph)))
    if w <= 1:
        return 0
    if w <= 10:
        return w - 1
    if w <= 12:
        return 10
    if w <= 15:
        return 11
    if w <= 19:
        return 12
    if w <= 24:
        return 13
    if w <= 29:
        return 14
    return 15


def spread_index(fm, wind_mph):
    """Chart D."""
    return CHART_D[chart_d_row(fm)][wind_column(wind_mph)]


def fire_class(si):
    for lo, hi, cls in CLASS_LIMITS:
        if lo <= si <= hi:
            return cls
    return 5 if si > 100 else 1


MESSAGES = {
    'LOW': 'LOW - Wildfire ignitions unlikely. Outdoor burning is safest.',
    'MODERATE': 'MODERATE - Wildfires may occur. Restrict burning to early morning or late evening.',
    'HIGH': 'HIGH - Wildfires ignite easily. Outdoor burning strongly discouraged!',
    'VERY_HIGH': 'VERY HIGH - Fires start easily and spread rapidly. No outdoor burning!',
    'EXTREME': 'EXTREME - Every fire could become large. No burning. Call 911 immediately!',
}


def assess(temp_c, rh, wind_mph, stage='transition'):
    """Full class-day answer for one reading.
    wind_mph=None means there is no wind data: fuel moisture is still worked out,
    but no spread index or class is (needs_wind=True)."""
    temp_f = temp_c * 9.0 / 5.0 + 32.0
    fm = fine_fuel_moisture(temp_f, rh, stage)
    result = {'temp_f': round(temp_f, 1), 'stage': stage, 'fine_fuel_moisture': fm,
              'needs_wind': wind_mph is None, 'spread_index': None, 'fire_class': None,
              'level': None, 'message': None}
    if wind_mph is None:
        return result
    si = spread_index(fm, wind_mph)
    cls = fire_class(si)
    result.update(spread_index=si, fire_class=cls, level=CLASS_LEVELS[cls],
                  message=MESSAGES[CLASS_LEVELS[cls]])
    return result


def validate_tables():
    """Self-checks on the typed-in charts. Returns a list of problems (empty = fine)."""
    problems = []
    if len(CHART_A_ROWS) != 39:
        problems.append('Chart A should have 39 rows, has %d' % len(CHART_A_ROWS))
    if len(HERBACEOUS_ROWS) != len(CHART_A_ROWS):
        problems.append('herbaceous window has %d rows, Chart A has %d'
                        % (len(HERBACEOUS_ROWS), len(CHART_A_ROWS)))
    for i, row in enumerate(CHART_A_ROWS):
        if len(row) != len(TEMP_BANDS):
            problems.append('Chart A row %d has %d boxes' % (i + 1, len(row)))
    # each temperature column must cover humidity 0..100 once, with no gap or overlap
    for col, cells in enumerate(_COLUMNS):
        ranges = []
        for lo, hi, row in cells:
            if (lo, hi) not in [(a, b) for a, b, _ in ranges]:
                ranges.append((lo, hi, row))
        ranges.sort()
        expected = 0
        for lo, hi, _ in ranges:
            if lo != expected:
                problems.append('temperature column %s: humidity gap/overlap at %d (expected %d)'
                                % (TEMP_BANDS[col], lo, expected))
            expected = hi + 1
        if expected != 101:
            problems.append('temperature column %s does not reach 100' % (TEMP_BANDS[col],))
        # printed from high humidity at the top to low at the bottom
        order = [lo for lo, hi, row in sorted(cells, key=lambda c: c[2])]
        if order != sorted(order, reverse=True):
            problems.append('temperature column %s: humidity does not fall going down' % (TEMP_BANDS[col],))
    # the X rule: every X must have an identical neighbouring row to move to
    for i, values in enumerate(HERBACEOUS_ROWS):
        for s, value in enumerate(values):
            if value == 'X':
                ok = any(0 <= n < len(CHART_A_ROWS) and CHART_A_ROWS[n] == CHART_A_ROWS[i]
                         and HERBACEOUS_ROWS[n][s] != 'X' for n in (i + 1, i - 1))
                if not ok:
                    problems.append('row %d %s is X with no repeated row to move to' % (i + 1, STAGES[s]))
    # Chart D: right shape, never falls as wind rises or fuel gets drier
    if len(CHART_D) != len(CHART_D_LABELS):
        problems.append('Chart D has %d rows but %d labels' % (len(CHART_D), len(CHART_D_LABELS)))
    for r, row in enumerate(CHART_D):
        if len(row) != len(WIND_COLUMNS):
            problems.append('Chart D row %s has %d columns' % (CHART_D_LABELS[r], len(row)))
        if row != sorted(row):
            problems.append('Chart D row %s falls as wind rises' % CHART_D_LABELS[r])
    for c in range(len(WIND_COLUMNS)):
        column = [row[c] for row in CHART_D]
        if column != sorted(column):
            problems.append('Chart D column %s falls as fuel gets drier' % WIND_COLUMNS[c])
    return problems
