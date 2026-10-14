# Demo images

Screenshots of Marinnex Lab, captured with Playwright by
[`web/scripts/demo-shots.mjs`](../../web/scripts/demo-shots.mjs).

**Two sources, and the difference matters.** Files numbered `01`–`06` are the
live portal at <https://marinnex.duckdns.org/>. Files numbered `20`–`25` are a
local run in mock mode, because the live account is empty — nobody has uploaded
to it — so a screenshot of it shows an empty state rather than the product.

Nothing here contains a real document. The mock-mode screens are drawn from
`samples/examples.json`, the synthetic fixtures already committed to this
repository, and the API key screen shows truncated key prefixes only — a secret
is displayed once, at creation, and never stored.

## The live portal

| File | What it shows |
|---|---|
| `01-landing.png` · `-mobile` | The public home page: what the product does, how it works, and what comes back |
| `02-guide.png` | The guide |
| `03-trust.png` | Where documents go, stated plainly — including that AI processing happens at DeepSeek, in China |
| `04-sign-in.png` | Sign in |
| `05-invite-only.png` | Sign-up, closed. Registration is invite only in production, so the page says so rather than leaving someone to guess |
| `06-documents.png` | What a new account sees on first sign-in, on the live portal |

## The product, in mock mode

| File | What it shows |
|---|---|
| `20-documents.png` | The document list |
| `21-review-evidence.png` | **The one to look at.** The review screen: the page on the left with the words each value was read from boxed on it, and on the right every field with how it was verified — `Found on page`, `Calculated`, or `Not on document` for a field with nothing printed. The banner reports the one line-item amount that could not be located, which is why the document is held for a person instead of being passed on |
| `22-schemas.png` | Schemas and their immutable versions |
| `23-api-keys.png` | Keys, and the generated call for your own code |
| `24-usage.png` | Pages and AI cost |
| `25-account.png` | Change your own password, and the account activity log |

## Re-capturing them

From `web/`, with the dependencies installed:

```bash
# the live portal, public pages only
node scripts/demo-shots.mjs

# the live portal including the signed-in pages
PORTAL_EMAIL=you@example.com PORTAL_PASSWORD=... node scripts/demo-shots.mjs

# the product screens, against a local mock-mode dev server on :5173
VITE_USE_MOCKS=true npm run dev          # in another terminal
SET=product BASE=http://localhost:5173 node scripts/demo-shots.mjs
```

Credentials are read from the environment and never written to a file. The
script refuses to save a screenshot of a page it could not reach, rather than
filing a redirect to the sign-in screen under the name of the page it was meant
to show.
