import { chromium } from 'playwright'
import AxeBuilder from '@axe-core/playwright'

const PAGES = [
  ['home', '/'],
  ['guide', '/guide'],
  ['trust', '/trust'],
  ['documents', '/app'],
  ['workspace', '/app/documents/doc_1m4an4f05hm4wn0vd'],
  ['keys', '/app/api-keys'],
]
const b = await chromium.launch()
let fails = 0
for (const scheme of ['light', 'dark']) {
  const ctx = await b.newContext({ viewport: { width: 1440, height: 950 }, colorScheme: scheme })
  const p = await ctx.newPage()
  for (const [name, path] of PAGES) {
    await p.goto('http://localhost:5173' + path, { waitUntil: 'networkidle' })
    await p.waitForTimeout(1200)
    const r = await new AxeBuilder({ page: p })
      .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])
      .analyze()
    const serious = r.violations.filter(v => v.impact === 'serious' || v.impact === 'critical')
    if (serious.length) {
      fails += serious.length
      console.log(`${scheme}/${name}:`)
      for (const v of serious) console.log(`   [${v.impact}] ${v.id} x${v.nodes.length} — ${v.nodes[0].target}`)
    }
  }
  await ctx.close()
}
console.log(fails === 0 ? 'no serious or critical violations' : `${fails} serious/critical`)
await b.close()
