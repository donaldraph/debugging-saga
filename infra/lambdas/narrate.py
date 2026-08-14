"""The narrator seam: Polly reads the saga aloud into S3.

Each tone gets its own neural voice, because the voice is half of how a tone
lands: a noir monologue needs a low American register, a nature documentary
needs a hushed British one. Polly bills by character, so four voices cost
the same as one.

Audio goes to the private bucket and comes back as a presigned URL; the
bucket never opens up. Objects expire after 7 days via the bucket lifecycle
rule, and the URL itself dies sooner.
"""

import os
import uuid

import boto3

# Neural voices, all available in us-east-1, cast per tone:
#   epic    -> Brian   (British male: the bard)
#   noir    -> Matthew (American male, low register: the private eye)
#   nature  -> Arthur  (British male: the documentarian)
#   tragedy -> Amy     (British female, formal: the chorus)
VOICES = {
    "epic": "Brian",
    "noir": "Matthew",
    "nature": "Arthur",
    "tragedy": "Amy",
}
ENGINE = "neural"

# SynthesizeSpeech bills at most 3000 chars per call for neural; stay under
# with margin and stitch. Polly MP3 chunks concatenate cleanly (same codec,
# same bitrate), so a long saga is just several calls in order.
_MAX_CHUNK = 2500

# Presigned GET lifetime. Long enough to listen and share within a sitting;
# actual validity is also capped by the Lambda role session behind it, which
# is fine for a play-it-now app.
_URL_TTL_S = int(os.environ.get("AUDIO_URL_TTL_S", "21600"))

_polly = boto3.client("polly")
_s3 = boto3.client("s3")


def _chunks(text: str):
    """Split on sentence ends into pieces under the Polly billing cap."""
    pieces, current = [], ""
    for sentence in text.replace("\n", " ").split(". "):
        candidate = f"{current}. {sentence}" if current else sentence
        if len(candidate) > _MAX_CHUNK and current:
            pieces.append(current)
            current = sentence
        else:
            current = candidate
    if current:
        pieces.append(current)
    # A single pathological sentence longer than the cap gets hard-split;
    # mid-sentence seams beat a hard Polly error.
    safe = []
    for p in pieces:
        while len(p) > _MAX_CHUNK:
            safe.append(p[:_MAX_CHUNK])
            p = p[_MAX_CHUNK:]
        safe.append(p)
    return safe


def narrate(text: str, tone: str) -> dict:
    """Synthesize the text in the tone's voice, store it, return the URL."""
    bucket = os.environ["AUDIO_BUCKET"]
    voice = VOICES.get(tone, "Brian")

    audio = b""
    for chunk in _chunks(text):
        resp = _polly.synthesize_speech(
            Text=chunk,
            VoiceId=voice,
            Engine=ENGINE,
            OutputFormat="mp3",
        )
        audio += resp["AudioStream"].read()

    key = f"audio/{uuid.uuid4().hex}.mp3"
    _s3.put_object(Bucket=bucket, Key=key, Body=audio, ContentType="audio/mpeg")

    url = _s3.generate_presigned_url(
        "get_object", Params={"Bucket": bucket, "Key": key}, ExpiresIn=_URL_TTL_S)
    return {
        "url": url,
        "voice": voice,
        "engine": ENGINE,
        "bytes": len(audio),
        "expires_in_s": _URL_TTL_S,
    }
