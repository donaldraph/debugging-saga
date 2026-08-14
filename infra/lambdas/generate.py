"""POST /generate - turn a true debugging story into a saga.

Body: {"tone": "epic|noir|nature|tragedy"} plus exactly one of
  {"showcase_id": "..."} - one of the four pre-approved real stories, or
  {"text": "..."}        - bring your own bug.

Public route by design: anyone can paste their story. The stage throttle and
the input cap protect the model quota. Runs synchronously - measured chain
latency (flash-latest 5-13s, lite 3s) fits under API Gateway's 29s cap with
room; if free-tier queueing ever breaks that, the convene async pattern is
the known fix.

Narration (Polly) lands in the next phase; until then audio is null.
"""

import json

import model
from showcase_data import SHOWCASE_BY_ID

MAX_CHARS = 6000
CORS = {"Access-Control-Allow-Origin": "*"}


def _resp(code: int, body: dict) -> dict:
    return {
        "statusCode": code,
        "headers": {**CORS, "Content-Type": "application/json"},
        "body": json.dumps(body),
    }


def handler(event, context):
    try:
        body = json.loads(event.get("body") or "{}")
    except json.JSONDecodeError:
        return _resp(400, {"error": "body must be JSON"})

    tone = body.get("tone", "epic")
    if tone not in model.TONES:
        return _resp(400, {"error": f"unknown tone '{tone}'",
                           "valid_tones": sorted(model.TONES)})

    showcase_id = body.get("showcase_id")
    if showcase_id:
        entry = SHOWCASE_BY_ID.get(showcase_id)
        if not entry:
            return _resp(404, {"error": f"unknown showcase saga '{showcase_id}'",
                               "valid_ids": sorted(SHOWCASE_BY_ID)})
        story = entry["story"]
        source = {"type": "showcase", "id": entry["id"],
                  "title": entry["title"], "project": entry["project"]}
    else:
        story = (body.get("text") or "").strip()
        if not story:
            return _resp(400, {"error": "send showcase_id or text; "
                                        "an empty story has no drama"})
        if len(story) > MAX_CHARS:
            return _resp(400, {"error": f"story too long ({len(story)} chars, "
                                        f"max {MAX_CHARS}); even Homer edited"})
        source = {"type": "freetext"}

    try:
        out = model.generate_saga(story, tone)
    except model.SagaError as exc:
        return _resp(503, {"error": "the narrator is unavailable",
                           "detail": str(exc)})

    return _resp(200, {
        "title": out["title"],
        "saga": out["saga"],
        "tone": tone,
        "tone_name": model.TONES[tone]["name"],
        "model": out["model"],
        "source": source,
        "audio": None,
    })
