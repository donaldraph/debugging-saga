# Architecture

Three CDK stacks (`dsg-dev-data`, `dsg-dev-api`, `dsg-dev-hosting`), and
two ways a saga comes into existence — one a visitor asks for, one nobody
does — sharing exactly one pipeline underneath.

```mermaid
flowchart LR
    subgraph interactive["A visitor asks (stateless)"]
        direction TB
        PICK[Pick a showcase story\nor paste your own bug]
        TONE[Pick a tone]
        GEN[POST /generate]
        PICK --> TONE --> GEN
    end

    subgraph unattended["Nobody asks (EventBridge, every 3h)"]
        direction TB
        ROT[Rotate to the next\nof 16 story x tone combos\n(reconstructed from the last\nstored combo, no cursor)]
        AUTO[auto_remix.py]
        ROT --> AUTO
    end

    GEN --> SEAM
    AUTO --> SEAM

    subgraph SEAM["The shared, proven pipeline"]
        direction TB
        MODEL[model.generate_saga\nGemini: flash-latest -> 3.5-flash-lite\ntrue facts, dramatized telling]
        NARR[narrate.narrate\nAmazon Polly, one neural voice per tone]
        MODEL --> NARR
    end

    NARR -- text-only if Polly fails,\nnever loses the saga --> RESP1[Response: title, saga,\nmodel, audio or audio_error]
    RESP1 --> GEN2[back to the visitor,\nnothing stored]

    NARR --> STORE[(DynamoDB dsg-autosaga-dev\npk=LATEST_AUTO, pk=AUTO history\n7-day TTL, matches audio bucket)]
    STORE --> LATEST[GET /latest-auto\nre-signs a fresh audio URL\nfrom the stored S3 key on every read]
    LATEST --> PANEL["Now showing, unattended"\npanel, above the interactive picker]
```

## Why this shape

- **Interactive stays stateless, on purpose.** A visitor's saga is
  generated, played, and forgotten - that was true on day one and the
  unattended feature was built to not compromise it, so it got its own
  table rather than making the whole app stateful.
- **One pipeline, two doors.** `auto_remix.py` calls the exact same
  `model.generate_saga` and `narrate.narrate` the interactive route
  already trusted. No second prompt to maintain, no second failure mode
  to test.
- **Fixed rotation, not random.** 16 combinations, alphabetical by tone,
  advanced from whatever combo is currently stored - reconstructible from
  one read, no separate cursor that could drift out of sync with reality.
- **Presigned URLs are re-signed on read, never stored as truth.** Polly's
  URLs are short-lived; `GET /latest-auto` regenerates one from the saved
  S3 key every time, so a saga sitting in the table for hours never points
  at a dead link.

## AWS services in play

Lambda (health, generate, showcase, auto-remix, latest-auto), EventBridge
(the 3-hour schedule), DynamoDB (the auto-remix table), S3 (audio, 7-day
lifecycle), Amazon Polly (narration), API Gateway (all routes, throttled),
Secrets Manager (the Gemini key), S3 + CloudFront (the frontend). Google
Gemini writes every saga - the load-bearing AI in both doors.
