// Runs DEMO.md click by click and checks what it promises. Needs a fresh demo seed: npm run seed
// Ask Claude uses the real endpoint, which must answer from its cache. Explain is mocked: no credits are spent.
import { chromium } from '@playwright/test'

const out = process.argv[2] ?? '../data/shots'
const browser = await chromium.launch()
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })
const logs = []
page.on('console', (m) => { if (['error', 'warning'].includes(m.type())) logs.push(`[${m.type()}] ${m.text().slice(0, 240)}`) })
page.on('pageerror', (e) => logs.push(`[pageerror] ${e.message}`))
await page.route('**/api/claude/explain', (route) => route.fulfill({ json: { text: 'Dead larvae rose to 24% from 9% at the last check while growth nearly stopped. With Ω at 2.9 the water looks fine, so these numbers match a bacterial pattern. The actions keep it from spreading and confirm it with a plate.', cached: false, model: 'mock' } }))
let opinionCached = null
page.on('response', async (res) => { if (res.url().endsWith('/api/claude/second-opinion')) opinionCached = (await res.json()).cached })

const results = []
const ok = (name, pass, detail = '') => { results.push(pass); console.log(`${pass ? 'PASS' : 'FAIL'}  ${name}${detail ? `  (${detail})` : ''}`) }
const started = Date.now()
const text = (loc) => loc.innerText()
const panel = page.locator('aside[aria-label="Check details"]')
const inspector = page.locator('aside[aria-label="Selected tank"]')

// 1. The Floor
await page.goto('http://localhost:5173/', { waitUntil: 'networkidle' })
ok('headline', (await text(page.locator('h1'))) === '2 tanks need attention now')
const para = await text(page.locator('section[aria-label="Summary"] p'))
ok('paragraph', para === 'Line 2 water has been corrosive since yesterday. It now affects T-04 and T-05, and T-06 is on the same line.', para)
const urgency = await text(page.getByRole('region', { name: 'Tanks by urgency' }))
ok('Act now shows T-04 and T-05', /T-04\s+At risk\s+Corrosive water/.test(urgency) && /T-05\s+At risk\s+Corrosive water/.test(urgency))
ok('Example data badge', await page.getByText('Example data').first().isVisible())
await page.locator('.ov.l2').first().hover()
await page.waitForTimeout(250)
await page.screenshot({ path: `${out}/final-1-floor.png` })
await page.mouse.move(5, 5)

// 2. New check for T-03
await page.getByRole('button', { name: /^T-03, Watch/ }).first().click()
await page.waitForTimeout(250)
ok('inspector switched to T-03', (await text(inspector)).startsWith('T-03'))
await page.getByRole('link', { name: 'New check' }).click()
await page.locator('#tank').waitFor()
ok('tank prefilled', (await page.locator('#tank').inputValue()) === 'T-03')
const t0 = Date.now()
await page.getByRole('button', { name: 'Use a sample slide' }).click()
await page.getByRole('menuitem', { name: /T-03 today/ }).click()
await page.locator('svg[role=application] polygon').first().waitFor()
const analyseMs = Date.now() - t0
ok('outlined in under a second', analyseMs < 1000, `${analyseMs} ms`)
ok('Synthetic sample label', await page.getByText('Synthetic sample').isVisible())
await page.waitForTimeout(300)
let counts = await text(panel.locator('section[aria-label="Counts"]'))
ok('counts 43 / 5 / 14', /Live\n43/.test(counts) && /Abnormal\n5/.test(counts) && /Dead\n14/.test(counts), counts.replace(/\n/g, ' ').slice(0, 70))
ok('three unsure marks', (await page.locator('svg[role=application] text').filter({ hasText: '?' }).count()) === 3)
await page.screenshot({ path: `${out}/final-2-review.png` })

