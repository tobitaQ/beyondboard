"""Reset the board and save what it prints between BEGIN and END.

Usage: python3 capture.py PORT OUT_PREFIX [passes] [timeout_s]
Writes OUT_PREFIX_pass1.txt, ... (needs pyserial; local/.venv has it).
"""
import sys
import time

import serial


def capture(port, timeout):
    s = serial.Serial(port, 115200, timeout=1)
    s.dtr = False
    s.rts = True
    time.sleep(0.2)
    s.rts = False
    lines, started, end = [], False, time.time() + timeout
    while time.time() < end:
        line = s.readline().decode(errors="replace").rstrip("\r\n")
        if line == "BEGIN":
            started, lines = True, []
        elif line == "END" and started:
            s.close()
            return lines
        elif started:
            lines.append(line)
    s.close()
    raise TimeoutError("no END within %d s; got %d lines" % (timeout, len(lines)))


def main():
    port, prefix = sys.argv[1], sys.argv[2]
    passes = int(sys.argv[3]) if len(sys.argv) > 3 else 3
    timeout = int(sys.argv[4]) if len(sys.argv) > 4 else 600
    for n in range(1, passes + 1):
        lines = capture(port, timeout)
        with open(f"{prefix}_pass{n}.txt", "w") as f:
            f.write("\n".join(lines) + "\n")
        print(f"pass {n}: {len(lines)} lines")


if __name__ == "__main__":
    main()
