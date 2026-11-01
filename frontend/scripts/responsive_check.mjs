// Responsive pass at 900 and 390 px: layouts, the phone menu, and the full-screen tank sheet.
import { chromium } from '@playwright/test'
const out = process.argv[2] ?? '../data/shots'
const browser = await chromium.launch()
const report = []
const paths = ['/', '/advisor', '/tanks', '/tanks/T-03', '/checks', '/checks/new?tank=T-03', '/decisions', '/photos']
for (const [width, height] of [[900, 800], [899, 800], [660, 800], [390, 844], [320, 640]]) {
  const page = await browser.newPage({ viewport: { width, height } })
  await page.route('**/api/advisor/analyze', (route) => route.fulfill({ status: 200, contentType: 'text/event-stream', body: '' }))
  const logs = []
  page.on('console', (m) => { if (['error', 'warning'].includes(m.type())) logs.push(m.text().slice(0, 200)) })
  page.on('pageerror', (e) => logs.push(e.message))
  for (const path of paths) {
    await page.goto(`http://localhost:5173${path}`, { waitUntil: 'networkidle' })
    await page.waitForTimeout(200)
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)
    if (overflow > 0) report.push(`${width}px ${path}: overflows by ${overflow}px`)
  }
  if (logs.length) report.push(`${width}px console: ${logs.join(' | ')}`)
  await page.close()
}
console.log(report.length ? report.join('\n') : 'No horizontal overflow or console problems at 900, 899, 660, 390 and 320 px')

const page = await browser.newPage({ viewport: { width: 900, height: 900 } })
await page.goto('http://localhost:5173/', { waitUntil: 'networkidle' })
await page.waitForTimeout(300)
await page.screenshot({ path: `${out}/r-900-floor.png` })
await page.goto('http://localhost:5173/checks/new?tank=T-03', { waitUntil: 'networkidle' })
await page.getByRole('button', { name: 'Use a sample slide' }).click()
await page.getByRole('menuitem', { name: /T-03 today/ }).click()
await page.locator('svg[role=application] polygon').first().waitFor()
await page.waitForTimeout(300)
await page.screenshot({ path: `${out}/r-900-newcheck.png` })
await page.close()

const phone = await browser.newPage({ viewport: { width: 390, height: 844 }, hasTouch: true })
await phone.goto('http://localhost:5173/', { waitUntil: 'networkidle' })
await phone.getByRole('button', { name: 'Open menu' }).click()
await phone.waitForTimeout(200)
await phone.screenshot({ path: `${out}/r-phone-menu.png` })
await phone.getByRole('link', { name: 'Decisions' }).click()
await phone.waitForURL(/decisions/)
console.log('menu closes after navigating:', (await phone.getByRole('button', { name: 'Open menu' }).count()) === 1)
await phone.goto('http://localhost:5173/', { waitUntil: 'networkidle' })
await phone.locator('.planlist button').nth(3).click()
await phone.waitForTimeout(400)
await phone.screenshot({ path: `${out}/r-phone-sheet.png` })
console.log('sheet is a dialog:', (await phone.getByRole('dialog').count()) === 1, '| body scroll locked:', await phone.evaluate(() => document.body.style.overflow))
await phone.keyboard.press('Escape')
await phone.waitForTimeout(150)
console.log('Esc closes the sheet:', (await phone.getByRole('dialog').count()) === 0)
const small = await phone.evaluate(() => [...document.querySelectorAll('.solid,.ghost,.chip,.planlist button')].filter((e) => e.getBoundingClientRect().height > 0 && e.getBoundingClientRect().height < 44).map((e) => `${e.textContent.trim().slice(0, 24)}=${Math.round(e.getBoundingClientRect().height)}`))
console.log('targets under 44 px on the Floor:', JSON.stringify(small))
await phone.goto('http://localhost:5173/checks/21', { waitUntil: 'networkidle' })
await phone.waitForTimeout(300)
await phone.screenshot({ path: `${out}/r-phone-check.png` })
await browser.close()
