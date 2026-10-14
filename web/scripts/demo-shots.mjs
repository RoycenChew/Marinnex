/**
 * Screenshots of the portal, for `docs/demo/`.
 *
 * Credentials come from the environment and are never written anywhere:
 *
 *   PORTAL_EMAIL=... PORTAL_PASSWORD=... node scripts/demo-shots.mjs
 *
 * BASE defaults to the live portal. Point it at http://localhost:5173 to shoot
 * a local run instead.
 *
 * The signed-in pages are only captured when credentials are supplied, and the
 * script refuses to write a screenshot of a page it could not reach — an image
 * of a redirect back to the login screen, filed under the name of the page it
 * was meant to show, is worse than a missing file.
 */
import { chromium } from 'playwright'
import { mkdir } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'

const BASE = process.env.BASE ?? 'https://marinnex.duckdns.org'
const OUT = new URL('../../docs/demo/', import.meta.url)
const EMAIL = process.env.PORTAL_EMAIL
const PASSWORD = process.env.PORTAL_PASSWORD

/** [file, path] */
const PUBLIC_PAGES = [
  ['01-landing', '/'],
  ['02-guide', '/guide'],
  ['03-trust', '/trust'],
  ['04-sign-in', '/login'],
  ['05-invite-only', '/register'],
]

const SIGNED_IN_PAGES = [
  ['06-documents', '/app'],
  ['07-schemas', '/app/schemas'],
  ['08-api-keys', '/app/api-keys'],
  ['09-usage', '/app/usage'],
  ['10-account', '/app/profile'],
]

/**
 * The same screens with data in them, shot against a local mock-mode run.
 *
 * The live portal's account is empty — nobody has uploaded to it — so a
 * screenshot of it shows an empty state and not the product. These use the
 * fixtures in `samples/examples.json`, which are synthetic and already in the
 * repository, so no real document is involved either way.
 */
const PRODUCT_PAGES = [
  ['20-documents', '/app'],
  ['22-schemas', '/app/schemas'],
  ['23-api-keys', '/app/api-keys'],
  ['24-usage', '/app/usage'],
  ['25-account', '/app/profile'],
]

const DESKTOP = { width: 1440, height: 900 }
const MOBILE = { width: 390, height: 844 }

// `public` shoots the live portal; `product` shoots a local mock-mode run.
const SET = process.env.SET ?? 'public'

await mkdir(OUT, { recursive: true })
const browser = await chromium.launch()
const written = []
const skipped = []

async function settle(page) {
  // networkidle alone fires before TanStack Query has painted the result, and
  // before the fonts land — both of which show up as a half-drawn screenshot.
  await page.waitForLoadState('networkidle').catch(() => {})
  await page.evaluate(() => document.fonts.ready).catch(() => {})
  await page.waitForTimeout(900)
}

async function shoot(page, file, { full = true } = {}) {
  const path = fileURLToPath(new URL(file + '.png', OUT))
  await page.screenshot({ path, fullPage: full, animations: 'disabled' })
  written.push(file + '.png')
}

async function capture(context, pages, { suffix = '', full = true } = {}) {
  const page = await context.newPage()
  for (const [file, route] of pages) {
    const response = await page.goto(BASE + route, { waitUntil: 'domcontentloaded' })
    await settle(page)
    const landed = new URL(page.url()).pathname
    const wanted = route === '/' ? '/' : route
    // A protected page bounces to /login. Record that rather than filing the
    // login screen under the wrong name.
    if (wanted !== '/' && landed !== wanted) {
      skipped.push(`${file}: ${route} redirected to ${landed}`)
      continue
    }
    if (response && response.status() >= 400) {
      skipped.push(`${file}: ${route} returned ${response.status()}`)
      continue
    }
    await shoot(page, file + suffix, { full })
  }
  await page.close()
}

