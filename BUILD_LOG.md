# Build log

Every real problem hit during the build, in the order it happened. Format per
entry: symptom, root cause, fix, reasoning. No invented entries; if a phase
went clean, it says so.

There is a pleasing recursion here: this project turns build logs into sagas,
and this file is the build log that will describe building it. If something
goes wrong enough, it may end up narrating itself.

## Phase 1: showcase selection + repo scaffold + CDK (2026-08-14)

Showcase sagas picked first, approved by the owner before any code. Four real
stories, pulled from the BUILD_LOGs of convene, standup-brief, and
study-conscience:

1. **The calendar-account mixup** (convene): four rounds of created calendars
   vanishing into whichever Google account the browser had active. Fixed by
   redesigning sync to match how the owner actually keeps their calendar.
2. **The five-token throttle** (standup-brief): a 5-token Bedrock test call
   denied for "too many tokens per day" against a 5.76 billion/day model quota
   that was never the constraint. The real wall was an opaque account-level
   allowance, fixable only through a support tier the account does not have.
3. **The schema that betrayed its own notes** (study-conscience): kubeadm
   extraArgs is a map in v1beta3 and a list in v1beta4, and the build note
   recording which was which had it backwards. Snag three of the same cluster
   recreate.
4. **The 29-second guillotine** (convene): three escalating defeats against
   API Gateway's hard timeout, ended by going async instead of shaving
   milliseconds.

Scaffold decisions, so later phases inherit them:

- **Stack shape copied from convene**, the most recently proven deploy of this
  pattern (CDK-TS data/api/hosting, Python 3.12 Lambdas, private S3 behind
  CloudFront with OAC). Same pinned toolchain: aws-cdk-lib ^2.150.0,
  typescript ~5.5.4, node 22.
- **The data stack is an S3 bucket, not DynamoDB.** Nothing persists except
  generated audio, and even that expires after 7 days via a lifecycle rule.
  A saga is stateless: generate, play, gone.
- **Audio is served by presigned URL**, so the bucket stays fully private and
  the frontend never needs bucket permissions.
- **Gemini model id stays a context flag** (`-c model=...`), because model
  gating has burned three projects in a row. Default is gemini-3.5-flash-lite,
  the id that actually survived convene's live testing; first live call here
  will re-verify what this key can reach.
- **API scaffold ships one real route (GET /health)** and nothing else. Routes
  land with the phase that implements them.

Proof: `npm install` + clean `tsc` + `cdk synth` produced all three templates
(dsg-dev-data, dsg-dev-api, dsg-dev-hosting) on the first run. No failures this
phase, so no symptom/root-cause entries yet.

### Early deploy (2026-08-14, same day)

Deployed the scaffold to AWS immediately, so a reachable URL exists from day
one. One pass, no failures, 557s total:

- Site: https://d1haw8tkljqm0i.cloudfront.net (honest placeholder, config.js
  injected with the API base)
- API: https://x8wn77svi0.execute-api.us-east-1.amazonaws.com/dev/ where
  GET /health returns ok with audio_bucket reachable against
  dsg-audio-dev, proving API Gateway, Lambda, IAM, and the bucket are wired
  end to end
- Public repo pushed: https://github.com/donaldraph/debugging-saga
- Same known cdk annotation as convene (crossStackReferencesDefaultStrong),
  a note not a failure.
