"""GET /showcase - the four real stories plus the available tones.

Includes each story's full source text so the frontend can show the true
build-log excerpt beside the generated saga; the recognizably-true part is
the product.
"""

import json

import model
from showcase_data import SHOWCASE

CORS = {"Access-Control-Allow-Origin": "*"}


def handler(event, context):
    return {
        "statusCode": 200,
        "headers": {**CORS, "Content-Type": "application/json"},
        "body": json.dumps({
            "sagas": SHOWCASE,
            "tones": [{"id": tid, "name": t["name"]}
                      for tid, t in sorted(model.TONES.items())],
        }),
    }
