# UX audit — Marinnex Lab

Phase A of `fdip/docs/prompts/MARINNEX_UX_MASTER_PROMPT.md`. No product code changed.
Observed in a browser (mock mode) and read from source and `openapi.json`.
Before screenshots: `web/audit/before/` at 1440 and 390, light theme.

## 1–2. Journey and information architecture today

One journey, entirely behind a login wall:
`/login → / (Documents) → upload → poll → /documents/:id/analysis → correct → approve → /schemas → test run → /api-keys → /exports-usage`.
Verified working end to end against the real backend.

| Blueprint expects | Today |
| --- | --- |
| Public: Home, How it works, Guide, Developers, Trust | **none** — no front door at all |
| App: Documents, Workspace, Keys, Usage, Guide, Account | Documents, Workspace, Schemas, Keys, Usage |

## 3–8. Problems

| # | Area | Problem | Pri |
| --- | --- | --- | --- |
| 1 | Visual | Primary is indigo `#4f46e5`; the brand is teal (`#08627a` prototype, `#006080` logo). Every token derives from it. | P0 |
| 2 | Visual | `logo.png` unused; the mark is a lucide `LayoutGrid` glyph — the most templated thing on screen | P0 |
| 3 | Visual | No illustration or diagram anywhere; nothing depicts a document until you open one | P1 |
| 4 | First-time | No homepage, welcome, tour, sample or onboarding. A new account lands on an empty table. Part 5's four questions: 1 of 4 answered | P0 |
| 5 | First-time | "FDIP" appears in UI copy; the public brand must be Marinnex Lab | P0 |
| 6 | Usability | Upload zone dominates even with 50 documents | P2 |
| 7 | Usability | No document search (no backend endpoint — `docs/BACKEND_REQUESTS.md` §5) | P2 |
| 8 | Usability | "Processing" is one word, not a staged story | P1 |
| 9 | Usability | Reasons listed flat; nothing says which matters, and no "review next" | P1 |
| 10 | Usability | Row selection counts but does nothing | P2 |
| 11 | Accessibility | Evidence boxes are focusable buttons with **no visible focus style** | P1 |
| 12 | Accessibility | On the page overlay, match class is conveyed by **colour alone** | P1 |
| 13 | Accessibility | No skip link; `prefers-reduced-motion` honoured only by one unused class | P1 |
| 14 | Accessibility | `--text-tertiary` on raised surface ≈ 4.0:1, under AA — needs measuring | P1 |
| 15 | Responsive | **Workspace unusable ≤768 px**: fixed sidebar, top bar collides, field text clipped mid-word (`before/workspace-390.png`) | P0 |
| 16 | Responsive | 768 px: Documents table clips its last column; sidebar never auto-collapses | P1 |
| 17 | Enterprise | No Guide, no Trust page, no Account screen, no visible audit trail | P0/P2 |
| 18 | Enterprise | Terminology drifts: "Usage & exports" vs "Export"; schema vs template undefined | P2 |

**Where it reads as a generic AI dashboard:** the lucide-glyph logo; the four-equal-KPI-card row; "Documents" + one sentence as a page header; nothing on screen depicting paper; and a landing surface that is an upload box plus a table — a tool, not an assistant.

## 9. Components to reuse

`ui/Button`, `ui/Badge`+`Swatch`, `ui/Card`+`CardHeader`+`StatCard`, `ui/Table` (+`THead/TH/TR/TD`, `Skeleton`, `TableSkeleton`, `EmptyState`), `ui/ConfirmDialog`, `StatusBadge`/`MatchBadge`, `UploadZone`, `CodeBlock`, `AuthShell`+`Field`, `layout/Sidebar|TopBar|CommandPalette|AppLayout`+`Page`, `review/PageViewer`+`boxesOf`, `review/FieldPanel`. Plus `lib/format`, `lib/status`, `lib/theme`, `index.css` tokens.

Phase B's component list names `StatusPill` and `PageHeader`. Both already exist under the redesign's names and do exactly that job, so they are reused rather than duplicated: **`StatusPill` = `components/StatusBadge`**, **`PageHeader` = `layout/AppLayout`'s `Page`** (title, description and action in a fixed place). New in Phase B: `ui/VerificationBadge` (+`HelpHint`), `ui/States` (`EmptyState`/`ErrorState`/`LoadingState`/`ScanPulse`), `Logo`, `layout/PublicLayout`, `lib/copy`.

