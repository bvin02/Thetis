// Drives the Floor at 1440 px: selection, table view, tooltips, approve/dismiss/undo.
import { chromium } from '@playwright/test'

const out = process.argv[2] ?? '../data/shots'
const browser = await chromium.launch()
const page = await browser.newPage({ viewport: { width: 1440, height: 1740 } })
const logs = []
page.on('console', (m) => { if (['error', 'warning'].includes(m.type())) logs.push(`[${m.type()}] ${m.text()}`) })
page.on('pageerror', (e) => logs.push(`[pageerror] ${e.message}`))
await page.goto('http://localhost:5173/', { waitUntil: 'networkidle' })
await page.screenshot({ path: `${out}/floor-t03.png` })

await page.getByRole('button', { name: /^T-04, At risk/ }).first().click()
await page.waitForTimeout(400)
await page.screenshot({ path: `${out}/floor-t04.png` })

await page.getByRole('button', { name: 'Table', exact: true }).click()
await page.waitForTimeout(200)
await page.getByRole('button', { name: /^T-02, Watch/ }).first().click()
await page.waitForTimeout(400)
await page.screenshot({ path: `${out}/floor-table.png` })
await page.getByRole('button', { name: 'Plan', exact: true }).click()

await page.locator('.ov.l1').first().hover()
await page.waitForTimeout(300)
await page.screenshot({ path: `${out}/floor-tooltip.png`, clip: { x: 240, y: 380, width: 780, height: 560 } })
await page.mouse.move(5, 5)

await page.getByRole('button', { name: /^T-03, Critical/ }).first().click()
await page.waitForTimeout(400)
const approve = page.getByRole('button', { name: 'Approve isolation' })
await approve.click()
await page.getByText('Isolation approved').waitFor()
await page.getByRole('button', { name: /^Dismiss: Plate/ }).click()
await page.getByText('Dismissed').waitFor()
await page.waitForTimeout(300)
const badgeAfter = await page.locator('[aria-label$="waiting"]').first().innerText()
await page.locator('aside[aria-label="Selected tank"]').screenshot({ path: `${out}/floor-decided.png` })
await page.getByRole('button', { name: /^Undo: Isolate/ }).click()
await page.getByRole('button', { name: 'Approve isolation' }).waitFor()
await page.getByRole('button', { name: /^Undo: Plate/ }).click()
await page.getByRole('button', { name: 'Request sampling' }).waitFor()
await page.waitForTimeout(300)
const badgeEnd = await page.locator('[aria-label$="waiting"]').first().innerText()

await page.goto('http://localhost:5173/?room=B', { waitUntil: 'networkidle' })
await page.waitForTimeout(300)
await page.screenshot({ path: `${out}/floor-room-b.png` })
console.log(JSON.stringify({ badgeAfter, badgeEnd, logs }))
await browser.close()
