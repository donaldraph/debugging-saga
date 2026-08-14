# Debugging Saga: your bug deserves a better story than "closed, works now"

*Built for the AWS Builder Center Weekend Creative Challenge, August 2026.*

**Try it: https://d1haw8tkljqm0i.cloudfront.net**
**Source: https://github.com/donaldraph/debugging-saga**

The least-read literature in software is the postmortem. We fight a bug for
two days, uncover a root cause of genuine cosmic irony, write it up in a
build log, and nobody ever reads it again, including us. Which is a shame,
because some of these stories are good. Not "good for a ticket comment"
good. Actually good.

Debugging Saga takes a true debugging story, what broke, why, and how it got
fixed, and retells it as a dramatic saga, read aloud by a narrator. Gemini
does the writing. Amazon Polly does the voice. You do the suffering, but you
did that part already.

## What it does

Two modes:

**The showcase.** Four of my own real debugging stories, pulled word for word
from the build logs of my last three challenge projects, pre-loaded as
selectable sagas. More on why this matters in a second.

**Bring your own bug.** Paste any debugging story and get it back
transformed.

Either way, you pick a tone: epic fantasy, noir detective, nature
documentary, or Greek tragedy. Each tone gets its own Polly voice, because a
noir monologue in a cheerful accent is a crime against the genre. Brian
narrates the epics, Matthew handles noir, Arthur does nature documentaries,
and Amy delivers the tragedies. The result plays as audio next to the
generated text, with the original log entry folded underneath, labelled "the
true story, as it was actually logged."

## The rule that makes it work: the facts are load-bearing

The easy version of this app invents a fun story vaguely inspired by your
input. That version is worthless. The whole joke of Debugging Saga is that
the story is TRUE. The dramatization is a costume; the body underneath is
your actual Tuesday.

So the prompt has hard rules, in priority order. Every technical fact
survives: what broke, what the error actually said, the real root cause, the
real fix. No invented failures, no imagined heroics. Real system names stay
recognizable (epithets are allowed, so API Gateway may be crowned "API
Gateway the Unbending", but the true name must appear). And the real numbers
must survive, because the numbers are usually the funniest part. Nobody can
improve on being denied a 5-token request against a quota of 5.76 billion.

That last example is one of the four showcase stories, from my standup-brief
build in July: a 5-token test call to Bedrock Nova Micro rejected for "too
many tokens per day," where the real wall turned out to be an opaque
account-level allowance, and the support case to fix it could not even be
filed by API because that requires a support subscription. Here is what
Gemini did with it in epic mode:

> Yet when the tiny offering of five tokens was cast into the abyss, a
> dreadful prophecy struck: ThrottlingException, declaring too many tokens
> per day, commanding the hero to wait... False prophets whispered of the
> per-model limit, a fortress sworn to hold five point seven six billion
> tokens each day, untouched and immense. But the true curse was darker.

Every beat of that is true. That is the product.

The other three showcase sagas are equally real: calendars that kept
vanishing into the wrong Google account on a shared machine, a kubeadm
config schema that my own notes had recorded backwards, and a three-round
fight with API Gateway's 29-second timeout. My build logs were already
written in symptom, root cause, fix, reasoning format for every project, so
the raw material was sitting there waiting to be dramatized.

## The architecture, kept deliberately small

The challenge's own advice was not to over-engineer, and this app is
genuinely simple:

- **Lambda (Python 3.12)** runs generation: one function calls Gemini, then
  Polly, then S3
- **Gemini** does the tone transformation (gemini-flash-latest primary,
  gemini-3.5-flash-lite fallback)
- **Amazon Polly** narrates with neural voices, one per tone
- **S3** holds the MP3s, served by presigned URL from a private bucket, with
  a 7-day lifecycle expiry
- **API Gateway** exposes POST /generate and GET /showcase, both public,
  with a narrow stage throttle
- **S3 + CloudFront** host the frontend (vanilla HTML/CSS/JS, no build step)
- **Secrets Manager** holds the Gemini key
- **CDK (TypeScript)** defines all of it in three stacks

There is no database. A saga is generated, played, and gone, which felt
thematically correct: that is also what happens to most debugging knowledge.

Two design choices earned their keep. First, generation is synchronous,
which sounds reckless given that one of my showcase stories is literally
about API Gateway killing slow requests at 29 seconds. But I measured before
deciding: the primary model runs 5 to 13 seconds and the fallback about 3,
so the chain fits with room, and the async pattern from that older war story
is documented in the build log as the known fix if it ever stops fitting.
Second, there is no fake fallback. Creative writing has no deterministic
plan B, so if every model fails, the API returns an honest 503 that says the
narrator is unavailable. This app never presents non-AI output as AI output.

## The bug the build donated to the genre

An app about debugging stories would obviously generate its own. After
deploying the new routes, both returned 403 "Missing Authentication Token"
while the health route worked fine. The routes existed. The methods existed.
I could see them in the console.

Root cause: the API Gateway stage was still serving a deployment snapshot
taken before the new methods landed, and API Gateway reports a route it does
not know as an authentication error, which is world-class misdirection. One
manual create-deployment fixed it. The lesson, now recorded in my build log
where future me will fail to read it: "Missing Authentication Token" on a
route you just added has nothing to do with authentication.

## The test that proved more than it meant to

The final check was a scripted click-through of the deployed site in a real
browser: pick a story, pick a tone, generate, and assert that the audio
actually plays, not just that a URL exists. The playback clock advanced 2.7
seconds after play(), so the narration genuinely narrates.

Then the test told on itself in the best way. The credits line under the
generated saga read "written by gemini-3.5-flash-lite." I had cast
flash-latest as the primary writer. The primary had failed mid-test, and the
fallback chain had caught it so quietly that the only evidence was the
honest credits line, which exists precisely because I wanted the app to
never lie about which model did the work. The next run went back to
flash-latest. Both models carry real traffic, and I have a screenshot of the
understudy taking the stage.

## Try it with your own bug

Paste your worst debugging story into the app and give it the tragedy
treatment. Mine ended with a chorus warning: "weep for the proud mortals who
trust a messenger that speaks only to ghosts." It was about a stale on-call
rotation.

The truth was already funny. It just needed a narrator.
