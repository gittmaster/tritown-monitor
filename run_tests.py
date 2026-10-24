"""Run every offline test script and print one summary.

Usage:  python run_tests.py

Each test_*.py is a plain script that prints a line like "12 passed, 0 failed".
The scripts exit with success even when a check fails, so this runner reads
that line instead of trusting the exit code.

test_live_forecast.py is skipped because it needs the real internet.
test_alerts.py has one known, documented failure (see README).
"""
import glob
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SKIP = {"test_live_forecast.py"}
KNOWN_FAILURES = {"test_alerts.py": 1}

total_pass = 0
total_fail = 0
unexpected = []

for path in sorted(glob.glob(os.path.join(HERE, "test_*.py"))):
    name = os.path.basename(path)
    if name in SKIP:
        print("%-36s skipped (needs internet)" % name)
        continue
    try:
        run = subprocess.run([sys.executable, path], cwd=HERE, capture_output=True,
                             text=True, timeout=300)
        out = (run.stdout or "") + (run.stderr or "")
    except subprocess.TimeoutExpired:
        print("%-36s TIMED OUT" % name)
        unexpected.append(name)
        continue
    found = re.findall(r"(\d+)\s+passed,\s+(\d+)\s+failed", out)
    if not found:
        print("%-36s NO RESULT LINE (exit code %s)" % (name, run.returncode))
        unexpected.append(name)
        continue
    passed, failed = (int(x) for x in found[-1])
    total_pass += passed
    total_fail += failed
    note = ""
    if failed:
        if failed == KNOWN_FAILURES.get(name):
            note = "  (known failure, see README)"
        else:
            unexpected.append(name)
            note = "  <-- UNEXPECTED"
    print("%-36s %3d passed, %d failed%s" % (name, passed, failed, note))

print("-" * 60)
print("TOTAL: %d passed, %d failed" % (total_pass, total_fail))
if unexpected:
    print("Needs attention: " + ", ".join(unexpected))
    sys.exit(1)
print("All as expected.")
