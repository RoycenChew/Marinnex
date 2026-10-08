import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Copy } from 'lucide-react'
import { VerificationBadge } from '../../components/ui/VerificationBadge'
import { BRAND, GLOSSARY, VERIFICATION } from '../../lib/copy'
import type { VerificationKey } from '../../lib/copy'

/**
 * The guide, from Part 9 of the package.
 *
 * Written for the person the first-time-user prompt describes: someone who has
 * never heard of OCR, parsing or a schema. Every statement here is something
 * this backend does today — the endpoints, the statuses and the error codes are
 * the real ones, and where something is not built the guide says so rather than
 * leaving a reader to find out.
 *
 * It is a public page, so it fetches nothing.
 */

type Section = { id: string; title: string; body: React.ReactNode }

const SNIPPET = `curl -X POST "https://your-host/v1/extract?wait=30" \\
  -H "Authorization: Bearer fdip_test_YOUR_KEY" \\
  -F "file=@invoice.pdf" \\
  -F "schema_id=invoice" \\
  -F "schema_version=1"`

const RESPONSE = `{
  "extraction_id": "ext_8f2",
  "status": "needs_review",
  "document_type": "invoice",
  "schema": { "id": "invoice", "version": 1 },
  "data": {
    "invoice_number": "INV-2026-0417",
    "total": "2142.72",
    "currency": "MYR"
  },
  "fields": {
    "total": {
      "status": "accepted",
      "match": "normalized",
      "evidence": [{ "page": 1, "bbox": [404, 277, 470, 288] }]
    }
  }
}`

const ERRORS: [string, string][] = [
  ['unsupported_file_type', 'The file is not a PDF or an image we can read.'],
  ['encrypted_pdf', 'The PDF is password-protected. Remove the password and send it again.'],
  ['page_limit_exceeded', 'The document has more pages than the limit allows.'],
  ['schema_version_not_allowed', 'This key is not permitted to use that schema version, or the version has not passed its test run.'],
  ['quota_exceeded', 'The key has used its monthly page allowance.'],
  ['idempotency_conflict', 'The same Idempotency-Key was reused with a different file.'],
]

export default function Guide() {
  return (
    <div className="mx-auto w-full max-w-6xl px-5 py-14">
      <header className="mb-10 max-w-[60ch]">
        <h1 className="font-[family-name:var(--font-display)] text-[clamp(2rem,4vw,3rem)] leading-tight text-[var(--text-primary)]">
          Guide
        </h1>
        <p className="mt-3 text-base leading-relaxed text-[var(--text-secondary)]">
          How {BRAND.name} works, what the results mean, and how to call it from
          your own system. No jargon, and nothing described here that is not
          built.
        </p>
      </header>

      <div className="grid gap-10 lg:grid-cols-[minmax(0,200px)_minmax(0,1fr)]">
        <nav aria-label="On this page" className="lg:sticky lg:top-20 lg:self-start">
          <ul className="flex flex-col gap-0.5">
            {CHAPTERS.flatMap((chapter) => [
              <li
                key={chapter.title}
                className="mt-3 px-2 py-1 text-xs font-medium text-[var(--text-tertiary)] first:mt-0"
              >
                {chapter.title}
              </li>,
              ...chapter.sections.map((section) => (
                <li key={section.id}>
                  <a
                    href={`#${section.id}`}
                    className="block rounded-[var(--radius-sm)] px-2 py-1 text-sm text-[var(--text-secondary)] hover:bg-[var(--surface-hover)] hover:text-[var(--text-primary)]"
                  >
                    {section.title}
                  </a>
                </li>
              )),
            ])}
          </ul>
        </nav>

        <div className="min-w-0">
          {CHAPTERS.map((chapter) => (
            <section key={chapter.title} className="mb-10 last:mb-0">
              <h2 className="font-[family-name:var(--font-display)] text-2xl text-[var(--text-primary)]">
                {chapter.title}
              </h2>
              <div className="mt-5 flex flex-col gap-7">
                {chapter.sections.map((section) => (
                  <article key={section.id} id={section.id} className="scroll-mt-20">
                    <h3 className="text-sm font-semibold text-[var(--text-primary)]">
                      {section.title}
                    </h3>
                    <div className="mt-1.5 flex max-w-[68ch] flex-col gap-2.5 text-sm leading-relaxed text-[var(--text-secondary)]">
                      {section.body}
                    </div>
                  </article>
                ))}
              </div>
            </section>
          ))}
        </div>
      </div>
    </div>
  )
}

