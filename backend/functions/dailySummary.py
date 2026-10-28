# aws.run("dailySummary", "temp.csv") -> a one-line summary of what was saved.
#
# An example of the bottom level: this function calls cloud services itself
# (DynamoDB and a different Bedrock model), so it goes outside the contract and
# works on aws only. Its permissions are in settings.json "functions".
import json
import statistics

import boto3

MODEL = "jp.amazon.nova-2-lite-v1:0"


def run(input, context):
    if context["destination"] != "aws":
        return "dailySummary only works on aws (it reads the cloud database)."
    table = boto3.resource("dynamodb").Table(context["table"])
    items = table.query(
        KeyConditionExpression="pk = :pk",
        ExpressionAttributeValues={":pk": f"REC#{context['device']}#{input}"},
        ScanIndexForward=False,
        Limit=100,
    )["Items"]
    values = [float(i["v"]) for i in items]
    if not values:
        return f"No data in {input}."
    stats = {
        "count": len(values),
        "min": min(values),
        "max": max(values),
        "mean": round(statistics.mean(values), 2),
    }
    res = boto3.client("bedrock-runtime").converse(
        modelId=MODEL,
        messages=[{"role": "user", "content": [{"text": (
            "Summarize these temperature statistics in one short sentence: " + json.dumps(stats)
        )}]}],
        inferenceConfig={"maxTokens": 100},
    )
    return res["output"]["message"]["content"][0]["text"].strip()
