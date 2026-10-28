# Used by the fault-injection test (evaluation/e9_faults): fails the way a user's
# function with a bug would, so that the device shows the function's message.


def run(input):
    raise ValueError("the sensor value is missing")
