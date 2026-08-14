#!/usr/bin/env python3
"""Local prompt-tuning harness: generate a saga for one showcase entry.

Usage: python3 scripts/try_saga.py <showcase-id> <tone> [model-id]
Pulls the real key from Secrets Manager, calls the real model, prints the
result with timing. This is how the prompt gets tuned before any deploy.
"""

import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "infra" / "lambdas"))


def main() -> None:
    import os
    saga_id = sys.argv[1] if len(sys.argv) > 1 else "five-token-throttle"
    tone = sys.argv[2] if len(sys.argv) > 2 else "epic"
    if len(sys.argv) > 3:
        os.environ["MODEL_ID"] = sys.argv[3]
        os.environ["MODEL_FALLBACKS"] = ""

    raw = subprocess.run(
        ["aws", "secretsmanager", "get-secret-value", "--secret-id",
         "debugging-saga/gemini", "--query", "SecretString", "--output", "text"],
        capture_output=True, text=True, check=True).stdout
    os.environ["GEMINI_API_KEY"] = json.loads(raw)["api_key"]

    import model
    from showcase_data import SHOWCASE_BY_ID

    story = SHOWCASE_BY_ID[saga_id]["story"]
    t0 = time.time()
    out = model.generate_saga(story, tone)
    dt = time.time() - t0

    print(f"--- {out['model']}  {dt:.1f}s  tone={tone}  {len(out['saga'].split())} words")
    print(f"TITLE: {out['title']}\n")
    print(out["saga"])


if __name__ == "__main__":
    main()
