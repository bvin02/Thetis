// Screenshots every page at 1440 and 390 px and reports console errors and horizontal overflow.
import { chromium } from '@playwright/test'
const out = process.argv[2] ?? '../data/shots'
const browser = await chromium.launch()
const pages = [
  ['tank', '/tanks/T-03'], ['tank-t04', '/tanks/T-04'], ['tank-empty', '/tanks/T-09'], ['tanks', '/tanks'], ['checks', '/checks'],
  ['decisions', '/decisions'], ['photos', '/photos'], ['notfound', '/nope'], ['advisor', '/advisor'],
]
const results = []
for (const [width, height, suffix] of [[1440, 1000, ''], [390, 844, '-phone']]) {
  const page = await browser.newPage({ viewport: { width, height } })
  // This script never spends credits: the Advisor stays on what's stored
  await page.route('**/api/advisor/analyze', (route) => route.fulfill({ status: 200, contentType: 'text/event-stream', body: '' }))
  const logs = []
  page.on('console', (m) => { if (['error', 'warning'].includes(m.type())) logs.push(`[${m.type()}] ${m.text().slice(0, 300)}`) })
  page.on('pageerror', (e) => logs.push(`[pageerror] ${e.message}`))
  for (const [name, path] of pages) {
    await page.goto(`http://localhost:5173${path}`, { waitUntil: 'networkidle' })
    await page.waitForTimeout(350)
    await page.screenshot({ path: `${out}/page-${name}${suffix}.png`, fullPage: true })
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)
    results.push({ name, width, overflow, logs: logs.splice(0) })
  }
  await page.close()
}
console.log(JSON.stringify(results.filter((r) => r.overflow > 0 || r.logs.length), null, 1))
console.log('checked', results.length)
await browser.close()
