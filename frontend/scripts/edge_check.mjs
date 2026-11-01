// Edge cases driven in a real browser. Claude responses are mocked here: this script never spends credits.
import { chromium } from '@playwright/test'
import fs from 'node:fs'
import path from 'node:path'

const out = process.argv[2] ?? '../data/shots'
const repo = path.resolve(process.cwd(), '..')
const browser = await chromium.launch()
const results = []
const ok = (name, pass, detail = '') => { results.push({ name, pass, detail }); console.log(`${pass ? 'PASS' : 'FAIL'}  ${name}${detail ? `  (${detail})` : ''}`) }

async function newPage(width = 1440, height = 1000) {
  const page = await browser.newPage({ viewport: { width, height } })
  page.logs = []
  page.on('console', (m) => { if (['error', 'warning'].includes(m.type())) page.logs.push(`[${m.type()}] ${m.text().slice(0, 240)}`) })
  page.on('pageerror', (e) => page.logs.push(`[pageerror] ${e.message}`))
  // Nothing in this script may reach the real Claude API
  await page.route('**/api/claude/second-opinion', (route) => route.fulfill({ json: { opinions: { 6: { cls: 'dead', confidence: 'high', reason: 'Empty shell, outline only' } }, cached: false, model: 'mock' } }))
  await page.route('**/api/claude/explain', (route) => route.fulfill({ json: { text: 'Dead larvae rose to 24% from 9%. These numbers match the pattern. The actions isolate the tank.', cached: false, model: 'mock' } }))
  return page
}
const panel = (page) => page.locator('aside[aria-label="Check details"]')

// 1. A photo with no grid: sizes and the estimate wait for a scale, then a drawn line supplies it
{
  const page = await newPage()
  await page.goto('http://localhost:5173/checks/new?tank=T-05', { waitUntil: 'networkidle' })
  await page.getByRole('button', { name: 'Use a sample slide' }).click()
  await page.getByRole('menuitem', { name: /Malformed D-stage/ }).click()
  await page.locator('svg[role=application] polygon').first().waitFor()
  await page.waitForTimeout(300)
  ok('no grid: size asks for a scale', (await panel(page).innerText()).includes('Sizes need a scale'))
  ok('no grid: estimate asks for a scale', (await panel(page).innerText()).includes('The estimate needs a scale'))
  ok('no grid: caption offers Add a scale', await page.getByRole('button', { name: 'Add a scale' }).isVisible())
  await page.getByRole('button', { name: 'Add a scale' }).click()
  const box = await page.locator('svg[role=application]').boundingBox()
  await page.mouse.move(box.x + 100, box.y + 300)
  await page.mouse.down()
  await page.mouse.move(box.x + 400, box.y + 300, { steps: 6 })
  await page.mouse.up()
  await page.waitForTimeout(150)
  await page.screenshot({ path: `${out}/edge-scale.png` })
  await page.locator('#scale-um').fill('960')
  await page.getByRole('button', { name: 'Apply' }).click()
  await page.getByText(/manual scale/).waitFor()
  await page.waitForTimeout(350)
  const text = await panel(page).innerText()
  ok('manual scale: sizes appear', /±/.test(text), text.match(/\d+ ± \d+/)?.[0] ?? '')
  ok('manual scale: estimate appears', text.includes('live larvae'))
  await page.screenshot({ path: `${out}/edge-scale-done.png`, fullPage: true })
  ok('no console errors (scale)', page.logs.length === 0, page.logs.join(' | '))
  await page.close()
}

// 2. Bad file, two photos, removing one, over-stocked warning, save disabled without a tank
{
  const page = await newPage()
  await page.goto('http://localhost:5173/checks/new', { waitUntil: 'networkidle' })
  ok('save disabled before a photo', await page.getByRole('button', { name: 'Save check' }).isDisabled())
  const bad = path.join(repo, 'data', 'not-a-photo.jpg')
  fs.writeFileSync(bad, 'this is not an image')
  await page.locator('input[type=file]').first().setInputFiles(bad)
  await page.getByRole('alert').waitFor()
  ok('bad file shows a plain message', (await page.getByRole('alert').first().innerText()).includes('JPG or PNG'))
  fs.unlinkSync(bad)
  page.logs.length = 0 // the 422 above is expected, and the browser logs it

  await page.locator('input[type=file]').first().setInputFiles([
    path.join(repo, 'fixtures/slides/slide-healthy-umbo.jpg'), path.join(repo, 'fixtures/slides/slide-d-stage.jpg'),
  ])
  await page.getByRole('tab', { name: 'Photo 2' }).waitFor()
  await page.waitForTimeout(350)
  const both = await panel(page).locator('section[aria-label="Counts"]').innerText()
  ok('two photos: counts add up', both.includes('98 counted') || /\b9\d counted/.test(both), both.split('\n')[1])
  ok('save disabled without a tank', await page.getByRole('button', { name: 'Save check' }).isDisabled())
  await page.locator('#tank').selectOption('T-01')
  await page.waitForTimeout(300)
  ok('save enabled with tank and photo', await page.getByRole('button', { name: 'Save check' }).isEnabled())
  await page.locator('#concentration').fill('1')
  await page.waitForTimeout(350)
  ok('over-stocked warning shows', (await panel(page).innerText()).includes('More than were stocked'))
  await page.screenshot({ path: `${out}/edge-two-photos.png`, fullPage: true })
  await page.locator('#concentration').fill('50')
  await page.getByRole('button', { name: 'Remove photo 2' }).click()
  await page.waitForTimeout(350)
  ok('removing a photo updates counts', (await panel(page).locator('section[aria-label="Counts"]').innerText()).includes('44 counted'))
  await page.getByRole('button', { name: 'Remove photo 1' }).click()
  ok('removing the last photo returns to the drop zone', await page.getByText('Drop microscope photos here').isVisible())
  ok('no console errors (uploads)', page.logs.length === 0, page.logs.join(' | '))
  await page.close()
}

