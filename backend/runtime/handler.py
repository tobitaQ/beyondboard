"""AWS adapter: the entry point the device talks to (POST /v1/{ping,save,load,run,ask}).

The contract itself lives in core.py. This file only says where things go on
AWS: records in DynamoDB, files in S3, functions in Lambda, the AI in Bedrock.
Every response is HTTP 200 with {"ok", "code", "error", "result"}.
"""

import base64
import hashlib
import json
import os
import uuid
from datetime import datetime, timedelta, timezone

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError, ReadTimeoutError

from core import (
    ERR_LIMIT,
    ERR_NOT_FOUND,
    ERR_RUN_FAILED,
    ERR_SERVER,
    ERR_TIMEOUT,
    Adapter,
    CloudError,
    Core,
)

CALL_LOG_DAYS = 90


class AwsAdapter(Adapter):
    def __init__(self):
        self.table = boto3.resource("dynamodb").Table(os.environ["TABLE"])
        self.s3 = boto3.client("s3")
        self.bedrock = boto3.client("bedrock-runtime")
        self.bucket = os.environ["BUCKET"]
        self.functions = json.loads(os.environ.get("FUNCTIONS", "{}"))
        self.model = os.environ["ASK_MODEL"]
        self.daily_limit = int(os.environ["ASK_DAILY_LIMIT"])
        self.ask_max_chars = int(os.environ["ASK_MAX_CHARS"])

    def authenticate(self, token):
        if not token:
            return None
        digest = hashlib.sha256(token.encode()).hexdigest()
        item = self.table.get_item(Key={"pk": f"TOKEN#{digest}", "sk": "META"}).get("Item")
        return item["device"] if item else None

    def append(self, device, name, ts, request_id, value):
        self.table.put_item(
            Item={"pk": f"REC#{device}#{name}", "sk": f"{ts}#{request_id}", "t": ts, "v": value}
        )
        # Remember the name, so that list() does not have to scan the table.
        self.table.put_item(Item={"pk": f"NAMES#{device}", "sk": name})

    def saved_key(self, device, name):
        return f"saved/{device}/{name}"

    def put_binary(self, device, name, data):
        self.remove(device, name)  # an image replaces whatever was there
        content_type = "image/jpeg" if name.lower().endswith((".jpg", ".jpeg")) else "application/octet-stream"
        self.s3.put_object(
            Bucket=self.bucket, Key=self.saved_key(device, name), Body=data, ContentType=content_type
        )
        self.table.put_item(Item={"pk": f"NAMES#{device}", "sk": name, "kind": "binary"})

    def is_binary(self, device, name):
        item = self.table.get_item(Key={"pk": f"NAMES#{device}", "sk": name}).get("Item")
        return bool(item) and item.get("kind") == "binary"

    def remove(self, device, name):
        if self.is_binary(device, name):
            self.s3.delete_object(Bucket=self.bucket, Key=self.saved_key(device, name))
            self.table.delete_item(Key={"pk": f"NAMES#{device}", "sk": name})
            return 1
        keys = []
        kwargs = {
            "KeyConditionExpression": "pk = :pk",
            "ExpressionAttributeValues": {":pk": f"REC#{device}#{name}"},
            "ProjectionExpression": "pk, sk",
        }
        while True:
            page = self.table.query(**kwargs)
            keys += page["Items"]
            if "LastEvaluatedKey" not in page:
                break
            kwargs["ExclusiveStartKey"] = page["LastEvaluatedKey"]
        with self.table.batch_writer() as batch:
            for key in keys:
                batch.delete_item(Key={"pk": key["pk"], "sk": key["sk"]})
        self.table.delete_item(Key={"pk": f"NAMES#{device}", "sk": name})
        return len(keys)

    def names(self, device, prefix):
        condition = "pk = :pk"
        values = {":pk": f"NAMES#{device}"}
        if prefix:
            condition += " AND begins_with(sk, :prefix)"
            values[":prefix"] = prefix
        names, kwargs = [], {"KeyConditionExpression": condition, "ExpressionAttributeValues": values}
        while True:
            page = self.table.query(**kwargs)
            names += [item["sk"] for item in page["Items"]]
            if "LastEvaluatedKey" not in page:
                return names
            kwargs["ExclusiveStartKey"] = page["LastEvaluatedKey"]

    def records(self, device, name):
        kwargs = {
            "KeyConditionExpression": "pk = :pk",
            "ExpressionAttributeValues": {":pk": f"REC#{device}#{name}"},
        }
        while True:
            page = self.table.query(**kwargs)
            for item in page["Items"]:
                yield item["t"], item["v"]
            if "LastEvaluatedKey" not in page:
                return
            kwargs["ExclusiveStartKey"] = page["LastEvaluatedKey"]

    def file(self, name):
        try:
            obj = self.s3.get_object(Bucket=self.bucket, Key=f"files/{name}")
        except ClientError as e:
            if e.response["Error"]["Code"] in ("NoSuchKey", "AccessDenied"):
                return None
            raise
        return obj["Body"].read().decode("utf-8", errors="replace")

    def invoke(self, name, data, device, request_id, timeout_ms):
        arn = self.functions.get(name)
        if not arn:
            raise CloudError(
                ERR_NOT_FOUND,
                f'There is no function "{name}". Put {name}.py in backend/functions/ and deploy.',
            )
        client = boto3.client(
            "lambda", config=Config(read_timeout=timeout_ms / 1000, retries={"max_attempts": 0})
        )
        try:
            res = client.invoke(
                FunctionName=arn,
                Payload=json.dumps({"input": data, "device": device, "requestId": request_id}),
            )
        except ReadTimeoutError:
            raise CloudError(ERR_TIMEOUT, f'"{name}" did not finish within {timeout_ms // 1000} s.')
        payload = json.loads(res["Payload"].read() or b"null")
        if res.get("FunctionError"):
            message = payload.get("errorMessage", "") if isinstance(payload, dict) else ""
            if "Task timed out" in message:
                raise CloudError(ERR_TIMEOUT, f'"{name}" did not finish in time.')
            raise CloudError(ERR_RUN_FAILED, f'An error occurred in "{name}": {message}')
        return payload.get("output", "") if isinstance(payload, dict) else ""

    def complete(self, system, text, log, image=None):
        content = [{"text": text}]
        if image:
            content.insert(0, {"image": {"format": "jpeg", "source": {"bytes": image}}})
        try:
            res = self.bedrock.converse(
                modelId=self.model,
                system=[{"text": system}],
                messages=[{"role": "user", "content": content}],
                inferenceConfig={"maxTokens": 1024, "temperature": 0.2},
            )
        except ClientError as e:
            print(f"bedrock error: {e!r}")
            raise CloudError(
                ERR_SERVER, "The AI is not available right now. Check the backend settings."
            )
        usage = res.get("usage", {})
        log["tokensIn"] = log.get("tokensIn", 0) + usage.get("inputTokens", 0)
        log["tokensOut"] = log.get("tokensOut", 0) + usage.get("outputTokens", 0)
        return "".join(p.get("text", "") for p in res["output"]["message"]["content"])

    def count_ask(self, device):
        now = datetime.now(timezone.utc)
        try:
            self.table.update_item(
                Key={"pk": f"USAGE#{device}#{now.strftime('%Y-%m-%d')}", "sk": "ask"},
                UpdateExpression="ADD #c :one SET #ttl = :ttl",
                ConditionExpression="attribute_not_exists(#c) OR #c < :limit",
                ExpressionAttributeNames={"#c": "count", "#ttl": "ttl"},
                ExpressionAttributeValues={
                    ":one": 1,
                    ":limit": self.daily_limit,
                    ":ttl": int((now + timedelta(days=CALL_LOG_DAYS)).timestamp()),
                },
            )
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                raise CloudError(
                    ERR_LIMIT, f"Today's limit of {self.daily_limit} questions has been reached."
                )
            raise

    def log_call(self, device, op, request_id, entry):
        ts = datetime.now(timezone.utc)
        self.table.put_item(
            Item={
                "pk": f"CALL#{ts.strftime('%Y-%m-%d')}",
                "sk": f"{ts.isoformat()}#{request_id}",
                "device": device,
                "op": op,
                "name": entry.get("name", ""),
                "code": entry.get("code", 0),
                "ms": entry.get("ms", 0),
                "bytesIn": entry.get("in", 0),
                "bytesOut": entry.get("out", 0),
                "tokensIn": entry.get("tokensIn", 0),
                "tokensOut": entry.get("tokensOut", 0),
                "ttl": int((ts + timedelta(days=CALL_LOG_DAYS)).timestamp()),
            }
        )


CORE = Core(AwsAdapter())


def handler(event, context):
    headers = event.get("headers", {})
    request_id = headers.get("x-request-id") or str(uuid.uuid4())
    raw = event.get("body") or "{}"
    try:
        if event.get("isBase64Encoded"):
            raw = base64.b64decode(raw).decode("utf-8")
        body = json.loads(raw)
    except (ValueError, UnicodeDecodeError):
        body = None
    code, error, result = CORE.handle(
        event.get("rawPath", ""), body, headers.get("x-device-token", ""), request_id
    )
    return {
        "statusCode": 200,
        "headers": {"content-type": "application/json"},
        "body": json.dumps(
            {"ok": code == 0, "code": code, "error": error, "result": result}, ensure_ascii=False
        ),
    }
