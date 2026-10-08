import { chromium } from 'playwright'
const PAGES = [['home','/'],['guide','/guide'],['trust','/trust'],['documents','/app'],
  ['workspace','/app/documents/doc_1m4an4f05hm4wn0vd'],['keys','/app/api-keys'],
  ['schemas','/app/schemas'],['usage','/app/usage']]
const WIDTHS = [1440, 1280, 1024, 768, 390]
const b = await chromium.launch(); const bad = []; const errs = []
for (const w of WIDTHS) {
  for (const scheme of ['light','dark']) {
    const ctx = await b.newContext({ viewport: { width: w, height: 900 }, colorScheme: scheme })
    const p = await ctx.newPage()
    p.on('pageerror', e => errs.push(`${w}/${scheme}: ${e}`))
    for (const [name, path] of PAGES) {
      await p.goto('http://localhost:5173' + path, { waitUntil: 'networkidle' })
      await p.waitForTimeout(900)
      const over = await p.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1)
      if (over) bad.push(`${name} @${w} ${scheme}`)
      if (w === 1440 || w === 390) {
        await p.screenshot({ path: `audit/after/${name}-${w}-${scheme}.png`, fullPage: w === 1440 && path.startsWith('/app') === false })
      }
    }
    await ctx.close()
  }
}
console.log('horizontal overflow:', bad.length ? bad : 'none')
console.log('page errors:', errs.length ? errs.slice(0,5) : 'none')
await b.close()
