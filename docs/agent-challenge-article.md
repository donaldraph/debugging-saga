# Weekend Creative Agent Challenge: Debugging Saga

Tags: #agents

A saga generator that used to wait for you to press a button. Now it
doesn't.

## Vision & What the App Does

Debugging Saga takes a true engineering war story and retells it as a
narrated epic in one of four voices — epic fantasy, noir detective, nature
documentary, Greek tragedy — while keeping every real fact intact: the
actual error text, the actual root cause, the actual numbers. Last week
that only happened when a visitor picked a story and a tone and pressed
Dramatize. It was, deliberately, stateless: generate, play, forget.

This week's challenge asks for the opposite instinct — an agent that makes
something new on its own and has it ready before you return. Rather than
bolt on something unrelated, I gave the app a second, unattended act that
sits beside the first without touching it: every three hours, with nobody
watching, it picks the next story and tone in a fixed rotation, writes and
narrates a full saga through the exact same pipeline a human triggering it
would use, and has it waiting on the page as "Now showing, unattended" the
next time anyone visits.

## How You Built It

The interactive route, `POST /generate`, stayed exactly as it was: no
database, a saga is born, played, and forgotten, because there's still real
value in that being true for anyone bringing their own bug. The unattended
half needed the one thing the interactive half deliberately avoided —
memory — so it got its own DynamoDB table rather than compromising the
original design. `pk=LATEST_AUTO` holds the current premiere, `pk=AUTO,
sk=timestamp` is history, and both carry a 7-day TTL that matches the audio
bucket's own lifecycle rule, so a stored saga's text never outlives the
audio file it points to.

The new Lambda, `auto_remix.py`, calls the identical two functions the
interactive path already trusted — `model.generate_saga` for the Gemini
retelling, `narrate.narrate` for the Polly narration — so there was no new
model-wrangling to do. The only genuinely new decision was how to pick
"what's next" without a human choosing. I went with a fixed rotation
through all sixteen story-tone combinations, alphabetical by tone, rather
than random selection, for a specific reason: it's reconstructible. The
Lambda doesn't need a separate cursor in the database — it reads the last
stored combination, finds it in the fixed list, and advances one step. No
extra state, no risk of the cursor and the data disagreeing.

The read side needed its own small honesty fix. Polly's presigned URLs are
short-lived by design, and a saga sitting in DynamoDB for hours would
eventually point at a dead link. So `GET /latest-auto` doesn't serve the
stored URL at all — it stores the S3 *key* and re-signs a fresh URL from it
on every single read, which meant teaching `narrate.py` a second, smaller
function, `presign()`, alongside the one that does the original synthesis.

I verified the whole thing by invoking the deployed `auto_remix.py`
directly — the same code EventBridge calls, not a mock — four times in a
row. It produced the calendar-account-mixup story in epic, then nature,
then noir, then tragedy: no repeats, exactly the fixed order predicted.
The fourth one, "The Tragedy of the Misplaced Calendars," came back through
`GET /latest-auto` seconds later with a real, freshly re-signed audio URL.
The EventBridge rule itself confirms `ENABLED` on a 3-hour schedule.

## AWS Services Used / Architecture Overview

The stack grew by one table and one schedule on top of last week's
foundation, all still CDK-TS: AWS Lambda (health, generate, showcase,
now auto-remix and latest-auto), Amazon API Gateway (the public routes,
throttled to protect model quota), Amazon DynamoDB (new — the auto-remix
table, pay-per-request, TTL'd), Amazon EventBridge (new — the 3-hour
schedule that makes this an agent instead of a button), Amazon S3 (private
audio storage, 7-day lifecycle), Amazon CloudFront (the frontend), Amazon
Polly (neural narration, one voice per tone), AWS Secrets Manager (the
Gemini key), and Google Gemini itself for the tone transformation — the one
non-AWS piece, present for the same reason as last week: an unresolved
account-level Bedrock throttle that a weekend can't route around.

## What You Learned

The hardest part wasn't adding a schedule — EventBridge and a Lambda handle
that in a few lines. It was resisting the urge to touch the part that
already worked. The interactive picker earned its statelessness on purpose,
and the honest move was to give the new behavior its own table and its own
route rather than quietly making the whole app stateful to support one
feature. I also learned that "unattended" needs its own honesty discipline,
the same way the mood thresholds and the true numbers did last week: a
presigned URL that silently expires is a small dishonesty (a broken link
where a working one was promised), so the fix wasn't to cache longer, it
was to stop trusting a stored URL at all and regenerate the truth on every
read.

## Link to App or Repo

- Live app: https://d1haw8tkljqm0i.cloudfront.net
- Source: https://github.com/donaldraph/debugging-saga