/** Sign in through the form, leaving the session cookie on the context. */
async function signIn(context, email, password) {
  const page = await context.newPage()
  await page.goto(BASE + '/login', { waitUntil: 'domcontentloaded' })
  await settle(page)
  await page.locator('input[type="email"]').fill(email)
  await page.locator('input[autocomplete="current-password"]').fill(password)
  await page.locator('button[type="submit"]').click()
  await page.waitForURL(/\/app/, { timeout: 30_000 })
  await settle(page)
  await page.close()
}

/**
 * The review screen, reached by opening the first document in the list.
 *
 * Navigated to rather than addressed by id: the fixture ids in
 * `samples/examples.json` are regenerated whenever the captures are re-run, so
 * a hard-coded one goes stale silently and shoots a "not found" page.
 */
async function reviewScreen(context, suffix) {
  const page = await context.newPage()
  await page.goto(BASE + '/app', { waitUntil: 'domcontentloaded' })
  await settle(page)
  const first = page.locator('a[href*="/app/documents/"]').first()
  if ((await first.count()) === 0) {
    skipped.push(`21-review-evidence${suffix}: no document in the list to open`)
    await page.close()
    return
  }
  await first.click()
  await page.waitForURL(/\/app\/documents\//, { timeout: 30_000 })
  await settle(page)
  if (await page.getByText('Not found, or not in this project').count()) {
    skipped.push(`21-review-evidence${suffix}: the document did not load`)
    await page.close()
    return
  }
  await shoot(page, '21-review-evidence' + suffix)
  await page.close()
}

// --- product screens, against a local mock-mode run -------------------------
if (SET === 'product') {
  const context = await browser.newContext({ viewport: DESKTOP, colorScheme: 'light' })
  // Mock mode accepts the seeded development account; MSW answers the rest.
  await signIn(context, 'dev@fdip.local', 'devpass')
  await capture(context, PRODUCT_PAGES)
  await reviewScreen(context, '')
  await context.close()
  await browser.close()
  const out = [`base: ${BASE}`, `written: ${written.length}`, ...written.map((f) => `  ${f}`),
    ...(skipped.length ? ['skipped:', ...skipped.map((s) => `  ${s}`)] : [])].join('\n')
  console.log(out)
  process.exit(skipped.length ? 1 : 0)
}

// --- public pages -----------------------------------------------------------
// Light only. The app has a dark theme and it works, but a demo folder with
// each screen twice makes the reader choose between two of the same thing
// instead of looking at the product.
{
  const context = await browser.newContext({ viewport: DESKTOP, colorScheme: 'light' })
  await capture(context, PUBLIC_PAGES)
  await context.close()
}

// --- the landing page on a phone -------------------------------------------
{
  const context = await browser.newContext({
    viewport: MOBILE,
    colorScheme: 'light',
    isMobile: true,
    hasTouch: true,
    deviceScaleFactor: 2,
  })
  await capture(context, [['01-landing-mobile', '/']])
  await context.close()
}

// --- signed in --------------------------------------------------------------
if (EMAIL && PASSWORD) {
  const context = await browser.newContext({ viewport: DESKTOP, colorScheme: 'light' })
  const page = await context.newPage()
  await page.goto(BASE + '/login', { waitUntil: 'domcontentloaded' })
  await settle(page)
  await page.locator('input[type="email"]').fill(EMAIL)
  await page.locator('input[autocomplete="current-password"]').fill(PASSWORD)
  await page.locator('button[type="submit"]').click()
  await page.waitForURL(/\/app/, { timeout: 30_000 })
  await settle(page)
  await page.close()

  // The session cookie is on the context, so the pages reuse it.
  await capture(context, SIGNED_IN_PAGES)
  await context.close()
} else {
  skipped.push('signed-in pages: PORTAL_EMAIL and PORTAL_PASSWORD were not set')
}

await browser.close()

const report = [
  `base: ${BASE}`,
  `written: ${written.length}`,
  ...written.map((f) => `  ${f}`),
  ...(skipped.length ? ['skipped:', ...skipped.map((s) => `  ${s}`)] : []),
].join('\n')
console.log(report)
