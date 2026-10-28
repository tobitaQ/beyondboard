"""Wraps a user's functions/<name>.py so that users only write

    def run(input):
        return "result"

`input` is the string sent by aws.run(name, input); the return value is sent
back to the device as a string.

A function may also take a second argument, `context`, with "device" (who
called) and "destination" ("aws" or "local"). Functions that call other cloud
services this way go outside the contract (the bottom level), so they may only
work on one destination; permissions are given in settings.json "functions".
"""

import inspect
import os

import user_function

TAKES_CONTEXT = len(inspect.signature(user_function.run).parameters) >= 2


def handler(event, context):
    if TAKES_CONTEXT:
        info = {"device": event.get("device", ""), "destination": "aws",
                "table": os.environ.get("TABLE", ""), "bucket": os.environ.get("BUCKET", "")}
        result = user_function.run(event.get("input", ""), info)
    else:
        result = user_function.run(event.get("input", ""))
    if result is None:
        result = ""
    return {"output": str(result)}
