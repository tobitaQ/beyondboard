# IoT Rule: SELECT * FROM 'esp32/anomaly/request'  ->  this Lambda
import json
import boto3

iot = boto3.client("iot-data")
LIMIT = 30.0


def lambda_handler(event, context):
    result = "anomaly" if float(event["temp"]) > LIMIT else "normal"
    iot.publish(topic="esp32/anomaly/reply", qos=0, payload=json.dumps({"result": result}))
