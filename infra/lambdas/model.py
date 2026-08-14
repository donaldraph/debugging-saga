"""The model seam: turn a true debugging story into a dramatic saga.

This is the load-bearing AI. The job is genuine tone transformation with
narrative judgment: the model must keep every technical fact from the source
(what broke, the real error text, the real root cause, the real fix) while
retelling the events in the requested voice. Dramatize the telling, never
the facts.

Wired to Google Gemini. Key from Secrets Manager. There is no deterministic
fallback for creative writing, so if every model fails the caller gets an
honest error - this app never presents non-AI output as a saga.
"""

import json
import os
import urllib.error
import urllib.request
from typing import Optional

# Model gating on this key is fiddly (convene, verified live 2026-07-31):
# gemini-2.5-* 404, gemini-3.5-flash 503s under load, gemini-2.0-flash 429s.
# gemini-flash-latest (sharper writing) and gemini-3.5-flash-lite (reliable)
# both held. Sharp one primary: this is creative output, quality is the point.
MODEL_ID = os.environ.get("MODEL_ID", "gemini-flash-latest")
MODEL_FALLBACKS = [m.strip() for m in
                   os.environ.get("MODEL_FALLBACKS", "gemini-3.5-flash-lite").split(",")
                   if m.strip()]
GEMINI_SECRET_NAME = os.environ.get("GEMINI_SECRET_NAME", "debugging-saga/gemini")
_API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"

# API Gateway kills any request at 29s. Primary gets a generous budget since
# saga generation is a longer output than convene's slot ranking; the fallback
# gets what fits in the remainder.
_PRIMARY_TIMEOUT_S = int(os.environ.get("GEMINI_TIMEOUT_S", "18"))
_FALLBACK_TIMEOUT_S = int(os.environ.get("GEMINI_FALLBACK_TIMEOUT_S", "8"))

TONES = {
    "epic": {
        "name": "Epic fantasy",
        "instructions": (
            "A mock-heroic fantasy epic in the manner of a bard recounting a "
            "legendary quest. Third person past tense. The engineer is a "
            "questing hero, systems are realms and creatures, error messages "
            "are prophecies and curses. Use Homeric epithets for recurring "
            "systems (API Gateway the Unbending, kubeadm keeper of clusters). "
            "Grand formal diction played completely straight against the "
            "mundane subject; the comedy comes from the gap, never from "
            "winking at the audience."
        ),
    },
    "noir": {
        "name": "Noir detective",
        "instructions": (
            "Hard-boiled detective fiction. First person, world-weary, "
            "cynical. The bug is a case that walked in the door; the engineer "
            "narrates it like a private eye who has seen too many stack "
            "traces. Short punchy sentences. Rain optional but encouraged. "
            "Systems are characters in the underworld: informants, crooked "
            "gatekeepers, dames with secrets. The error message is delivered "
            "like a threat left at a crime scene."
        ),
    },
    "nature": {
        "name": "Nature documentary",
        "instructions": (
            "A hushed, reverent nature documentary. Present tense, second or "
            "third person. The engineer is a creature observed in its natural "
            "habitat; the bug is predator or prey. The narrator finds "
            "profound wonder in mundane behavior (here, the developer "
            "refreshes the console for the fourth time). Patient, awed, "
            "occasionally melancholy about the brutality of the ecosystem. "
            "Do not name any real documentary narrator."
        ),
    },
    "tragedy": {
        "name": "Greek tragedy",
        "instructions": (
            "A Greek tragedy performed by a chorus. Formal, fatalistic, "
            "addressed partly to the gods. The engineer is a tragic hero "
            "whose flaw (hubris, or trusting their own notes) sets fate in "
            "motion. The chorus comments on the action and warns of doom the "
            "hero cannot hear. Invocations, laments, and at least one cry to "
            "the heavens. The machines are indifferent gods and oracles. The "
            "closing line belongs to the chorus, drawing the moral as a "
            "warning to all who build."
        ),
    },
}