// 3. Fix the missed shell, then ask Claude
await page.getByRole('button', { name: 'Add larva' }).click()
const box = await page.locator('svg[role=application]').boundingBox()
await page.mouse.click(box.x + box.width * 0.939, box.y + box.height * 0.377)
await page.getByRole('dialog').waitFor()
await page.waitForTimeout(150)
await page.screenshot({ path: `${out}/final-3-added.png` })
await page.keyboard.press('3')
await page.keyboard.press('Escape')
await page.waitForTimeout(300)
counts = await text(panel.locator('section[aria-label="Counts"]'))
ok('Dead goes to 15, 24%', /Dead\n15\n24% of counted/.test(counts), counts.replace(/\n/g, ' ').slice(0, 70))
ok('crop note', await page.getByText('Sends 3 small crops to Claude.').isVisible())
await page.getByRole('button', { name: 'Ask Claude' }).click()
await page.getByText("Claude's second opinion").waitFor({ timeout: 90000 })
await page.waitForTimeout(200)
ok('answer came from the cache, no credits spent', opinionCached === true, String(opinionCached))
await page.screenshot({ path: `${out}/final-4-claude.png` })
await page.getByRole('button', { name: 'Accept all' }).click()
await page.waitForTimeout(200)
ok('nothing left to check', (await text(panel)).includes('Nothing left to check.'))

// 4. Water and save
await page.getByRole('button', { name: 'Use these' }).click()
ok('water filled', (await page.locator('#w-omega').inputValue()) === '2.9' && (await page.locator('#w-ph').inputValue()) === '7.96')
await page.screenshot({ path: `${out}/final-5-water.png`, fullPage: true })
await page.getByRole('button', { name: 'Save check' }).click()
await page.waitForURL(/\?tank=T-03/)

// 5. Back on the Floor
const toast = page.getByRole('status').filter({ hasText: 'Check saved' })
await toast.waitFor()
ok('toast', (await text(toast)).includes('Check saved. T-03 is now Critical. 3 decisions waiting.'))
await page.getByRole('heading', { name: '3 tanks need attention now' }).waitFor()
ok('headline after save', true)
const para2 = await text(page.locator('section[aria-label="Summary"] p'))
ok('paragraph after save', para2.endsWith('Separately, T-03 shows a pattern that matches a bacterial outbreak.'))
await page.getByText('Pattern matches a bacterial outbreak').waitFor()
const insp = await text(inspector)
ok('inspector: pattern and rules-based', insp.includes('Pattern matches a bacterial outbreak') && insp.includes('Rules-based'))
ok('inspector: dead 24% up from 9%', /Dead larvae\n24%\n9% at last check/.test(insp))
ok('inspector: water fine', /Ω aragonite\n2\.9\ntarget ≥ 2/.test(insp))
ok('inspector: 15 dead on the photo', insp.includes('15 dead'))
ok('three actions', insp.includes('3 to decide'))
await page.screenshot({ path: `${out}/final-6-saved.png`, fullPage: true })
await page.getByRole('button', { name: 'Approve isolation' }).click()
await page.getByText('Isolation approved').waitFor()
ok('isolation approved', true)
await inspector.screenshot({ path: `${out}/final-7-approved.png` })

// 6. The tank page
await page.getByRole('link', { name: 'Open T-03' }).click()
await page.waitForURL(/tanks\/T-03/)
await page.locator('section[aria-label="Trends"]').waitFor()
await page.waitForTimeout(300)
await page.getByRole('button', { name: 'Shell length', exact: true }).click()
await page.waitForTimeout(250)
ok('expected growth label', await page.getByText('Dashed: expected 9 µm/day').isVisible())
ok('checks table', (await page.locator('section[aria-label="Checks"] tbody tr').count()) === 5)
await page.getByRole('button', { name: 'Explain' }).click()
await page.getByText('Written by Claude from the numbers above').waitFor()
await page.waitForTimeout(200)
await page.screenshot({ path: `${out}/final-8-tank.png`, fullPage: true })
ok('explain caption', true)

ok('no console errors', logs.length === 0, logs.join(' | '))
console.log(`\n${results.filter(Boolean).length} of ${results.length} passed in ${((Date.now() - started) / 1000).toFixed(1)} s`)
await browser.close()