function Code({ children, label }: { children: string; label: string }) {
  const [copied, setCopied] = useState(false)
  return (
    <div className="overflow-hidden rounded-[var(--radius-md)] border bg-[var(--surface-sunken)]">
      <div className="flex items-center justify-between border-b px-3 py-1.5">
        <span className="text-xs text-[var(--text-tertiary)]">{label}</span>
        <button
          type="button"
          onClick={() => {
            void navigator.clipboard.writeText(children)
            setCopied(true)
            window.setTimeout(() => setCopied(false), 1600)
          }}
          className="inline-flex items-center gap-1.5 rounded-[var(--radius-xs)] px-1.5 py-1 text-xs text-[var(--text-secondary)] hover:bg-[var(--surface-hover)]"
        >
          <Copy className="h-3 w-3" />
          {copied ? 'Copied' : 'Copy'}
        </button>
      </div>
      <pre className="overflow-x-auto p-3 text-xs leading-relaxed text-[var(--text-secondary)]">
        <code>{children}</code>
      </pre>
    </div>
  )
}

const ALL_STATES: VerificationKey[] = [
  'exact',
  'normalized',
  'derived',
  'fuzzy_ocr',
  'not_found',
  'not_checked',
]

const CHAPTERS: { title: string; sections: Section[] }[] = [
  {
    title: 'Getting started',
    sections: [
      {
        id: 'what-is-it',
        title: `What is ${BRAND.name}?`,
        body: (
          <>
            <p>
              You give it an invoice. It reads the invoice and gives you back the
              information in it — the number, the vendor, the dates, the amounts
              and every line of the table — in a form your software can use.
            </p>
            <p>
              What makes it different is that it shows its working. Every value
              points back at the words on the page it was read from, and anything
              it cannot point at is held for a person instead of being passed on.
            </p>
          </>
        ),
      },
      {
        id: 'first-upload',
        title: 'Uploading your first document',
        body: (
          <>
            <p>
              Sign in, then drop a file onto the Documents screen or choose one.
              A PDF, a scan or a photo from your phone all work, up to 20 MB.
            </p>
            <p>
              Sending the same file twice is recognised as the same document, so
              a retry never costs you a second reading.
            </p>
          </>
        ),
      },
      {
        id: 'results',
        title: 'Understanding your results',
        body: (
          <>
            <p>
              A document ends in one of a few states. <strong>Ready</strong> means
              every required value was found on the page and every check passed.{' '}
              <strong>Needs your review</strong> means something is worth a
              person's eyes — the data is there, with a reason against each field
              that needs one.
            </p>
            <p>
              Scanned documents always end in review. That is routine for any
              scan, not a judgement about your file.
            </p>
            <p>
              A field that is simply not printed on your document comes back{' '}
              <em>absent</em>, shown as "Not on document". It never comes back as
              zero, because zero is a number someone might act on.
            </p>
          </>
        ),
      },
      {
        id: 'reviewing',
        title: 'Reviewing fields',
        body: (
          <>
            <p>
              Open a document and you get the page on one side and what was found
              on the other. Selecting a value highlights the words it came from.
              On a phone these are two tabs, and choosing a value takes you to the
              page.
            </p>
            <p>
              Each value says how it was checked, rather than giving you a score:
            </p>
            <ul className="mt-1 flex flex-col gap-2">
              {ALL_STATES.map((key) => (
                <li key={key} className="flex flex-col gap-1">
                  <VerificationBadge match={key} />
                  <span>{VERIFICATION[key].meaning}</span>
                </li>
              ))}
            </ul>
            <p>
              Correct anything that is wrong and save. A correction never
              overwrites what came before: it creates a new version, and the old
              one stays readable in the history.
            </p>
          </>
        ),
      },
      {
        id: 'selecting',
        title: 'Choosing the information you need',
        body: (
          <>
            <p>
              You rarely want all twenty-five fields. Tick the ones you do and
              save them with a name — that saved list is called a{' '}
              <strong>schema</strong>. {GLOSSARY.schema}
            </p>
            <p>
              Before a key may use a schema version, run it on three to five of
              your own documents. That test is there so you find out what it does
              with your invoices before your systems depend on it.
            </p>
          </>
        ),
      },
      {
        id: 'custom-fields',
        title: 'Fields of your own',
        body: (
          <>
            <p>
              If the template does not read something your invoices carry — a
              site reference, a project code — you can add it. Name it the way
              your system reads it, say in a sentence what it is, and list the
              labels it appears under. "D/O No" and "No. Pesanan" are the same
              field on two suppliers' invoices, and telling us both helps.
            </p>
            <p>
              Up to ten per version. They come back alongside the template
              fields, and they are found on the page in exactly the same way: if
              we cannot point at the words it was read from, the document waits
              for a person rather than passing the value on.
            </p>
            <p>
              What they do <em>not</em> get is the checking the template fields
              have. Nothing confirms a field of yours means what you intended the
              way subtotal and tax are confirmed against the total — there is no
              arithmetic behind it to check. Run a test on a few of your own
              documents, read which of your fields were found, and look at the
              values before you build on them.
            </p>
          </>
        ),
      },
      {
        id: 'output-names',
        title: 'Naming and ordering what you receive',
        body: (
          <>
            <p>
              Each field can be given the name your own system uses, put in the
              order you want, and marked required or optional. Required means a
              document missing it waits for a person.
            </p>
            <p>
              You can also pick how dates and amounts are formatted. That applies
              to your spreadsheet exports and to this screen only — the API
              always sends ISO dates and amounts as plain decimal strings, so
              your code never has to guess which format someone chose.
            </p>
            <p>
              You can change all of this while a version is still a draft. Once
              it has passed a test or a key is using it, changing it would break
              whoever is already relying on those names, so it is saved as a new
              version instead.
            </p>
          </>
        ),
      },
      {
        id: 'exporting',
        title: 'Exporting your data',
        body: (
          <p>
            Select documents and export them as CSV or Excel. One row per
            document, or one row per line item, depending on what you are
            reconciling.
          </p>
        ),
      },
    ],
  },
  {
    title: 'API and integration',
    sections: [
      {
        id: 'api-key',
        title: 'Creating an API key',
        body: (
          <>
            <p>
              {GLOSSARY.apiKey} Create one on the API keys screen. Keys come in
              two kinds: <strong>test</strong> keys never reach the paid AI
              provider, so building against them costs nothing, and{' '}
              <strong>live</strong> keys do real extractions.
            </p>
            <p>
              The key is shown once, when it is created. Only a hash of it is
              stored, so we cannot recover it for you — if it is lost, revoke it
              and make another. Keep it on your server, never in a web page, a
              mobile app or a public repository.
            </p>
          </>
        ),
      },
      {
        id: 'auth',
        title: 'Authentication',
        body: (
          <p>
            Send the key as a bearer token:{' '}
            <code className="rounded bg-[var(--surface-sunken)] px-1 py-0.5 text-xs">
              Authorization: Bearer fdip_live_…
            </code>{' '}
            Each key belongs to one project and sees only that project's
            documents. Keys are rate limited per minute and have a monthly page
            allowance.
          </p>
        ),
      },
      {
        id: 'first-request',
        title: 'Your first request',
        body: (
          <>
            <p>
              Post the file to <code>/v1/extract</code> with the schema you want
              back. Adding <code>?wait=30</code> holds the connection for up to
              thirty seconds and returns the finished result if it is ready;
              otherwise you get an id to poll.
            </p>
            <Code label="curl">{SNIPPET}</Code>
            <p>
              Send an <code>Idempotency-Key</code> header if you retry. The same
              key with the same file returns the original job; with a different
              file it is refused, rather than quietly processing twice.
            </p>
          </>
        ),
      },
      {
        id: 'response',
        title: 'The response',
        body: (
          <>
            <p>
              <code>data</code> holds the values. <code>fields</code> holds, for
              each one, how it was verified and where on the page it was found.
            </p>
            <Code label="200 OK">{RESPONSE}</Code>
            <p>
              <strong>Money is a string</strong>, always, beside an ISO currency
              code — <code>"2142.72"</code>, not <code>2142.72</code>. Parsing it
              into a float is how cents go missing. Dates are ISO strings, and
              because Malaysian invoices are written day-first, the schema's
              locale hint decides how an ambiguous date is read. If there is no
              hint and the date is ambiguous, it goes to review rather than being
              guessed.
            </p>
          </>
        ),
      },
      {
        id: 'errors',
        title: 'When something goes wrong',
        body: (
          <>
            <p>
              Errors are RFC 9457 problem documents with a stable{' '}
              <code>code</code>. Branch on the code, never on the message.
            </p>
            <dl className="mt-1 flex flex-col gap-2">
              {ERRORS.map(([code, meaning]) => (
                <div key={code}>
                  <dt>
                    <code className="rounded bg-[var(--surface-sunken)] px-1 py-0.5 text-xs text-[var(--text-primary)]">
                      {code}
                    </code>
                  </dt>
                  <dd className="mt-0.5">{meaning}</dd>
                </div>
              ))}
            </dl>
            <p>
              A timeout, a 429 or a 5xx is worth retrying with a backoff. A
              corrupt, encrypted or oversized file is not — it will fail the same
              way every time.
            </p>
          </>
        ),
      },
    ],
  },
  {
    title: 'Good to know',
    sections: [
      {
        id: 'supported',
        title: 'What it can read',
        body: (
          <>
            <p>
              Invoices, including credit notes. Digital PDFs with a text layer,
              and scans or photos, which are read with OCR. Malaysian formats are
              first-class: MYR, SST, day-first dates, and labels in English or
              Malay.
            </p>
            <p>
              Bank statements and LHDN e-invoice files are planned and not built.
              Receipts are not supported. If you send something that is not an
              invoice, you are told so — you do not get invoice fields filled in
              from a document that has none.
            </p>
          </>
        ),
      },
      {
        id: 'confidence',
        title: 'Why there is no confidence score',
        body: (
          <>
            <p>
              Because we do not have one that would mean anything. A model can
              report how sure it feels, and that feeling is not calibrated
              against whether the value is right — a confidently wrong number is
              the most expensive thing this product could hand you.
            </p>
            <p>
              So instead of a number you cannot check, you get the evidence: the
              match class above, the words on the page, and deterministic checks
              run in code. Model-reported confidence is recorded, and never used
              to decide anything.
            </p>
            <p>
              On scanned fields you may see a scan-quality band. That measures
              how clearly the scanner read the text. It does not say whether the
              value is correct.
            </p>
          </>
        ),
      },
      {
        id: 'validation',
        title: 'What is checked',
        body: (
          <>
            <p>
              Arithmetic is checked in code, never by the model: subtotal plus
              tax must equal the total, the line amounts must sum to the
              subtotal, and a quantity times a unit price must equal its row
              amount. Tax rates are checked against tax amounts.
            </p>
            <p>
              A document is accepted automatically only if every required field
              was found on the page, every check passed, and nothing was
              truncated. Otherwise it waits for you.
            </p>
          </>
        ),
      },
      {
        id: 'troubleshooting',
        title: 'If something looks wrong',
        body: (
          <>
            <p>
              <strong>A value is wrong.</strong> Select it to see what it was read
              from. If the page says something else, correct it — your correction
              is saved as a new version.
            </p>
            <p>
              <strong>Everything is flagged.</strong> Usually a poor scan. A
              straight, well-lit photo at arm's length, or a 300 DPI scan, reads
              far better than a photograph at an angle.
            </p>
            <p>
              <strong>It says this is not an invoice.</strong> Check you sent the
              right file. Statements and receipts are not supported.
            </p>
            <p>
              <strong>Nothing happens after an upload.</strong> Processing is
              asynchronous; the screen polls and updates itself. A few pages
              normally take under a minute.
            </p>
          </>
        ),
      },
      {
        id: 'best-practices',
        title: 'Getting good results',
        body: (
          <ul className="flex list-disc flex-col gap-1.5 pl-4">
            <li>Send the digital PDF when you have one. A text layer beats a photograph of the same page every time.</li>
            <li>Pin a schema version in your integration, so a change on our side cannot reshape your data.</li>
            <li>Run the schema test on your own documents, not ours.</li>
            <li>Keep money as the string we send you until you put it in a decimal type.</li>
            <li>Build against a test key first. It costs nothing.</li>
          </ul>
        ),
      },
      {
        id: 'help',
        title: 'Getting help',
        body: (
          <p>
            Every error on screen keeps its technical code behind a "Details"
            disclosure — that code is the fastest way to say what happened. For
            how your documents are handled and where they are processed, see{' '}
            <Link to="/trust" className="text-[var(--text-brand)] underline">
              Trust
            </Link>
            .
          </p>
        ),
      },
    ],
  },
]
