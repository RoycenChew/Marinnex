# Marinnex Lab Product UX Blueprint

## 1. Product positioning

**Turn financial documents into usable data.**

The product should communicate that it helps people move from unstructured
financial documents to verified structured information.

### Core promise

> Upload your financial document. Let AI extract the information. Review what matters. Use the data anywhere.

---

## 2. Product personality

### Human
The user should feel guided rather than tested.

### Enterprise-ready
The product should look reliable, controlled and professional.

### Intelligent
AI should be visible through useful behavior, not decorative "AI" effects.

### Transparent
Show where extracted information came from and which fields deserve review.

### Calm
Financial software should not feel noisy or futuristic for the sake of looking futuristic.

---

## 3. Main information architecture

### Public

- Home
- How It Works
- Use Cases
- Guide
- API
- About / Trust

### Application

- Dashboard
- Documents
- Document Workspace
- API Keys
- API Documentation
- Guide / Help
- Account

---

## 4. Homepage journey

### Hero

Headline:

> Turn Financial Documents Into Usable Data.

Supporting copy:

> Upload invoices, receipts, statements and supported financial documents. Let AI extract the information, review what matters, and turn the result into structured data.

Primary CTA:

> Process Your First Document

Secondary CTA:

> See How It Works

### Hero visual

Do not use a generic AI illustration.

Use an interactive document-to-data animation:

Document
→ scanning
→ extracted fields
→ confidence
→ human review
→ structured output
→ API

---

## 5. Home sections

1. Hero
2. The manual-work problem
3. Interactive "How it works"
4. Product preview
5. Human review / confidence
6. Supported use cases
7. API / integration
8. Trust and security
9. First-time-user guide
10. Final CTA
11. Footer

---

## 6. First-time-user journey

First visit:

> Welcome to Marinnex Lab.

Explain in one screen:

1. Upload a document
2. AI extracts information
3. Review the result
4. Use or export the data

Offer:

- Start with a document
- Take a 1-minute tour

Never force the tour repeatedly.

---

## 7. Document workspace

Desktop layout:

```text
--------------------------------------------------------------
Header
--------------------------------------------------------------
Breadcrumb / document name

┌──────────────────────────┬─────────────────────────────────┐
│                          │ Extracted Information            │
│     DOCUMENT PREVIEW     │                                 │
│                          │ Invoice Number    INV-001   ✓   │
│                          │ Vendor             ABC       ✓   │
│                          │ Date               06/10/26  ✓   │
│                          │ Tax                RM600     ⚠   │
│                          │ Total              RM10600   ✓   │
│                          │                                 │
│                          │ [Review] [Export] [Use Data]    │
└──────────────────────────┴─────────────────────────────────┘
```

Clicking a field should highlight its source location if the backend/document
viewer supports coordinates.

---

## 8. Confidence UX

Never hide uncertainty.

Example:

**Total**
RM 10,600
96% confidence

**Tax**
RM 600
68% confidence
Needs review

Confidence should never rely only on color.

---

## 9. Human review philosophy

Do not tell users:

> Trust our AI.

Tell users:

> Here is what the AI found. Here is where it came from. Here is how confident it is. You remain in control.

---

## 10. API experience

API should feel like a product feature, not a developer afterthought.

Journey:

API
→ What can I do?
→ Create API key
→ Copy key
→ Make first request
→ Read response
→ Integration guide

Only show capabilities actually supported by the backend.

---

## 11. Enterprise-ready characteristics

The UI should communicate:

- predictable navigation
- role clarity
- auditability where supported
- controlled actions
- transparent processing states
- safe error handling
- accessibility
- responsive behavior
- clear documentation
- consistent terminology
- no exaggerated AI claims

Never invent compliance certifications, encryption claims,
retention policies or accuracy percentages.

---

## 12. Visual direction

Use the supplied Marinnex Lab logo as the brand anchor.

Preferred visual language:

- deep teal / blue-green
- white
- neutral surfaces
- dark readable typography
- restrained accent colors
- subtle borders
- generous spacing
- strong hierarchy

Avoid:

- excessive purple AI gradients
- cyberpunk visuals
- excessive glassmorphism
- glowing particles
- decorative AI sparkles
- random floating cards
- unnecessary animations

---

## 13. Design principle

The workflow is the design.

The interface should make these questions easy to answer:

1. What is this?
2. What do I upload?
3. What is the AI doing?
4. What did it find?
5. Is the result reliable?
6. What needs my attention?
7. What can I do with the result?
8. How can my system use it?
