"""GET /latest-auto - the frontend's read of the unattended premiere.

Read-only, public, no model spend: EventBridge and auto_remix.py own
generation. The stored audio URL is short-lived by design (it's a Polly
presigned GET), so this regenerates a fresh one from the stored S3 key on
every read rather than serving a URL that may already be dead.
"""

import json
import os

import boto3

import narrate

TABLE_NAME = os.environ["AUTOSAGA_TABLE"]
CORS = {"Access-Control-Allow-Origin": "*"}

_table = boto3.resource("dynamodb").Table(TABLE_NAME)


def _resp(code, body):
    return {
        "statusCode": code,
        "headers": {**CORS, "Content-Type": "application/json", "Cache-Control": "no-store"},
        "body": json.dumps(body),
    }


def handler(event, context):
    item = _table.get_item(Key={"pk": "LATEST_AUTO", "sk": "LATEST_AUTO"}).get("Item")
    if not item:
        return _resp(200, {"latest": None})

    record = json.loads(item["body"])
    if record.get("audio") and record["audio"].get("key"):
        try:
            record["audio"]["url"] = narrate.presign(record["audio"]["key"])
        except Exception:  # noqa: BLE001 - stale audio beats a broken response
            pass

    return _resp(200, {"latest": record})
