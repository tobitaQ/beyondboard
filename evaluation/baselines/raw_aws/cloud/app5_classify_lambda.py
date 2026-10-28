# IoT Rule: SELECT * FROM 'esp32/classify/request'  ->  this Lambda
# The execution role needs bedrock:InvokeModel and s3:PutObject.
import json
import time
import boto3

iot = boto3.client("iot-data")
s3 = boto3.client("s3")
bedrock = boto3.client("bedrock-runtime")
MODEL = "jp.anthropic.claude-haiku-4-5-20251001-v1:0"
BUCKET = "my-esp32-bucket"
LABELS = ["normal", "warning", "danger"]


def lambda_handler(event, context):
    prompt = (
        "How safe is this temperature for a server room? Reply with exactly one of: "
        + ", ".join(LABELS)
        + "\n\nData:\n"
        + event["data"]
    )
    label = "unknown"
    for _ in range(2):
        res = bedrock.converse(
            modelId=MODEL,
            messages=[{"role": "user", "content": [{"text": prompt}]}],
            inferenceConfig={"maxTokens": 20},
        )
        answer = res["output"]["message"]["content"][0]["text"].strip().lower()
        if answer in LABELS:
            label = answer
            break
    key = f"status/{int(time.time() * 1000)}.json"
    s3.put_object(Bucket=BUCKET, Key=key, Body=json.dumps({"data": event["data"], "label": label}))
    iot.publish(topic="esp32/classify/reply", qos=0, payload=json.dumps({"label": label}))