_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "saga": {"type": "string"},
    },
    "required": ["title", "saga"],
}

_PROMPT = """\
You retell TRUE debugging stories as dramatic sagas for narration aloud. The
input below is a real excerpt from an engineer's build log. Retell those same
events in the requested tone.

Tone: {tone_name}. {tone_instructions}

Hard rules, in priority order:
1. Every technical fact in the source survives: what broke, what the error
   actually said, the real root cause, the real fix, the real reasoning.
   Someone who lived the source story must recognize every beat of it.
2. Never invent technical events. No extra failures, no imagined heroics.
   Dramatize the telling, never the facts.
3. Keep the real numbers. 29 seconds, 5 tokens, 5.76 billion, four rounds:
   the true numbers are usually the funniest thing in the story, so they
   must appear.
4. Real system names stay recognizable. You may crown them with epithets
   (API Gateway the Unbending) but the true name must appear at least once.
5. Write for the EAR, not the eye: this will be read aloud by a narrator.
   Flowing prose only. No markdown, no bullet lists, no code blocks, no
   stage directions, no asterisks. Punctuation only where a voice would
   pause.
6. 250 to 400 words. End on the resolution, and if the source draws a
   lesson, land it as the closing line in your tone's voice.
7. Play it completely straight. The comedy is the gap between the gravity
   of the voice and the mundanity of the subject. Never wink.

Also produce a short dramatic title in the same tone (no quotes around it).

The true story:
---
{story}
---
"""


def _api_key() -> Optional[str]:
    if os.environ.get("GEMINI_API_KEY"):
        return os.environ["GEMINI_API_KEY"]
    try:
        import boto3
        raw = boto3.client("secretsmanager").get_secret_value(
            SecretId=GEMINI_SECRET_NAME)["SecretString"]
        return json.loads(raw).get("api_key")
    except Exception:  # noqa: BLE001 - no secret / no access -> caller errors honestly
        return None


def _call_gemini(prompt: str, key: str, model_id: str, timeout: int) -> dict:
    url = f"{_API_BASE}/{model_id}:generateContent?key={key}"
    body = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": _RESPONSE_SCHEMA,
            # Creative writing wants heat; the facts are pinned by the prompt.
            "temperature": 0.9,
        },
    }).encode("utf-8")
    req = urllib.request.Request(
        url, data=body, method="POST", headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        payload = json.load(r)
    return json.loads(payload["candidates"][0]["content"]["parts"][0]["text"])


class SagaError(Exception):
    """Every model attempt failed; the caller should return an honest 503."""


def generate_saga(story: str, tone: str) -> dict:
    """Retell a true story in a tone. Returns {title, saga, model, tone}.

    Raises SagaError if no model produced output - never fakes a saga.
    """
    tone_def = TONES[tone]
    key = _api_key()
    if not key:
        raise SagaError("no Gemini key available")

    prompt = _PROMPT.format(
        tone_name=tone_def["name"],
        tone_instructions=tone_def["instructions"],
        story=story,
    )

    last_err: Exception | str = "no models configured"
    for idx, model_id in enumerate([MODEL_ID, *MODEL_FALLBACKS]):
        timeout = _PRIMARY_TIMEOUT_S if idx == 0 else _FALLBACK_TIMEOUT_S
        try:
            raw = _call_gemini(prompt, key, model_id, timeout)
        except Exception as exc:  # noqa: BLE001 - try the next model
            last_err = exc
            continue
        title = (raw.get("title") or "").strip()
        saga = (raw.get("saga") or "").strip()
        if saga:
            return {"title": title or "An untitled saga",
                    "saga": saga, "model": model_id, "tone": tone}
        last_err = "model returned an empty saga"
    reason = type(last_err).__name__ if isinstance(last_err, Exception) else str(last_err)
    raise SagaError(f"all models failed ({reason})")
