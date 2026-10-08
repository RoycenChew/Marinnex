# Master prompt: Marinnex Lab UX redesign

**For Claude Code, working in `fdip/`.** Your job is to apply the owner's UX package to
the existing web app in `fdip/web/`.

The package is in `fdip/docs/ux/`:
- `README.md`
- `design/PRODUCT_UX_BLUEPRINT.md`
- `prompts/MASTER_UI_UX_PROMPT.md`
- `prompts/HOME_AND_VIDEO_PROMPT.md`
- `prompts/FIRST_TIME_USER_PROMPT.md`
- `prompts/ENTERPRISE_READINESS_PROMPT.md`
- `animation/marinnex-document-flow.html`
- `assets/marinnex-lab-logo.png`

Read all of it first. It is the owner's design intent. It holds the design direction:
- tone
- page structure
- copy
- onboarding
- tour
- guide
- animation storyboard
- quality gate

**This file wins over the package wherever they disagree.** Section 2 lists the known
conflicts. They exist because the package was written without knowledge of the real
backend.

---

## 1. Ground rules

1. **Where you may write:**
   - Edit only inside `fdip/web/`, plus `fdip/web/UX_AUDIT.md` and
     `fdip/web/BACKEND_REQUESTS.md`.
   - Copy the logo into `fdip/web/src/assets/`.
   - Never touch the backend, migrations, tests, `pyproject.toml`, `.env*` outside
     `web/`, the toolkit or the benchmark.
2. **Git:**
   - Work on a new branch, `ux-marinnex`, created from the current `ui-redesign`.
   - If the backend pass from the last task (`document_type` derived; type gate on
     interactive upload; `response_model` and `project_id` in OpenAPI) is uncommitted
     or unfinished, report that first and stop.
   - Commit after each phase in §4. Never push.
3. **Keep what works:**
   - Every flow from the current "Done when" checklist must keep working: login,
     upload, review with highlights, correct, approve, schema, test run, key, export.
   - The keyboard shortcuts must keep working: J, K, E, A.
   - Keep zero `@ts-nocheck`, generated OpenAPI types, mock mode, and
     `npm run build` green.
4. **Reuse:** reuse the existing stack (Tailwind v4 `@theme` tokens, shadcn/ui,
   lucide, recharts, sonner, cmdk, react-resizable-panels). For animation:
   - Use CSS first.
   - Use `motion` (Framer Motion) only if CSS cannot do the job.
   - No video files, no Lottie, no tour library heavier than about 10 kB. A small
     custom tour component is fine.
5. **Facts only:**
   - Every claim in the UI must be true of this backend today. When unsure, check
     `openapi.json`, `API_CONTRACT_FOR_UI.md` or the backend code (read-only).
   - If the UI needs something the backend does not provide, add it to
     `BACKEND_REQUESTS.md` and build a clearly marked fallback. Never fake data.

---

## 2. Corrections to the package (these override it)

| # | Package says | Reality | Do this instead |
| --- | --- | --- | --- |
| C1 | "96% confidence" / "68% confidence" on each field | The backend has **no calibrated per-field confidence**. It returns a match class (`exact`, `normalized`, `derived`, `fuzzy_ocr`, `not_found`, `not_checked`), a field status, `reasons`, and for OCR evidence a minimum OCR word confidence. A made-up % would be an accuracy claim, which the package itself forbids. | Show **verification states**, never percentages: "Found on page" (exact/normalized), "Calculated" (derived), "Possible misread, please check" (fuzzy_ocr), "Not on document" (not_found), "Not checked" (not_checked). Add the field status (Accepted / Needs review) and the reason in plain words. For OCR fields only, you may show "Scan quality: low / medium / high", banded from the OCR confidence, with a tooltip saying it measures how clearly the text was read, not whether the value is right. Every state has an icon and text, never colour alone. Apply this everywhere: workspace, tour step 4, homepage animation, guide. |
| C2 | "Invoices, receipts, statements and supported financial documents" | **Invoices only** today. Bank statements are a later phase. Receipts are not supported. | All copy says "invoices". Use cases may list future types only under a clearly labelled "Coming later" with no dates. |
| C3 | Animation JSON `"total": 10600.00` | The API returns money as **decimal strings plus an ISO currency code**, and dates as ISO strings. | Build the animation's JSON from a real example in `samples/examples.json` (shortened). Field names must match the real contract. |
| C4 | Teal brand direction | The current tokens use an indigo primary. | Switch the primary to the package's teal (`#08627a`, dark `#06485a`), with a full 50–950 scale derived from it. Re-check AA contrast in light and dark mode. The status colours stay semantic. |
| C5 | Trust and privacy messaging | Data is processed by DeepSeek, whose servers are in China. Storage is currently local, with Malaysia hosting planned and not live. There are no certifications and no stated retention policy. | The Trust page and footer state only the true facts, e.g. "AI processing is performed by DeepSeek (servers in China)". Never claim Malaysian data residency, encryption at rest, compliance or certifications. Leave a clearly marked `TODO: owner to confirm` placeholder for the privacy policy and retention. |
| C6 | AutoCount as a reference | It is a real company, and your shell may not reach the site. | Use it as a strategy reference only, through the principles already in the package. Do not fetch, screenshot or copy anything from it. |
| C7 | Field selection: "Select → Use" | Selection is the **schema builder**: tick template fields, create a schema version, run a test, then create a key. | Present "Select" as "Choose the information you need", explained in plain words, and keep the existing endpoints. Explain a schema in plain words: "a saved list of the fields you want back". |
| C8 | Public pages (Home, How it works, Guide, API docs, Trust) | The app is currently login-only. | Add public routes that need no login (`/`, `/how-it-works`, `/guide`, `/developers`, `/trust`). The app moves under `/app/*`, and old links redirect. Public pages must never call authenticated endpoints. |
| C9 | Error copy, e.g. "Contact Support" | There is no support channel yet. | Show "Contact support" only if `VITE_SUPPORT_URL` is set; otherwise hide it. Every friendly error message keeps the RFC 9457 `code` visible in a small "Details" disclosure for developers. |
| C10 | Mobile at 390 px | The review workspace needs width. | On screens 768 px and below, the workspace becomes two tabs ("Document" / "Information"), and selecting a field switches to the Document tab with its highlight. Public pages are fully responsive. The app shell is usable at 390 px but optimised for 1024 px and above. |

