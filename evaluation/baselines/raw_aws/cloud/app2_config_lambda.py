# IoT Rule: SELECT * FROM 'esp32/config/get'  ->  this Lambda
import json
import boto3

s3 = boto3.client("s3")
iot = boto3.client("iot-data")
BUCKET = "my-esp32-bucket"


def lambda_handler(event, context):
    obj = s3.get_object(Bucket=BUCKET, Key=event["name"])
    text = obj["Body"].read().decode("utf-8")
    iot.publish(topic="esp32/config/reply", qos=0, payload=json.dumps({"config": text}))
