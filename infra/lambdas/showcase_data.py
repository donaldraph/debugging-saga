"""The four showcase stories, pulled from the real BUILD_LOGs.

Every `story` below is stitched from the actual log entries of the named
project (light trims for length, no invented events). That is the point of
the showcase: the drama is added, the facts are not. Owner approved these
four picks on 2026-08-14 before any code was written.
"""

SHOWCASE = [
    {
        "id": "calendar-account-mixup",
        "title": "The calendar-account mixup",
        "project": "convene",
        "date": "2026-07-31",
        "teaser": "Four rounds of created calendars kept vanishing into the "
                  "wrong Google account.",
        "story": """\
Symptom: four rounds of "create Academic + Community calendars" all ended
with the sync reporting the calendars not found, even after OAuth was pointed
at the right account.

Root cause, uncovered by enumerating events per calendar via the API: on a
shared machine with several Google accounts signed in, calendar and event
creation kept landing in whichever account the browser had active, not the
connected one. The refresh token first belonged to one account (empty), was
re-minted for a second account (which held the real AWS events on its PRIMARY
calendar), but the "Academic" and "Community" sub-calendars never appeared
because they were made elsewhere. Ultimately the owner added everything to ONE
calendar (primary), distinguishing type by event title ("academic",
"outreach", "tour").

Fix, checkpointed with the owner before deviating: added a second source mode.
The calendar client now resolves the literal name "primary", and sync gained a
split mode that reads ONE calendar and classifies each event academic vs
community by a title tag. Deployed with splitCalendar=primary. The
two-calendar mode is still there for anyone who keeps them separate.

Reasoning: matching how the user actually keeps their calendar beats making
them restructure it, and single-calendar-with-tags is arguably the more
realistic student setup. Live proof on real data: sync returned mode=split,
academic 2 / community 2 events, and detected 2 hard conflicts - an
"Academic" event colliding with both "outreach" and "tour" at the same time
on August 1. A second sync returned open_new 0 / still_open 2 / cleared 0,
proving the machinery held on real data.""",
    },
    {
        "id": "five-token-throttle",
        "title": "The five-token throttle",
        "project": "standup-brief",
        "date": "2026-07-10",
        "teaser": "Denied 5 tokens against a quota of 5.76 billion a day.",
        "story": """\
Symptom: a tiny 5-token test call to amazon.nova-micro-v1:0 on Bedrock
returned ThrottlingException: Too many tokens per day, please wait before
trying again.

Root cause: this is NOT the per-model Service Quota. The per-model "tokens
per day" quota for Nova Micro defaults to 5.76 BILLION per day and is not
adjustable via the Service Quotas API. The throttle is an account-level daily
on-demand token allowance tied to account standing - a separate, opaque limit
raised only through an AWS Support case. Model access was confirmed enabled:
this was a throttle, not an AccessDenied. The actual footprint was tiny - one
brief is a few thousand tokens, well under 0.02% of the model quota. The
model quota was never the constraint.

Everything up to the model call was verified working with real data: 23 real
commits fetched from GitHub, the prompt built all four sections correctly.
The live Nova call failed after 4 retries, on both the direct model and the
cross-region inference profile - the profile does not bypass the account
allowance.

The fix path: file an AWS Support case to raise the account's on-demand daily
token limit. Except the case could not be filed via API, because the account
is on Basic support - the AWS CLI returned SubscriptionRequiredException. So
the support case asking for more tokens required a support subscription. It
was drafted as a document with exact copy-paste text for a console
submission instead.

Not faked: no placeholder brief was written to the database to make the
pipeline look done. Generation stayed honestly blocked until the allowance
freed up, and the UI showed the real reason.""",
    },
    {
        "id": "schema-betrayal",
        "title": "The schema that betrayed its own notes",
        "project": "study-conscience",
        "date": "2026-07-16",
        "teaser": "kubeadm rejected the config exactly the way my own note "
                  "said it wouldn't.",
        "story": """\
Recreating a kind Kubernetes cluster at v1.35.1 with audit logging enabled.
Three snags, in order.

Snag A: kind create and delete errored with "failed to lock config file:
open /home/user/.kube/config.lock: permission denied", and kubectl config
get-contexts was empty. Root cause: the ~/.kube directory was owned by
root:root, so the user could not create files inside it. This predated the
project and was why the context was empty from the start. Fix: chown the
directory back. Fixing ownership repairs the whole kubectl workflow, not just
this project; a repo-local workaround would have left two competing
kubeconfigs on a shared box.

Snag B: the recreate pulled kindest/node v1.36.1, not the v1.35.1 the old
cluster and the certification exams use. Root cause: the first config did not
pin a node image, so kind used its newer default. Fix: pinned the image.
Exam parity matters more than newest.

Snag C, the betrayal: the recreate then failed inside kubeadm with "cannot
unmarshal array into ... extraArgs of type map[string]string". Root cause:
kind emits kubeadm ClusterConfiguration as v1beta3 for v1.35.1, where
extraArgs is a MAP. The v1beta4 list-of-name-value form (correct for v1.36
and later) is rejected. And the build note recording which form was which
had it BACKWARDS - the config was written from the note, and the note was
wrong. Fix: used the map form, and documented the version split in the
config comment "so future me does not flip it again". The failure mode is
loud (kubeadm refuses to init), so no silent drift, but it cost a full
cluster recreate.""",
    },
    {
        "id": "29-second-guillotine",
        "title": "The 29-second guillotine",
        "project": "convene",
        "date": "2026-07-31",
        "teaser": "Three escalating defeats against a timeout that cannot be "
                  "negotiated with.",
        "story": """\
The AI recommendation endpoint died three ways in a row.

First: the local smoke test returned the honest deterministic fallback
instead of AI, because the default model now 503'd hard under load for this
key. Fix: tested five models three times each with the real response schema.
Two held up. Made the sharp one primary with an automatic fallback to the
solid one.

Second: the first live POST returned "Endpoint request timed out". Root
cause: API Gateway REST APIs kill ANY request at 29 seconds, and the model
budget (45 seconds plus retries plus fallback) exceeded it. Fix: one tight
attempt per model at 12 seconds, letting the model chain be the resilience -
a 503 returns fast, so falling to the next model beats backing off in place.

Third: after that, BOTH models timed out at 12 seconds. Root cause: a 10-day
window yields 223 half-hourly free slots, and asking the model to rank all
223 made a huge prompt and an enormous generation. Fix: down-sample to an
evenly-spread 18 before the call. Ranking 200 near-duplicate slots is
pointless and slow.

Even then, on free-tier latency the endpoint only succeeded 2 to 4 times in
6. The final fix: stop standing under the guillotine. The endpoint went
asynchronous - the API handler computes the deterministic part fast, writes a
PENDING record, invokes a worker Lambda, and returns a pending id in about 2
seconds. The worker does the model ranking with a full 60-second timeout and
flips the record to done; the dashboard polls until it is. The 29-second cap
is a property of API Gateway, not of the work. Decoupling the slow call from
the request removed the cliff entirely instead of shaving timeouts to barely
fit, and the feature became reliable.""",
    },
]

SHOWCASE_BY_ID = {s["id"]: s for s in SHOWCASE}
