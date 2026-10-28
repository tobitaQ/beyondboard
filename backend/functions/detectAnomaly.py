# aws.run("detectAnomaly", "38.2") calls this function in the cloud.
# `input` is the text sent from the device. Return the text to send back.

LIMIT = 30.0  # degrees Celsius


def run(input):
    temperature = float(input)
    if temperature > LIMIT:
        return "anomaly"
    return "normal"
