"""GET /health - proves API Gateway, Lambda, IAM, and the audio bucket are wired.

The one real route the scaffold ships. Checks the audio bucket actually exists
and is reachable with the function's role, so a 200 here means the whole chain
works, not just that Lambda can return JSON.
"""

import json
import os

import boto3
from botocore.exceptions import ClientError

CORS = {"Access-Control-Allow-Origin": "*"}


def handler(event, context):
    bucket = os.environ["AUDIO_BUCKET"]
    try:
        boto3.client("s3").head_bucket(Bucket=bucket)
        bucket_status = "reachable"
    except ClientError as exc:
        bucket_status = f"error: {exc.response['Error']['Code']}"

    return {
        "statusCode": 200,
        "headers": {**CORS, "Content-Type": "application/json"},
        "body": json.dumps({"status": "ok", "audio_bucket": bucket_status}),
    }
