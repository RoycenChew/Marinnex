# Marinnex Lab — Human-Centered Enterprise UX Design Package

This package is a design/implementation starter kit for redesigning Marinnex Lab's
Intelligent Document Processing (IDP) product for financial documents.

## Core idea

Marinnex Lab should feel like:

> A helpful financial document assistant.

Not:

> A generic AI dashboard.

The product journey is:

**Upload → Understand → Extract → Review → Select → Use**

## Reference philosophy

AutoCount Malaysia is used ONLY as a reference for collecting product/UX ideas:
- clear business communication
- strong navigation
- practical product discovery
- helpful resources
- obvious calls to action
- professional enterprise presentation
- approachable onboarding

Do NOT copy AutoCount's:
- branding
- colors
- layouts
- text
- illustrations
- components
- assets
- page structure

Build an original Marinnex Lab experience.

## Package contents

- `prompts/MASTER_UI_UX_PROMPT.md`
  Full Claude Code redesign prompt.
- `prompts/HOME_AND_VIDEO_PROMPT.md`
  Homepage + animation/video direction.
- `prompts/FIRST_TIME_USER_PROMPT.md`
  Onboarding and guide experience.
- `prompts/ENTERPRISE_READINESS_PROMPT.md`
  Enterprise UX quality gates.
- `design/PRODUCT_UX_BLUEPRINT.md`
  Product architecture, sitemap and user journey.
- `animation/marinnex-document-flow.html`
  Standalone HTML/CSS/JS animation prototype.
- `animation/README.md`
  How to convert the prototype into React/Next.js.
- `assets/marinnex-lab-logo.png`
  Supplied Marinnex Lab logo.

## Recommended Claude Code workflow

1. Give Claude Code `MASTER_UI_UX_PROMPT.md`.
2. Ask it to inspect the existing project before changing anything.
3. Ask it to create a UX audit and implementation plan.
4. Review the plan.
5. Then let Claude implement.
6. Use `HOME_AND_VIDEO_PROMPT.md` for the homepage hero/animation.
7. Use `FIRST_TIME_USER_PROMPT.md` for onboarding.
8. Use `ENTERPRISE_READINESS_PROMPT.md` as the final quality gate.

The animation prototype is intentionally technology-light. It demonstrates the
concept without forcing a particular framework.
