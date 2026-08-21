"""The unattended premiere: EventBridge calls this on its own, no human in
the loop, and it has something new ready by the time anyone returns.

Rotates through all 16 (showcase story x tone) combinations rather than
picking randomly, so a run never immediately repeats the last one, and
runs the exact same proven seam the interactive /generate route uses:
model.generate_saga for the text, narrate.narrate for the audio. Stores the
result under pk=LATEST_AUTO (fast fetch) and pk=AUTO/sk=timestamp (history),
7-day TTL matching the audio bucket's own lifecycle rule.
"""

import json
import os
from datetime import datetime, timedelta, timezone

import boto3

import model
import narrate
from showcase_data import SHOWCASE, SHOWCASE_BY_ID

TABLE_NAME = os.environ["AUTOSAGA_TABLE"]
HISTORY_KEEP_DAYS = 7

_table = boto3.resource("dynamodb").Table(TABLE_NAME)

# Fixed, deterministic rotation order rather than random, so which combo
# ran next is reconstructable from the last one alone - no separate cursor
# needed, and every combo gets an equal turn.
_COMBOS = [(s["id"], tone) for s in SHOWCASE for tone in sorted(model.TONES)]


def _last_combo():
    item = _table.get_item(Key={"pk": "LATEST_AUTO", "sk": "LATEST_AUTO"}).get("Item")
    if not item:
        return None
    body = json.loads(item["body"])
    return (body.get("source", {}).get("id"), body.get("tone"))


def _next_combo():
    last = _last_combo()
    if last is None or last not in _COMBOS:
        return _COMBOS[0]
    return _COMBOS[(_COMBOS.index(last) + 1) % len(_COMBOS)]


def handler(event, context):
    showcase_id, tone = _next_combo()
    entry = SHOWCASE_BY_ID[showcase_id]

    out = model.generate_saga(entry["story"], tone)

    audio = None
    audio_error = None
    try:
        audio = narrate.narrate(f"{out['title']}. {out['saga']}", tone)
    except Exception as exc:  # noqa: BLE001 - text-only beats losing the saga
        audio_error = f"narration failed ({type(exc).__name__}); text-only saga"

    now = datetime.now(timezone.utc)
    record = {
        "generated_at": now.isoformat(timespec="seconds"),
        "title": out["title"],
        "saga": out["saga"],
        "tone": tone,
        "tone_name": model.TONES[tone]["name"],
        "model": out["model"],
        "source": {"type": "showcase", "id": entry["id"],
                   "title": entry["title"], "project": entry["project"]},
        "audio": audio,
        "audio_error": audio_error,
        "auto": True,
    }

    expires = int((now + timedelta(days=HISTORY_KEEP_DAYS)).timestamp())
    body = json.dumps(record)
    _table.put_item(Item={"pk": "AUTO", "sk": record["generated_at"],
                          "expires_at": expires, "body": body})
    _table.put_item(Item={"pk": "LATEST_AUTO", "sk": "LATEST_AUTO", "body": body})
    return record
