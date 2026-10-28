# IoT Rule: SELECT * FROM 'esp32/ask/request'  ->  this Lambda
# The execution role needs bedrock:InvokeModel, and model access must be enabled.
import json
import boto3

iot = boto3.client("iot-data")
bedrock = boto3.client("bedrock-runtime")
MODEL = "jp.anthropic.claude-haiku-4-5-20251001-v1:0"


def lambda_handler(event, context):
    text = event["prompt"] + "\n\nData:\n" + event["data"]
    res = bedrock.converse(
        modelId=MODEL,
        messages=[{"role": "user", "content": [{"text": text}]}],
        inferenceConfig={"maxTokens": 1024},
    )
    answer = res["output"]["message"]["content"][0]["text"]
    iot.publish(topic="esp32/ask/reply", qos=0, payload=json.dumps({"answer": answer}))
