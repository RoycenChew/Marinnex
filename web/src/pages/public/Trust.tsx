import { Link } from 'react-router-dom'
import { AlertTriangle } from 'lucide-react'
import { BRAND, TRUST_FACTS } from '../../lib/copy'

/**
 * C5 — the honest version.
 *
 * The package's trust page advertised encryption, residency and compliance.
 * None of that is true of this system today, and a trust page that overstates
 * is worse than none: it is the one page a reader will hold you to. So this
 * page states what is implemented, says plainly what is not, and marks the two
 * things only the owner can write.
 *
 * Nothing here is a legal document. It is a description of the system.
 */

/** Stated as absences, because a reader assumes these unless told otherwise. */
const NOT_TRUE_YET = [
  'We hold no certifications and claim no compliance standard — not SOC 2, not ISO 27001, nothing.',
  'Your documents are not stored in Malaysia. Hosting there is planned; today they sit on the machine running this software.',
  'We make no claim about encryption at rest. Whether the disk holding your files is encrypted depends on the machine it runs on.',
  'There is no automatic deletion schedule yet. Documents stay until they are deleted.',
  'We publish no accuracy figure. Accuracy depends on your documents, and a number measured on ours would not predict yours.',
]

export default function Trust() {
  return (
    <div className="mx-auto w-full max-w-3xl px-5 py-14">
      <h1 className="font-[family-name:var(--font-display)] text-[clamp(2rem,4vw,3rem)] leading-tight text-[var(--text-primary)]">
        Where your documents go
      </h1>
      <p className="mt-4 text-base leading-relaxed text-[var(--text-secondary)]">
        You are about to send us your suppliers' invoices. Here is everything we
        can tell you about what happens to them, including the parts that are not
        finished.
      </p>

      <section className="mt-10">
        <h2 className="font-[family-name:var(--font-display)] text-2xl text-[var(--text-primary)]">
          What is true today
        </h2>
        <dl className="mt-5 flex flex-col gap-5">
          {TRUST_FACTS.map((fact) => (
            <div key={fact.title}>
              <dt className="text-sm font-semibold text-[var(--text-primary)]">
                {fact.title}
              </dt>
              <dd className="mt-1 text-sm leading-relaxed text-[var(--text-secondary)]">
                {fact.body}
              </dd>
            </div>
          ))}
        </dl>
      </section>

      <section className="mt-10">
        <h2 className="font-[family-name:var(--font-display)] text-2xl text-[var(--text-primary)]">
          What is not true yet
        </h2>
        <ul className="mt-5 flex flex-col gap-3">
          {NOT_TRUE_YET.map((line) => (
            <li
              key={line}
              className="flex gap-2.5 text-sm leading-relaxed text-[var(--text-secondary)]"
            >
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-[var(--color-warning-600)]" />
              {line}
            </li>
          ))}
        </ul>
      </section>

      <section className="mt-10">
        <h2 className="font-[family-name:var(--font-display)] text-2xl text-[var(--text-primary)]">
          What we never record
        </h2>
        <p className="mt-3 text-sm leading-relaxed text-[var(--text-secondary)]">
          Our logs carry identifiers and error codes only. Document text,
          extracted values, page images, the prompts we send the AI provider and
          the responses it returns are never written to a log. API keys are
          stored only as a hash, so a key that is lost cannot be recovered from
          us — only replaced.
        </p>
      </section>

      {/* Marked, not filled in: a privacy policy is the owner's to write, and a
          placeholder dressed up as one would be the worst thing on this page. */}
      <section className="mt-10 rounded-[var(--radius-lg)] border border-dashed p-5">
        <h2 className="text-sm font-semibold text-[var(--text-primary)]">
          Privacy policy and retention
        </h2>
        <p className="mt-2 text-sm leading-relaxed text-[var(--text-secondary)]">
          <span className="font-medium text-[var(--text-primary)]">
            TODO: owner to confirm.
          </span>{' '}
          A privacy notice naming the processor and the processing location, and
          a stated retention period, are required before {BRAND.name} is opened
          to the public. Neither is published yet, and this page will link to
          both when they are.
        </p>
      </section>

      <p className="mt-10 text-sm text-[var(--text-secondary)]">
        <Link to="/" className="text-[var(--text-brand)] hover:underline">
          Back to the homepage
        </Link>
      </p>
    </div>
  )
}
