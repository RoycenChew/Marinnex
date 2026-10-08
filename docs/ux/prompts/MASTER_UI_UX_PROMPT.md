# CLAUDE CODE MASTER PROMPT
# Marinnex Lab — Human-Centered Enterprise Financial IDP UX

You are a Senior Product Designer, UX Architect, Design Systems Engineer and
Frontend Architect.

Your task is to redesign the existing Marinnex Lab Intelligent Document
Processing product into a human-centered, attractive, scalable and
enterprise-ready experience.

## IMPORTANT REFERENCE RULE

Use AutoCount Malaysia as a DESIGN REFERENCE ONLY.

Reference:
https://www.autocountsoft.com/

Study it to collect ideas about:
- business-oriented communication
- navigation
- product discovery
- CTA hierarchy
- resources
- trust
- practical workflows
- professional SaaS presentation
- first-time-user communication

DO NOT copy its visual identity, layout, components, text, illustrations,
branding or page structure.

We are learning from the product/UX strategy and then creating an ORIGINAL
Marinnex Lab experience.

---

# PART 1 — UNDERSTAND BEFORE CODING

Before changing code, inspect:

- README
- architecture documents
- package.json
- source tree
- routes
- components
- styles
- design tokens
- authentication
- API integration
- document processing
- extraction schema
- document viewer
- API key implementation
- existing loading/error states
- current responsive behavior

Do not destroy working functionality.

Do not invent backend functionality.

Do not invent API endpoints.

Do not claim unsupported document types.

---

# PART 2 — CREATE A UX AUDIT

Create:

`UX_AUDIT.md`

Include:

1. Current user journey
2. Current information architecture
3. Current visual problems
4. Current usability problems
5. First-time-user problems
6. Accessibility problems
7. Mobile/responsive problems
8. Enterprise UX gaps
9. Reusable components
10. Existing functionality that must be preserved
11. Recommended changes
12. Priority: P0 / P1 / P2

Identify where the current UI feels like a generic AI-generated dashboard.

---

# PART 3 — DESIGN PHILOSOPHY

The product should feel like:

> A helpful financial document assistant.

Not:

> A generic AI dashboard.

The core journey is:

UPLOAD
↓
UNDERSTAND
↓
EXTRACT
↓
REVIEW
↓
SELECT
↓
USE

---

# PART 4 — HOMEPAGE

Build a strong homepage.

Hero headline:

> Turn Financial Documents Into Usable Data.

Supporting message:

> Upload your financial document. Let AI extract the information.
> Review what matters. Use the data anywhere.

Primary CTA:

> Process Your First Document

Secondary CTA:

> See How It Works

The hero MUST visually demonstrate the product.

Do not use a generic AI illustration.

Show:

Document
→ AI scanning
→ extracted fields
→ confidence
→ review
→ structured data
→ API

---

# PART 5 — FIRST-TIME USER EXPERIENCE

A first-time user should understand the product in approximately 10 seconds.

Answer:

- What does this do?
- What do I upload?
- What happens next?
- What will I receive?

First entry:

> Welcome to Marinnex Lab

> Let's process your first financial document.

Show:

1. Upload
2. AI extraction
3. Review
4. Use your data

Actions:

- Upload My First Document
- Take a 1-minute Tour

---

# PART 6 — PRODUCT TOUR

Create a guided tour.

Step 1:
> Upload your financial document here.

Step 2:
> Your original document stays visible while you review the extracted information.

Step 3:
> These are the values our AI found.

Step 4:
> Confidence helps you decide which fields need attention.

Step 5:
> Review the result, then export or integrate your data.

Allow:
- Skip
- Back
- Next
- Finish

Do not force the tour on every visit.

---

# PART 7 — DOCUMENT WORKSPACE

Create a professional document-processing workspace.

Desktop:

Left:
Original document

Right:
Extracted information

Each extracted field should support, where technically possible:

- value
- confidence
- source page
- source location
- review state
- edit
- validation

Example:

Invoice Number
INV-2026-001
96% confidence

Tax
RM 600
68% confidence
Needs review

---

# PART 8 — HUMAN REVIEW

This is a core product principle.

Do not simply show:

> Extraction completed.

Show:

> Your document is ready to review.

For uncertain information:

> Needs review

Explain why when possible.

If source coordinates exist, clicking an extracted field should highlight
the corresponding source in the document.

---

# PART 9 — GUIDE

Create a Guide page.

Sections:

Getting Started
- What is Marinnex Lab?
- Uploading your first document
- Understanding results
- Reviewing fields
- Selecting information
- Exporting data

API & Integration
- Creating an API key
- Authentication
- First request
- Response format
- Error handling

Advanced
- Supported documents
- Confidence
- Validation
- Troubleshooting
- Best practices

Use simple English.

---

# PART 10 — API

Create an approachable API experience.

Explain:

> API keys allow your application to connect to Marinnex Lab and receive
> structured document information.

Then:

Create API Key
→ Copy
→ First Request
→ Response
→ Integration Guide

Security warning:

> Never expose your API key in frontend code or public repositories.

Only implement claims that match the actual backend.

---

# PART 11 — TRUST

Financial documents require trust.

Communicate:

- transparency
- human review
- source traceability
- controlled actions
- privacy information
- processing status

Do NOT invent:
- certifications
- compliance
- encryption
- retention
- accuracy percentages

Only use verified implementation facts.

---

# PART 12 — DESIGN SYSTEM

Use the supplied Marinnex Lab logo.

Create reusable tokens for:

- typography
- spacing
- radius
- borders
- shadows
- buttons
- inputs
- badges
- cards
- alerts
- document fields
- confidence states
- navigation

Visual direction:

professional
calm
human
financial
trustworthy
modern

Avoid excessive:
- gradients
- glassmorphism
- neon
- AI sparkles
- particles
- decorative animation

---

# PART 13 — ANIMATION

Animation must explain functionality.

Good:
- document scan
- field extraction
- source highlighting
- progress
- review state
- success
- guided tour

Bad:
- decorative particles
- constant floating objects
- excessive parallax
- animation everywhere

Respect `prefers-reduced-motion`.

---

# PART 14 — ENTERPRISE UX

Ensure:

- predictable navigation
- consistent terminology
- accessible forms
- keyboard navigation
- visible focus
- meaningful loading states
- useful errors
- useful empty states
- responsive behavior
- scalable component architecture
- maintainable design tokens

---

# PART 15 — IMPLEMENTATION PROCESS

Do NOT immediately rewrite the entire frontend.

Sequence:

1. Audit
2. Sitemap
3. User journeys
4. Design system
5. Wireframes
6. Homepage
7. Onboarding
8. Document workspace
9. Guide
10. API
11. Error/loading/empty states
12. Responsive
13. Accessibility
14. Testing
15. Documentation

If project conventions require approval between planning and implementation,
STOP after the planning phase.

---

# PART 16 — FINAL TEST

Pretend you are a first-time user.

Can you:

1. Understand the product?
2. Know what to click?
3. Upload a document?
4. Understand processing?
5. Understand extraction?
6. Identify uncertain information?
7. Verify a result?
8. Select information?
9. Export/use data?
10. Find the API?
11. Create an API key?
12. Find help?

If any answer is no, improve the UX.

---

# FINAL PRINCIPLE

Do not optimize for visual impressiveness.

Optimize for:

Understanding
↓
Confidence
↓
Action
↓
Verification
↓
Successful outcome

The product should make users feel:

> "I know what is happening, I know what I need to check, and I know what to do next."
