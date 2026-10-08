# Marinnex Lab — quality gate

Phase F of `MARINNEX_UX_MASTER_PROMPT.md`. Everything below was run on this
machine against the **real backend** (uvicorn + worker, `FDIP_PROVIDER_MODE=mock`)
with the UI in `VITE_USE_MOCKS=false`, except where it says mock mode. Scripts are
in `web/audit/`; screenshots in `web/audit/after/` (56 files — that folder is
git-ignored, so they are on disk, not in the commit).

## Part 16 — the twelve first-time-user questions

| # | Question | Answer | Evidence |
| --- | --- | --- | --- |
| 1 | Understand the product? | Yes | `/` states what it does in one sentence, then shows a run of it. `audit/after/home-1440-light.png` |
| 2 | Know what to click? | Yes | One primary CTA per screen; an empty account gets the welcome rather than a zeroed dashboard |
| 3 | Upload a document? | Yes | `audit/realbackend.mjs` step 4: a real `invoice_digital.pdf` through the UI |
| 4 | Understand processing? | Yes | Staged messages from `PROCESSING_STEPS`, driven by `job.stage` where known, a timer otherwise |
| 5 | Understand extraction? | Yes | Fields grouped Header / Totals / Line items, each with its value and how it was checked |
| 6 | Identify uncertain information? | Yes | Verification states, the "N fields need your review" banner, and Review next |
| 7 | Verify a result? | Yes | Selecting a value highlights the words it came from — verified on the real page image, `audit/after/real-workspace.png` |
| 8 | Select information? | Yes | `audit/q9q11.mjs`: the schema builder loads the real 26-field template |
| 9 | Export / use data? | Yes | `audit/q9q11.mjs`: CSV and Excel controls on Usage |
| 10 | Find the API? | Yes | A "Developers" group in the sidebar, and the integration journey on the keys screen |
| 11 | Create an API key? | Yes | `audit/q9q11.mjs`: created against the real backend, revealed once, with the exposure warning |
| 12 | Find help? | Yes — **this was the one "no"** | The guide existed only on the public site, which a signed-in user has no reason to revisit. "Guide and help" is now in the sidebar and the ⌘K palette |

## Enterprise readiness checklist

| § | Item | Result |
| --- | --- | --- |
| 1 | Product clarity | Pass — the homepage explains it without jargon |
| 2 | Navigation: Documents, Guide, API, keys, help | Pass, **after** fixing help (Q12 above) |
| 3 | Upload / processing / completion / failure / retry | Pass — `ErrorState` carries a retry and the RFC 9457 code behind a disclosure |
| 4 | Value vs. verification vs. needs review vs. verified | Pass — one vocabulary, in `copy.ts`, used by workspace, homepage, tour and guide |
| 5 | Source traceability | Pass — evidence boxes measured against the rendered page |
| 6 | No unsupported claims | Pass — no percentage anywhere; `/trust` lists what is *not* true |
| 7 | Accessibility | Pass — see below |
| 8 | Responsive 1440 / 1280 / 1024 / 768 / 390 | Pass — 8 pages × 5 widths × 2 themes, no horizontal overflow, no page errors (`audit/after.mjs`) |
| 9 | Loading / success / empty / error / retry | Pass — every list has an empty state; Usage was the last one without |
| 10 | Animation performance | Pass — the hero pauses off screen, holds a still frame under reduced motion, and takes no pointer events |
| 11 | Design consistency | Pass — radii, spacing, colour and type all come from tokens in `index.css` |
| 12 | Enterprise readiness | See the final question |

## Accessibility

axe-core (`wcag2a`, `wcag2aa`, `wcag21a`, `wcag21aa`) over Home, Guide, Trust,
Documents, Workspace and API keys, in **both themes**: **no serious or critical
violations**. Ten were found and fixed:

- `--text-tertiary` failed AA in both themes — 4.34:1 on the light sunken
  surface, 3.07:1 on the dark overlay. Both are now measured values that clear
  4.5 on every surface in their theme.
- Dark-mode danger text measured 4.35:1 over its own tinted banner. A lighter
  `--color-danger-400` is now used for foregrounds in that theme.
- Two links sitting inside paragraphs were distinguished by colour alone; they
  are underlined.

Keyboard (`audit/keyboard.mjs`): the skip link is the first tab stop, the hero
CTA is reachable by Tab alone, focus is a visible 2px outline, J/K/E/A work in
the workspace, and the tour takes arrow keys and closes on Escape.

Reduced motion (`audit/reducedmotion.mjs`): zero animating elements on Home,
Guide, Documents and Workspace.

## Known gaps

- `fuzzy_ocr` and OCR scan-quality bands are exercised in **mock mode only**:
  the sample corpus here produces a clean digital invoice, and Tesseract is not
  on this machine's PATH. The code path is the same one the badge uses
  everywhere else.
- "Mark as checked" is the reviewer's own list for one sitting. There is no
  per-field endpoint, so it is not persisted — logged in `BACKEND_REQUESTS.md`.
- Screenshots in `audit/after/` are not versioned, because `web/.gitignore`
  excludes `audit/`.

## The final question

> Would a finance employee trust this interface enough to process a real
> document?

Yes, and for one reason: it never claims more than it can show. There is no
confidence score to misread, every value points back at the words it came from,
the arithmetic is checked in code, and a scan is always seen by a person. The
Trust page states where documents are processed and lists what the system does
not have. The honest answer is the trustworthy one.
