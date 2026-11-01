// Runs the SPEC §1 demo steps in a real browser. Needs a demo seed: npm run seed
import { chromium } from '@playwright/test'
import path from 'node:path'

const out = process.argv[2] ?? '../data/shots'
const browser = await chromium.launch()
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } })
const logs = []
page.on('console', (m) => { if (['error', 'warning'].includes(m.type())) logs.push(`[${m.type()}] ${m.text()}`) })
page.on('pageerror', (e) => logs.push(`[pageerror] ${e.message}`))
const started = Date.now()
const step = (name) => console.log(`${((Date.now() - started) / 1000).toFixed(1)}s  ${name}`)

await page.goto('http://localhost:5173/', { waitUntil: 'networkidle' })
step(await page.locator('h1').innerText())
await page.screenshot({ path: `${out}/demo-1-floor.png`, fullPage: true })

await page.getByRole('button', { name: /^T-03, Watch/ }).first().click()
await page.waitForTimeout(200)
await page.getByRole('link', { name: 'New check' }).click()
await page.waitForURL(/checks\/new\?tank=T-03/)
await page.screenshot({ path: `${out}/demo-2-empty.png` })
const selected = await page.locator('#tank').inputValue()
step(`tank prefilled: ${selected}`)

const t0 = Date.now()
const repo = path.resolve(process.cwd(), '..')
await page.locator('input[type=file]').first().setInputFiles(path.join(repo, 'fixtures/demo/t03-today.jpg'))
await page.getByText('Synthetic sample').waitFor()
await page.locator('svg[role=application] polygon').first().waitFor()
step(`analysed and outlined in ${Date.now() - t0} ms`)
await page.waitForTimeout(400)
await page.screenshot({ path: `${out}/demo-3-review.png`, fullPage: true })
const before = await page.getByRole('region', { name: 'Counts' }).innerText().catch(() => '')
const counts0 = await page.locator('aside[aria-label="Check details"] section[aria-label="Counts"]').innerText()
step(`counts: ${counts0.replace(/\n/g, ' ')}`)

// Fix one wrong call by clicking its outline and pressing 3
const poly = page.locator('svg[role=application] polygon[stroke="#2E8B57"]').nth(4)
await poly.click({ force: true })
await page.getByRole('dialog').waitFor()
await page.waitForTimeout(150)
await page.screenshot({ path: `${out}/demo-4-popover.png` })
await page.keyboard.press('3')
await page.waitForTimeout(350)
const counts1 = await page.locator('aside[aria-label="Check details"] section[aria-label="Counts"]').innerText()
step(`after correction: ${counts1.replace(/\n/g, ' ')}`)
await page.keyboard.press('1') // put it back
await page.keyboard.press('Escape')

// Review steps through the unsure ones
const review = page.getByRole('button', { name: 'Review', exact: true })
if (await review.count()) {
  await review.click()
  await page.waitForTimeout(350)
  await page.screenshot({ path: `${out}/demo-5-review-step.png` })
  await page.keyboard.press('Tab')
  await page.waitForTimeout(200)
  await page.keyboard.press('Escape')
  await page.getByRole('button', { name: 'Fit' }).click()
}

// Add larva mode
await page.getByRole('button', { name: 'Add larva' }).click()
const box = await page.locator('svg[role=application]').boundingBox()
await page.mouse.click(box.x + 12, box.y + 12)
await page.waitForTimeout(200)
const dialog = await page.getByRole('dialog').innerText()
step(`manual larva popover: ${dialog.replace(/\n/g, ' ').slice(0, 60)}`)
await page.getByRole('button', { name: 'Delete' }).click()

// Copy the line's last water readings
await page.getByRole('button', { name: 'Use these' }).click()
const omega = await page.locator('#w-omega').inputValue()
step(`water copied, omega=${omega}`)
await page.locator('aside[aria-label="Check details"]').screenshot({ path: `${out}/demo-6-panel.png` })

await page.getByRole('button', { name: 'Save check' }).click()
await page.waitForURL(/\?tank=T-03/)
await page.getByText('Check saved.').waitFor()
step(await page.getByRole('status').filter({ hasText: 'Check saved' }).innerText())
await page.waitForTimeout(500)
step(await page.locator('h1').innerText())
step(await page.locator('section[aria-label="Summary"] p').innerText())
await page.screenshot({ path: `${out}/demo-7-after-save.png`, fullPage: true })

await page.getByRole('button', { name: 'Approve isolation' }).click()
await page.getByText('Isolation approved').waitFor()
step('isolation approved')
await page.getByRole('button', { name: /^Undo: Isolate/ }).click()
await page.getByRole('button', { name: 'Approve isolation' }).waitFor()

await page.getByRole('link', { name: 'Review outlines' }).click()
await page.waitForURL(/checks\/\d+/)
await page.getByRole('button', { name: 'Edit outlines' }).waitFor()
await page.waitForTimeout(400)
await page.screenshot({ path: `${out}/demo-8-check-detail.png`, fullPage: true })
step('check detail open')
console.log(JSON.stringify({ logs, before: before.length }))
await browser.close()
