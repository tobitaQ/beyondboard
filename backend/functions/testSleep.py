# Used by the conformance tests: waits `input` seconds, then answers "done".
import time


def run(input):
    time.sleep(float(input or 0))
    return "done"
