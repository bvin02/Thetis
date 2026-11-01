// The one live Claude call the build was allowed: Ask Claude on t03-today.jpg, through the app.
// Do not run this again without a reason; a repeat with the same crops is answered from the cache.
import { chromium } from '@playwright/test'
const out = process.argv[2] ?? '../data/shots'
const browser = await chromium.launch()
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } })
const logs = []
page.on('console', (m) => { if (['error', 'warning'].includes(m.type())) logs.push(`[${m.type()}] ${m.text()}`) })
page.on('pageerror', (e) => logs.push(`[pageerror] ${e.message}`))
await page.goto('http://localhost:5173/checks/new?tank=T-03', { waitUntil: 'networkidle' })
await page.getByRole('button', { name: 'Use a sample slide' }).click()
await page.getByRole('menuitem', { name: /T-03 today/ }).click()
await page.locator('svg[role=application] polygon').first().waitFor()
await page.getByRole('button', { name: 'Ask Claude' }).waitFor()
console.log(await page.getByText(/Sends \d+ small/).innerText())
await page.screenshot({ path: `${out}/claude-before.png` })
const t0 = Date.now()
await page.getByRole('button', { name: 'Ask Claude' }).click()
await page.getByText("Claude's second opinion").or(page.getByRole('alert')).first().waitFor({ timeout: 120000 })
console.log(`answered in ${Date.now() - t0} ms`)
await page.waitForTimeout(300)
await page.screenshot({ path: `${out}/claude-after.png`, fullPage: true })
const list = await page.locator('aside[aria-label="Check details"] section[aria-label="Counts"]').innerText()
console.log(list)
console.log(JSON.stringify(logs))
await browser.close()
