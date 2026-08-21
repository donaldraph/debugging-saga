# Weekend Creative Agent Challenge: Debugging Saga

Tags: #agents

A saga generator used to need you to press a button. Not anymore.

## Vision & What the App Does

Debugging Saga takes a real engineering horror story and turns it into a narrated epic. Four voices to choose from: epic fantasy, noir detective, nature documentary, Greek tragedy. Every version keeps the real facts locked in place. The actual error text, the actual root cause, the actual numbers. Comedy comes from the gap between the drama and the mundane bug, never from making anything up.

Last week that only happened when a visitor picked a story, picked a tone, and hit Dramatize. On purpose, it was stateless. Generate, play, forget, like most debugging knowledge.

This week's challenge wants the opposite instinct: an agent that makes something new without you and has it ready when you get back. So instead of bolting on something unrelated, I gave the app a second act that runs beside the first without touching it. Every three hours, nobody watching, it picks the next story and tone off a fixed rotation, writes and narrates a full saga through the same pipeline a human would trigger, and leaves it sitting on the page under "Now showing, unattended" for whoever shows up next.

## How You Built It

`POST /generate` didn't change at all. No database, a saga gets born, played, and forgotten, and that's still worth keeping for anyone who wants to bring their own bug. The unattended half needed exactly the thing the interactive half was built to avoid: memory. So it got its own DynamoDB table instead of dragging the rest of the app into being stateful. `pk=LATEST_AUTO` holds the current premiere, `pk=AUTO, sk=timestamp` is history, both on a 7-day TTL that matches the audio bucket's own lifecycle, so a saga's text never outlives the audio file it points at.

The new Lambda, `auto_remix.py`, just calls the same two functions the interactive route already trusts: `model.generate_saga` for the retelling, `narrate.narrate` for the Polly voice. No new model wrangling required. The one real decision was how to pick "what's next" with no human in the loop, and I went with a fixed rotation through all sixteen story and tone combos, alphabetical by tone, instead of random. Reason: it's reconstructible. No cursor sitting in the database that could drift out of sync with reality. Read the last stored combo, find it in the list, move one step forward. Done.

The read side needed a smaller fix, but an honest one. Polly's presigned URLs die after a while, and a saga sitting in DynamoDB for hours would eventually point at nothing. So `GET /latest-auto` never serves the stored URL. It stores the S3 key and re-signs a fresh URL on every single read, which meant giving `narrate.py` a second, tiny function called `presign()` next to the one that does the actual synthesis.

I proved it by invoking the deployed `auto_remix.py` directly, four times in a row, the same code EventBridge calls, not a mock. It produced the calendar-account-mixup story in epic, then nature, then noir, then tragedy. No repeats, exactly the order the rotation predicts. The fourth one, "The Tragedy of the Misplaced Calendars," came back through `GET /latest-auto` seconds later with a real, freshly signed audio URL. The EventBridge rule itself checks in as `ENABLED` on a 3-hour schedule.

## AWS Services Used / Architecture Overview

The stack grew by one table and one schedule on top of last week's foundation, still CDK-TS. AWS Lambda runs health, generate, showcase, and now auto-remix and latest-auto. Amazon API Gateway fronts the public routes, throttled so nobody can burn the model quota by accident. Amazon DynamoDB is the new auto-remix table, pay-per-request, TTL'd. Amazon EventBridge is the new part too, the 3-hour schedule that makes this an agent and not a button. Amazon S3 stores audio privately on a 7-day lifecycle, CloudFront serves the frontend, Amazon Polly does the narration with one neural voice per tone, and Secrets Manager holds the Gemini key. Google Gemini itself handles the tone transformation, the one piece not running on AWS, for the same reason as last week: an account-level Bedrock throttle that no weekend is going to fix.

## What You Learned

Adding the schedule wasn't the hard part. EventBridge and a Lambda do that in a handful of lines. The hard part was leaving alone what already worked. The interactive picker earned its statelessness on purpose, so the honest move was giving the new behavior its own table and its own route instead of quietly turning the whole app stateful for one feature's sake. I also learned that "unattended" carries its own honesty test. A presigned URL that quietly dies is a small lie, a broken link standing where a working one was promised. The fix wasn't a longer cache. It was refusing to trust a stored URL at all and just regenerating the truth on every read.

## Link to App or Repo

- Live app: https://d1haw8tkljqm0i.cloudfront.net
- Source: https://github.com/donaldraph/debugging-saga
