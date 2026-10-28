# Function for App 3 on AWS Lambda (Python, function URL). The sketch posts a
# temperature as text; the function returns "anomaly" or "normal".
import base64

LIMIT = 30.0


def lambda_handler(event, context):
    body = event.get("body") or ""
    if event.get("isBase64Encoded"):
        body = base64.b64decode(body).decode()
    temperature = float(body)
    result = "anomaly" if temperature > LIMIT else "normal"
    return {"statusCode": 200, "headers": {"Content-Type": "text/plain"}, "body": result}
