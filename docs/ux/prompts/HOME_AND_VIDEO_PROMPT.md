# HOMEPAGE + PRODUCT ANIMATION PROMPT

Create a premium Marinnex Lab homepage experience around one central visual:

# Document → Intelligence → Verified Data

The animation should feel like a live miniature product demonstration.

## Animation story

### Scene 1 — Document

A realistic financial document card enters the interface.

Label:

> Financial Document

Show subtle invoice fields.

### Scene 2 — Upload

A cursor/drop interaction places the document into the processing area.

Text:

> Upload your document

### Scene 3 — AI Processing

A restrained scanning line moves through the document.

Status messages:

Reading document...
Identifying financial fields...
Validating extracted values...

Do not use "AI magic".

### Scene 4 — Extraction

Fields appear one by one:

Invoice Number
Vendor
Date
Subtotal
Tax
Total

Each field visually connects back to the source.

### Scene 5 — Confidence

Show:

Total
RM 10,600
96% confidence

Then:

Tax
RM 600
68% confidence
Needs review

This communicates that the AI is useful but not blindly trusted.

### Scene 6 — Human Review

A user cursor selects the uncertain tax field.

The original document highlights the corresponding source.

Text:

> Review what matters.

### Scene 7 — Structured Data

The interface transitions from visual document fields into structured output.

Example:

{
  "invoice_number": "INV-2026-001",
  "vendor": "ABC Sdn Bhd",
  "total": 10600.00
}

### Scene 8 — API

The structured data moves into an API/integration card.

Text:

> Ready to use.

### Final

Marinnex Lab logo

> Turn financial documents into usable data.

CTA:

> Process Your First Document

---

# Animation style

Professional enterprise SaaS.

Motion should be:

- smooth
- purposeful
- subtle
- fast enough to understand
- slow enough to read

Avoid:

- cyberpunk
- neon
- excessive glowing
- spinning AI brains
- robot imagery
- particle backgrounds

Use the Marinnex Lab teal/blue-green brand direction.

---

# Technical implementation

Prefer CSS/Framer Motion/React animation if already available.

If the project uses another animation system, reuse it.

The animation must:

- work on desktop
- degrade gracefully on mobile
- support reduced motion
- avoid excessive CPU usage
- not block page interaction
- pause when not visible if appropriate

Do not create a video file unless there is a clear reason.

For a web homepage, an interactive animation is preferable because it demonstrates
the actual product and remains editable.

A separate 30–45 second marketing video can be created later using the same
storyboard.