// 3. Zoom and pan
{
  const page = await newPage()
  await page.goto('http://localhost:5173/checks/new?tank=T-02', { waitUntil: 'networkidle' })
  await page.getByRole('button', { name: 'Use a sample slide' }).click()
  await page.getByRole('menuitem', { name: /Healthy umbo/ }).click()
  const svg = page.locator('svg[role=application]')
  await svg.locator('polygon').first().waitFor()
  const before = await svg.getAttribute('viewBox')
  const box = await svg.boundingBox()
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2)
  await page.mouse.wheel(0, -600)
  await page.waitForTimeout(100)
  const zoomed = await svg.getAttribute('viewBox')
  ok('wheel zooms in', zoomed !== before, zoomed)
  const scrollY = await page.evaluate(() => window.scrollY)
  ok('wheel does not scroll the page', scrollY === 0)
  await page.mouse.down()
  await page.mouse.move(box.x + box.width / 2 - 120, box.y + box.height / 2 - 60, { steps: 5 })
  await page.mouse.up()
  const panned = await svg.getAttribute('viewBox')
  ok('drag pans', panned !== zoomed, panned)
  await page.getByRole('button', { name: 'Fit' }).click()
  ok('Fit shows the whole photo', (await svg.getAttribute('viewBox')) === before)
  // Filters hide and show classes
  const liveCount = await svg.locator('polygon[stroke="#2E8B57"]').count()
  await page.getByRole('button', { name: /^Live/ }).click()
  ok('Live chip hides live outlines', (await svg.locator('polygon[stroke="#2E8B57"]').count()) === 0 && liveCount > 0)
  await page.getByRole('button', { name: /^Live/ }).click()
  await page.getByRole('button', { name: /^Ignored/ }).click()
  ok('Ignored chip shows ignored outlines', (await svg.locator('polygon[stroke="#AEB9C0"]').count()) > 0)
  // Arrow keys reach objects from the keyboard
  await page.getByRole('button', { name: /^Ignored/ }).click()
  await svg.focus()
  await page.keyboard.press('ArrowRight')
  await page.getByRole('dialog').waitFor()
  ok('arrow key selects an object', true)
  await page.keyboard.press('Escape')
  ok('no console errors (zoom)', page.logs.length === 0, page.logs.join(' | '))
  await page.close()
}

// 4. Claude on (mocked): opinions, accept, and Explain with its caption
{
  const page = await newPage()
  await page.route('**/api/claude/status', (route) => route.fulfill({ json: { enabled: true, model: 'mock', used_today: 0, limit: 100 } }))
  await page.goto('http://localhost:5173/checks/new?tank=T-03', { waitUntil: 'networkidle' })
  await page.getByRole('button', { name: 'Use a sample slide' }).click()
  await page.getByRole('menuitem', { name: /T-03 today/ }).click()
  await page.getByRole('button', { name: 'Ask Claude' }).waitFor()
  await page.getByRole('button', { name: 'Ask Claude' }).click()
  await page.getByText("Claude's second opinion").waitFor()
  const row = await panel(page).getByText(/Claude: Dead/).innerText()
  ok('opinion row wording', row.includes('Claude: Dead · Empty shell, outline only'), row)
  await page.getByRole('button', { name: 'Accept all' }).click()
  await page.waitForTimeout(300)
  const counts = await panel(page).locator('section[aria-label="Counts"]').innerText()
  ok('Accept all moves the larva to Dead', /Dead\n15/.test(counts))
  await page.goto('http://localhost:5173/tanks/T-04', { waitUntil: 'networkidle' })
  await page.getByRole('button', { name: 'Explain' }).click()
  await page.getByText('Written by Claude from the numbers above').waitFor()
  await page.locator('section[aria-label="Explain"]').screenshot({ path: `${out}/edge-explain.png` })
  ok('Explain shows text and caption', true)
  ok('no console errors (Claude on)', page.logs.length === 0, page.logs.join(' | '))
  await page.close()
}

