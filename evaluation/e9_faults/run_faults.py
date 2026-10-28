"""Run FaultTable: reset the board, record its lines, revoke the device's token
when it prints WAITING, then let it make one more call.

Usage: python3 run_faults.py PORT DEVICE OUT   (needs pyserial; local/.venv has it)
"""
import re
import subprocess
import sys
import time

import serial

port, device, out = sys.argv[1], sys.argv[2], sys.argv[3]


def mask(line):
    """Keep the user's own Wi-Fi name out of the output."""
    return re.sub(r'Wi-Fi "(?!no-such-wifi-beyondboard")[^"]*"', 'Wi-Fi "<your Wi-Fi>"', line)


s = serial.Serial(port, 115200, timeout=1)
s.dtr = False
s.rts = True
time.sleep(0.2)
s.rts = False
lines, started, end = [], False, time.time() + 600
while time.time() < end:
    line = s.readline().decode(errors="replace").rstrip("\r\n")
    if not line:
        continue
    print(mask(line), flush=True)
    if line == "BEGIN":
        started, lines = True, []
    elif line == "WAITING":
        subprocess.run(["npm", "run", "revoke", "--", device], cwd="../../backend", check=True)
        time.sleep(2)
        s.write(b"go\n")
    elif line == "END" and started:
        break
    elif started:
        lines.append(line)
with open(out, "w") as f:
    f.write("\n".join(mask(l) for l in lines) + "\n")