## 10. Must keep working

Login + `?project_id=` scoping + 404-not-403 · upload with `Idempotency-Key`, hash reuse, 2 s polling that stops · evidence overlay measured from the rendered image · corrections as new immutable versions; approve disabled over unsaved edits · decimals rendered from the string, never parsed · scan banner as **info**, mismatch banner, absent fields as "Not on document" never zero · schema + 3–5 test run + untested-version gate · one-time key reveal, derived status, revoke confirm · CSV/XLSX export, usage by month and key · **J/K/E/A** · mock mode · `npm run build` clean, zero `@ts-nocheck`.

## 11. Owner decisions (settled)

| # | Decision |
| --- | --- |
| 1 | **No percentages anywhere**, including hero Scene 5. Verification states per C1. OCR scan-quality band only on OCR evidence. |
| 2 | Public site ships **Home (with "How it works" as a section), Guide, Trust** only. Developers later; the in-app keys screen covers it. |
| 3 | **No SVG logo yet.** Trace `logo.png` to an interim single-colour SVG at `src/assets/marinnex-logo.svg`, recolourable via `currentColor`, marked INTERIM. PNG stays the source. |
| 4 | Brand **teal `#08627a`** with the prototype's earthier `#27865a` success / `#b57920` warning. Token swap first, in Phase B. |

## 12. New sitemap

| Public (no auth) | App (`/app/*`, auth) |
| --- | --- |
| `/` Home — hero animation, how it works, trust strip, CTA | `/app` Documents |
| `/guide` Getting started · API & integration · Advanced | `/app/documents/:id` Workspace |
| `/trust` honest data-processing disclosure (C5) | `/app/schemas`, `/app/schemas/:id` |
| `/login`, `/register` | `/app/api-keys`, `/app/usage` |

Old links redirect: `/documents/:id/analysis` → `/app/documents/:id`, and the other four app paths likewise. `/how-it-works` and `/developers` are deferred per decision 2, which overrides C8.

## 13. Where C1–C10 land

| C | Lands in |
| --- | --- |
| C1 no percentages | `VerificationBadge` (Phase B) → workspace fields, tour step 4, hero Scene 5, Guide |
| C2 invoices only | all copy; Home and Guide; future types only under "Coming later" |
| C3 real JSON | hero Scene 7, built from `samples/examples.json`: decimal strings + ISO dates |
| C4 teal | `index.css` `@theme` (Phase B); AA re-check in both themes |
| C5 trust facts | `/trust` + footer: "AI processing is performed by DeepSeek (servers in China)"; `TODO: owner to confirm` for privacy and retention |
| C6 AutoCount | strategy only; nothing fetched or copied |
| C7 "Select" | schema builder reworded: "Choose the information you need"; schema = "a saved list of the fields you want back" |
| C8 route split | `/app/*` + public routes + redirects (Phase B) |
| C9 errors | friendly message + `code` in a "Details" disclosure; "Contact support" only when `VITE_SUPPORT_URL` is set |
| C10 mobile | ≤768 px workspace becomes Document / Information tabs; selecting a field switches to Document with its highlight |

## 14. Commit plan

| Phase | Contents |
| --- | --- |
| **B** foundation | teal tokens, interim SVG logo, `copy.ts` glossary, route split + redirects, `VerificationBadge`, `StatusPill`, `EmptyState`, `ErrorState`, staged `LoadingState`, `HelpHint`, `PageHeader` |
| **C** public site | Home + 8-scene hero animation (CSS first, reduced-motion static frame, IntersectionObserver pause), Trust |
| **D** first-time | welcome on empty `/app`, 5-step tour with Skip/Back/Next/Finish, `localStorage` seen-flag, empty states everywhere |
| **E** workspace + API | grouped fields with `VerificationBadge` + plain reasons + Edit/Accept, "N fields need your review" with "Review next", mismatch banner, mobile tabs, key warning in the reveal dialog |
| **F** guide + gate | Guide page, readiness checklist, 1440/1280/1024/768/390 × light/dark, keyboard-only pass, reduced motion, axe, Part 16's 12 questions, after screenshots, re-verify "Done when" |

**Risks.** The hero animation is the largest single piece and the likeliest to slip; CSS-first keeps it cheap. The route split touches every `Link` and every Playwright selector. Re-tokenising to teal needs an AA re-check of the six match colours in both themes.
