# Debugging Saga

Your bug deserves a better story than "closed, works now."

Debugging Saga takes a real debugging story (what broke, why, how you fixed it)
and retells it as a dramatic narrated epic, out loud. Gemini does the rewrite,
Amazon Polly does the voice, and your kubeadm typo becomes a tale of betrayal
and redemption.

Built for the AWS Builder Center Weekend Creative Challenge (Aug 14-17, 2026).

## Two modes

- **Showcase:** four of my own real debugging stories, pulled word-for-word from
  the build logs of past projects and pre-loaded as selectable sagas. The facts
  under the drama are all true, which is what makes them funny.
- **Bring your own bug:** paste any debugging story (or honestly any text) and
  get it back as a saga.

Either way you pick a tone: epic fantasy, noir detective, nature documentary,
or Greek tragedy. The rewrite keeps the real technical facts intact inside the
dramatized language. The point is not to invent a story, it is to notice that
your actual Tuesday already was one.

## How it works

```
input text ──> Lambda ──> Gemini (tone transformation)
                  │
                  └─────> Polly (narration) ──> S3 (audio)
                                                   │
frontend <── API Gateway <── saga text + audio url ┘
```

- **Lambda (Python 3.12):** saga generation and speech synthesis
- **Gemini:** the load-bearing AI. Genuine narrative judgment, not decoration
- **Amazon Polly:** the narrator
- **S3:** generated audio
- **API Gateway:** generate + fetch endpoints
- **S3 + CloudFront:** static frontend
- **Secrets Manager:** the Gemini key

No database. A saga is generated, played, and released back into the void,
which is also what happens to most debugging knowledge anyway.

## Status

Backend complete and live: saga generation (Gemini, four tones) and
narration (Polly, one voice per tone) both work end to end.

- Site: https://d1haw8tkljqm0i.cloudfront.net
- API: https://x8wn77svi0.execute-api.us-east-1.amazonaws.com/dev/

The real frontend lands next; until then the site is an honest placeholder
and the API speaks for itself:

```
curl -X POST <api>/generate -H 'Content-Type: application/json' \
  -d '{"showcase_id": "five-token-throttle", "tone": "noir"}'
```

## Infra

CDK (TypeScript), three stacks: data (audio bucket), api, hosting.

```
cd infra
npm install
npx cdk deploy --all
```

Teardown: `npx cdk destroy --all`.