---

## 3. Product language

- Public brand: **Marinnex Lab**. "FDIP" stays an internal name: never in the UI, only
  in code and docs.
- Use the human tone and word swaps in `FIRST_TIME_USER_PROMPT.md` everywhere, e.g.:
  - "Your document is ready to review"
  - "Create an API key"
  - "Reading your document…" and the other staged loading messages, which should
    follow the backend's real processing steps where the API exposes them
- Keep one glossary in `src/lib/copy.ts`, holding every user-facing term and status
  label in one place: document, field, needs review, verified, schema, API key, test
  key, live key.

---

## 4. Phases (stop after Phase A for approval)

### Phase A: audit and plan (no product code)

Write `fdip/web/UX_AUDIT.md`. Keep it to 2 pages at most: tables, not essays. It covers
the 12 points from `MASTER_UI_UX_PROMPT.md` Part 2, plus:
- the new sitemap (public and app routes)
- where each conflict C1–C10 lands in the UI
- which existing components you will reuse
- the commit plan for Phases B–F

Take Playwright screenshots of the current app (light theme, at 1440 and 390) into
`web/audit/before/`. Then **stop and wait for the owner's OK.**

### Phase B: foundation

- Teal tokens (C4), logo, `copy.ts` glossary, and route split (C8).
- Shared components:
  - `VerificationBadge`, which implements C1
  - `StatusPill`
  - `EmptyState`, `ErrorState` and staged `LoadingState`
  - `HelpHint`: a "?" with a one-line explanation
  - `PageHeader`
- Commit.

### Phase C: public site

- Homepage with the 11 sections from the blueprint, adapted by C2 and C5.
- Hero animation: port `marinnex-document-flow.html` into a React component, following
  the eight scenes in `HOME_AND_VIDEO_PROMPT.md` with C1 and C3 applied. It must:
  - respect `prefers-reduced-motion` by showing a static final frame
  - pause when off screen (IntersectionObserver)
  - not block interaction
- Also build How it works, Trust (C5) and Developers. Commit.

### Phase D: first-time user experience

- Welcome screen on the first visit to `/app` when the user has no documents. Its
  primary action is "Upload my first document"; the secondary is "Take a 1-minute
  tour".
- The five-step tour from Part 6, with Skip, Back, Next and Finish. Store "seen" per
  user in `localStorage`; this is a UI preference only, never data.
- Never auto-start the tour again.
- Empty states on every list.
- Commit.

### Phase E: document workspace and API experience

- Workspace layout per the blueprint §7, using the existing split view and highlights.
- Fields are grouped, with `VerificationBadge` (C1), the reason in plain words, and
  Edit / Accept.
- Top banner: "N fields need your review" with "Review next", which jumps through them
  in order.
- On document type mismatch, a plain-language banner, e.g. "This doesn't look like an
  invoice".
- API journey from Part 10 on the existing keys screen and Developers page. The
  warning about never exposing keys appears in the one-time key dialog.
- Commit.

### Phase F: Guide, quality gate and finish

- Guide page with the sections from Part 9, in simple English. All facts must match
  C1–C5.
- Run `ENTERPRISE_READINESS_PROMPT.md` as a checklist. Test:
  - widths 1440 / 1280 / 1024 / 768 / 390
  - light and dark themes
  - keyboard-only walkthrough
  - reduced motion
- Run axe or Lighthouse accessibility on Home, Documents and Workspace. Fix anything
  serious or critical.
- Answer the 12 first-time-user questions from Part 16 honestly, yes or no. Fix every
  "no" or explain why it can't be fixed.
- Take after screenshots into `web/audit/after/`.
- Make sure the current "Done when" checklist still passes against the real backend.
- Commit.

---

## 5. Final report (15 lines at most), then stop

- Phases done; commits; files changed
- Gate results: readiness checklist, the 12 questions, accessibility score
- Anything not built, and why
- New `BACKEND_REQUESTS.md` items
- Owner decisions still needed, e.g. the privacy text, support URL and retention
  policy

No push and no merge: the owner reviews the screenshots and decides.
