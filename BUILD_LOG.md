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

## Phase 3: Gemini saga generation (2026-08-14)

The load-bearing AI. Decisions:

- **Synchronous, deliberately.** Convene earned its async worker because slot
  ranking had huge prompts and could exceed 29s. Saga generation measured
  live at 5-13s on gemini-flash-latest and ~3s on gemini-3.5-flash-lite, so
  the chain (18s + 8s budgets) fits under API Gateway's cap with room. If
  free-tier queueing ever breaks that, the convene async pattern is the
  known fix; logged here so future me does not rediscover it the hard way.
- **flash-latest primary, lite fallback.** Reversed from convene's async-era
  ordering: this is creative output, so the sharper writer gets first crack,
  and the reliable one is the net. No deterministic fallback exists for
  creative writing, so total failure is an honest 503 ("the narrator is
  unavailable"), never fake AI output.
- **POST /generate is public** because the whole point is anyone pasting
  their bug. Quota protection is a narrow stage throttle (5 rps / 10 burst)
  plus a 6000-char input cap instead of an API key.
- **Temperature 0.9.** The facts are pinned by the prompt rules, so the
  heat goes entirely into the telling.

Prompt tuning, against real stories with the real key before any deploy:
all four tones tested live (epic on five-token-throttle, noir on
schema-betrayal, nature on calendar-account-mixup, tragedy on
29-second-guillotine). All four kept every number and error string. One
tweak needed: the tragedy ended on a flat technical restatement, so the
tone instructions now hand the closing line to the chorus; the retest
closed with "do not shave your precious seconds to fit an arbitrary blade,
but sever the tether between the asking and the answering", which is the
correct amount of drama for a timeout bug.

One real failure this phase, and it is saga-worthy in its own right:

**Symptom:** after deploying the new routes, POST /generate and GET /showcase
both returned 403 "Missing Authentication Token" while GET /health kept
working. The resources and methods existed in API Gateway.
**Root cause:** the stage was still serving a deployment snapshot that
predated the new methods. The CloudFormation update created its deployment
before the new Method resources landed, so the stage pointed at a snapshot
of an API where /generate did not exist. API Gateway reports an unknown
route as a 403 auth error, which is a spectacular piece of misdirection.
**Fix:** one manual `aws apigateway create-deployment` against the stage to
re-snapshot; both routes answered immediately.
**Reasoning:** the misleading 403 is the trap worth logging. "Missing
Authentication Token" on a route you just added means the stage has not
been redeployed; it has nothing to do with authentication.

Live proof (2026-08-14): POST /generate with showcase_id
calendar-account-mixup returned a real epic from gemini-flash-latest in 13s
("Four times did the architect attempt the ritual of creation"); free-text
mode turned a pasted wrong-file CSS story into a nature documentary in 8s
("a file named styles dot css trapped inside an abandoned folder called old
underscore backup ... No browser will ever graze upon its rules"); bad tone
and empty text both return honest 400s naming the valid options.

## Phase 4: Polly narration (2026-08-14)

Decisions:

- **One neural voice per tone**, because the voice is half of how a tone
  lands aloud: Brian narrates the epics (the bard), Matthew the noir (the
  private eye), Arthur the nature documentaries (the documentarian), Amy the
  tragedies (the chorus). Polly bills per character, so four voices cost the
  same as one.
- **The narrator reads the title first**, like any self-respecting bard.
- **Audio stays in the private bucket, served by presigned URL** (6h), on
  top of the bucket's own 7-day lifecycle expiry. Streaming bytes through
  API Gateway (base64 inflation, 10MB cap) and opening the bucket were both
  worse options.
- **Chunked synthesis as a safety net**: neural SynthesizeSpeech bills at
  most 3000 chars per call, so text splits at sentence ends under 2500 and
  the MP3 chunks concatenate (same codec, same bitrate). Verified by unit
  test: a 200-sentence text splits into 5 chunks all under cap, and a
  pathological 6000-char single sentence hard-splits rather than erroring.
- **Text-only degradation**: if Polly fails after Gemini succeeded, the
  response keeps the saga and carries an explicit audio_error. The text is
  the primary artifact; losing it over a narration hiccup would be
  all-or-nothing for no reason.

No failures this phase: tsc + deploy clean, and both live tests worked
first try.

Live proof (2026-08-14): schema-betrayal as tragedy returned "The Curse of
the Inverted Scroll", narrated by Amy - a real 802KB MP3, 2m14s, downloaded
via the presigned URL and verified as MPEG layer III audio. A free-text
tab-in-the-yaml story as noir returned "A Single Byte of Treason" in
Matthew's voice, proving per-tone casting on the paste-your-own path too.

## Phase 5: frontend (2026-08-14)

The playbill. Own identity (parchment by day, stage-dark by night,
curtain-red and gold, Georgia serif), deliberately distinct from convene's
green editorial and standup-brief's sunrise paper. Vanilla HTML/CSS/JS, no
build step, no CDNs; the API base arrives via the config.js injection the
hosting stack has done since phase 1.

Structure follows the joke: Act I choose a story (showcase cards fetched
from GET /showcase, or the bring-your-own-bug textarea with a live 6000-char
counter), Act II choose a voice (tone pills), Dramatize. The result panel
opens with "The curtain rises on", plays the narration in a native audio
element, credits the cast honestly (tone, model, voice), and folds the
original build-log excerpt behind "The true story, as it was actually
logged" - truth beside drama is the product. If audio failed, the panel
says the narrator lost their voice and shows the text anyway. Waiting copy
rotates through four lines including "Consulting the muses. The muses are
rate-limited."

No failures this phase. Verified live after deploy: all four assets serve
200 from CloudFront with the right content types; headless Chrome rendered
the deployed page and the DOM shows all four showcase cards fetched from
the real API, all four tone pills, and the loading note cleared; screenshots
in both light and dark themes look right; Dramatize stays disabled until a
story and tone are both chosen. The generate path itself was already proven
at the API level in phases 3-4 and the page calls the same route the same
way.

## Phase 6: live click-through of both modes (2026-08-14)

The closing test: a real browser driving the deployed site through both
modes end to end, scripted with puppeteer-core against the installed Chrome
(scripts/clickthrough.js, committed; `npm i puppeteer-core` then run it).
The browser-extension route was not connected this session, so the scripted
real browser was the fallback; same Chrome, same site, same clicks.

Everything passed, ten assertions, zero page JS errors:

- Showcase mode: picked the five-token throttle card + Epic fantasy,
  Dramatize enabled only after both picks, generated "The Oath of the Five
  Tokens and the Iron Gate" with honest credits, and the audio REALLY
  played: 94.5s duration, playback clock advanced 2.7s after play(). The
  truth toggle showed the real build-log excerpt (5.76 BILLION and all).
- Bring-your-own-bug mode: typed a fresh on-call-rotation story (281 chars,
  live counter), picked Greek tragedy, got "The Tragedy of the Unread
  Oracle" narrated by Amy, closing line "weep for the proud mortals who
  trust a messenger that speaks only to ghosts".
- Bonus proof nobody planned: the showcase saga was written by
  gemini-3.5-flash-lite, meaning flash-latest failed once mid-test and the
  fallback chain caught it silently through the UI, exactly what it is for.
  The tragedy run went back to flash-latest. Both models are doing real
  work in production.

Full-page screenshots of both completed flows saved during the run. All six
build-order steps are done: the app is live, public, and demoable end to
end at https://d1haw8tkljqm0i.cloudfront.net.