// 5. Claude off: no buttons, nothing breaks
{
  const page = await newPage()
  await page.route('**/api/claude/status', (route) => route.fulfill({ json: { enabled: false, model: 'x', used_today: 0, limit: 100 } }))
  await page.goto('http://localhost:5173/checks/new?tank=T-03', { waitUntil: 'networkidle' })
  await page.getByRole('button', { name: 'Use a sample slide' }).click()
  await page.getByRole('menuitem', { name: /T-03 today/ }).click()
  await page.locator('svg[role=application] polygon').first().waitFor()
  await page.waitForTimeout(300)
  ok('no key: no Ask Claude', (await page.getByRole('button', { name: 'Ask Claude' }).count()) === 0)
  ok('no key: no crop note', (await page.getByText(/small crops? to Claude/).count()) === 0)
  await page.goto('http://localhost:5173/tanks/T-03', { waitUntil: 'networkidle' })
  await page.waitForTimeout(250)
  ok('no key: no Explain', (await page.getByRole('button', { name: 'Explain' }).count()) === 0)
  ok('no console errors (Claude off)', page.logs.length === 0, page.logs.join(' | '))
  await page.close()
}

// 6. Editing a saved check
{
  const page = await newPage()
  await page.goto('http://localhost:5173/checks', { waitUntil: 'networkidle' })
  await page.getByRole('button', { name: 'Larval room B' }).first().click()
  await page.waitForTimeout(300)
  const rows = await page.locator('tbody tr').count()
  ok('room filter narrows checks', rows > 0 && rows < 49, `${rows} rows`)
  await page.locator('tbody tr').first().click()
  await page.waitForURL(/checks\/\d+/)
  await page.getByRole('button', { name: 'Edit outlines' }).click()
  ok('Save changes starts disabled', await page.getByRole('button', { name: 'Save changes' }).isDisabled())
  const counts0 = await panel(page).locator('section[aria-label="Counts"]').innerText()
  await page.locator('svg[role=application] polygon[stroke="#2E8B57"]').nth(2).click({ force: true })
  await page.getByRole('dialog').waitFor()
  await page.keyboard.press('3')
  await page.getByRole('button', { name: 'Save changes' }).click()
  await page.getByRole('button', { name: 'Edit outlines' }).waitFor()
  await page.waitForTimeout(300)
  const counts1 = await panel(page).locator('section[aria-label="Counts"]').innerText()
  ok('saved correction changes the counts', counts0 !== counts1)
  await page.screenshot({ path: `${out}/edge-edited.png` })
  ok('no console errors (edit)', page.logs.length === 0, page.logs.join(' | '))
  await page.close()
}

// 7. Server unreachable: clear message, retry works
{
  const page = await newPage()
  let down = true
  await page.route('http://localhost:5173/api/**', (route) => (down ? route.abort() : route.fallback()))
  await page.goto('http://localhost:5173/', { waitUntil: 'load' })
  await page.getByRole('alert').first().waitFor({ timeout: 15000 })
  const text = await page.getByRole('alert').first().innerText()
  ok('server down: plain message', text.includes("Can't reach the Thetis server"), text.replace(/\n/g, ' '))
  await page.screenshot({ path: `${out}/edge-down.png` })
  down = false
  await page.getByRole('button', { name: 'Try again' }).click()
  await page.locator('h1').waitFor()
  ok('Try again recovers', (await page.locator('h1').innerText()).includes('tank'))
  await page.close()
}

// 8. Keyboard: focus ring and tab order on the Floor
{
  const page = await newPage()
  await page.goto('http://localhost:5173/', { waitUntil: 'networkidle' })
  for (let i = 0; i < 3; i++) await page.keyboard.press('Tab')
  const outline = await page.evaluate(() => getComputedStyle(document.activeElement).outlineStyle + ' ' + getComputedStyle(document.activeElement).outlineColor)
  ok('focus ring is visible', outline.startsWith('solid') && outline.includes('19, 85, 122'), outline)
  await page.locator('button[aria-label^="T-02,"]').first().focus()
  await page.screenshot({ path: `${out}/edge-focus.png`, clip: { x: 240, y: 180, width: 800, height: 480 } })
  await page.keyboard.press('Enter')
  await page.waitForTimeout(300)
  ok('Enter on a plan tank selects it', (await page.locator('aside[aria-label="Selected tank"]').innerText()).includes('T-02'))
  await page.close()
}

const failed = results.filter((r) => !r.pass)
console.log(`\n${results.length - failed.length} of ${results.length} passed`)
await browser.close()
