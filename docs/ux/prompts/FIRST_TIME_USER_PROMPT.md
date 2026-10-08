# FIRST-TIME USER UX PROMPT

Design Marinnex Lab for someone who has never used the product.

The user may be:

- a business owner
- accountant
- finance staff
- operations staff
- developer

Assume they do NOT understand:
- OCR
- document parsing
- extraction pipelines
- confidence scores
- schemas
- APIs

## First screen

Show:

# Welcome to Marinnex Lab

> Let's turn your financial document into usable information.

Then:

1. Upload a document
2. AI extracts information
3. Review the result
4. Use your data

CTA:

> Upload My First Document

Secondary:

> Take a 1-minute Tour

## Contextual help

Use small explanations near technical concepts.

Confidence:

> How certain the AI is about this value.

API Key:

> A secure credential your application uses to connect to Marinnex Lab.

Structured Data:

> Information extracted from your document in a format software can use.

## Empty state

Never show a blank dashboard.

Show:

> Your documents will appear here.

> Upload your first financial document to get started.

CTA:

> Upload Document

## Error state

Avoid:

HTTP 500
PROCESSING_EXCEPTION

Use:

> We couldn't process this document.

> The file may be unclear, corrupted, or unsupported.

Actions:

Try Again
Upload Another Document
View Supported Formats
Contact Support

## Loading state

Avoid:

Loading...

Use:

Reading your document...
Finding financial information...
Checking extracted values...
Preparing your results...

## Human tone

Replace technical phrases:

"Initiate document processing."
→ "Process document"

"Extraction completed successfully."
→ "Your document is ready to review."

"Invalid input."
→ "We couldn't read this document. Try uploading a clearer file."

"Generate API credentials."
→ "Create an API key"
