import { chromium } from '@playwright/test'
const out = process.argv[2] ?? '../data/shots'
const browser = await chromium.launch()
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })
const logs = []
page.on('console', (m) => { if (['error', 'warning'].includes(m.type())) logs.push(`[${m.type()}] ${m.text().slice(0, 300)}`) })
page.on('pageerror', (e) => logs.push(`[pageerror] ${e.message}`))
await page.goto('http://localhost:5173/tanks/T-04', { waitUntil: 'networkidle' })
const card = page.locator('section[aria-label="Trends"]')
for (const [label, name] of [['Shell length', 'length'], ['Dead & abnormal', 'mortality'], ['Water', 'water']]) {
  await page.getByRole('button', { name: label, exact: true }).click()
  await page.waitForTimeout(250)
  await card.screenshot({ path: `${out}/trend-${name}.png` })
}
// Hover shows the tooltip card
const box = await card.boundingBox()
await page.mouse.move(box.x + box.width * 0.6, box.y + 170)
await page.waitForTimeout(200)
await card.screenshot({ path: `${out}/trend-hover.png` })
await page.mouse.move(5, 5)
// Check row opens the check
await page.locator('section[aria-label="Checks"] tbody tr').first().click()
await page.waitForURL(/checks\/\d+/)
console.log('row opens', page.url())
// Close batch dialog
await page.goto('http://localhost:5173/tanks/T-01', { waitUntil: 'networkidle' })
await page.getByRole('button', { name: 'Close batch' }).click()
await page.waitForTimeout(250)
await page.screenshot({ path: `${out}/dialog-close.png` })
await page.getByRole('button', { name: 'Close batch', exact: true }).last().click()
await page.getByText(/Batch NW-1017 closed/).waitFor()
await page.waitForTimeout(400)
await page.screenshot({ path: `${out}/tank-closed.png` })
await page.getByRole('button', { name: 'Start batch' }).click()
await page.waitForTimeout(200)
await page.locator('#batch-code').fill('NW-2001')
await page.locator('#stocked').fill('15000000')
await page.screenshot({ path: `${out}/dialog-start.png` })
await page.getByRole('button', { name: 'Start batch', exact: true }).last().click()
await page.getByText(/Batch NW-2001 started/).waitFor()
await page.waitForTimeout(400)
await page.screenshot({ path: `${out}/tank-new-batch.png` })
console.log(JSON.stringify(logs))
await browser.close()
