import { chromium } from 'playwright'
const b = await chromium.launch()
const p = await b.newPage({ viewport: { width: 1440, height: 950 } })
const errs = []
p.on('pageerror', e => errs.push(String(e)))

// 1. Skip link is the first stop on the public site.
await p.goto('http://localhost:5173/', { waitUntil: 'networkidle' })
await p.keyboard.press('Tab')
console.log('first tab stop:', (await p.evaluate(() => document.activeElement?.textContent?.trim())))

// 2. Reach the primary CTA by keyboard alone and activate it.
let found = false
for (let i = 0; i < 25 && !found; i++) {
  await p.keyboard.press('Tab')
  found = await p.evaluate(() => document.activeElement?.textContent?.includes('Process your first document') ?? false)
}
console.log('reached hero CTA by Tab:', found)

// 3. Focus must be visible, not suppressed.
const outline = await p.evaluate(() => {
  const el = document.activeElement
  const s = el ? getComputedStyle(el) : null
  return s ? { outline: s.outlineStyle, width: s.outlineWidth, shadow: s.boxShadow !== 'none' } : null
})
console.log('focus indicator:', JSON.stringify(outline))

// 4. Workspace: J/K/E/A shortcuts and tab order.
await p.goto('http://localhost:5173/app/documents/doc_1m4an4f05hm4wn0vd', { waitUntil: 'networkidle' })
await p.waitForTimeout(1500)
await p.keyboard.press('j')
await p.waitForTimeout(250)
const sel = await p.evaluate(() => {
  const rows = [...document.querySelectorAll('[id^="field-"]')]
  return rows.find(r => r.className.includes('surface-selected'))?.id ?? null
})
console.log('J selects a field:', sel)
await p.keyboard.press('e')
await p.waitForTimeout(250)
console.log('E opens the editor:', await p.evaluate(() => document.activeElement?.tagName))
await p.keyboard.press('Escape')

// 5. Tour is reachable and escapable.
await p.goto('http://localhost:5173/app?empty=1', { waitUntil: 'networkidle' })
await p.waitForTimeout(1000)
await p.getByRole('button', { name: /Take a 1-minute tour/i }).click()
await p.waitForTimeout(400)
await p.keyboard.press('ArrowRight'); await p.waitForTimeout(250)
const step = (await p.innerText('[role=dialog]')).split('\n')[0]
await p.keyboard.press('Escape'); await p.waitForTimeout(300)
console.log('tour arrow key:', step, '| Escape closes:', await p.locator('[role=dialog]').count() === 0)
console.log('errors:', errs)
await b.close()
