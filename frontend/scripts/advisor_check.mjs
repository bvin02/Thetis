// Browser checks for the Advisor. Every Claude call is mocked, so this spends nothing. Needs a fresh demo seed: npm run seed
import { chromium } from '@playwright/test'

const out = process.argv[2] ?? '../data/shots'
const base = 'http://localhost:5173'
const results = []
const ok = (name, pass, detail = '') => { results.push(pass); console.log(`${pass ? 'PASS' : 'FAIL'}  ${name}${detail ? `  (${detail})` : ''}`) }
const browser = await chromium.launch()

const ANALYSIS = {
  headline: 'Buffer line 2 now: Ω aragonite is 1.4 and 56.9M larvae are at stake.',
  brief: 'Line 2 water turned corrosive a day ago, putting T-04, T-05 and T-06 at risk.',
  do_first: [
    { ref: 'line-L2', action: 'Buffer line 2 with soda ash, 96 g total.', why: 'Ω 1.4 on line 2. 56.9M larvae at stake.' },
    { ref: 'yield-T-07-setting', action: 'Grade T-07 and move the largest to S-02.', why: 'Losing about 344k larvae a day.' },
    { ref: '', action: 'Sample T-10.', why: 'Gut fell to 0.32.' },
  ],
}
const sseBody = (events) => events.map((e) => `data: ${JSON.stringify(e)}\n\n`).join('')

async function newPage(viewport = { width: 1440, height: 900 }) {
  const page = await browser.newPage({ viewport })
  page.errors = []
  page.on('console', (m) => { if (['error', 'warning'].includes(m.type()) && !page.allowErrors) page.errors.push(m.text().slice(0, 200)) })
  page.on('pageerror', (e) => page.errors.push(e.message))
  return page
}

/** Pretend Claude is on and nothing is stored, and answer analyze with these events. */
async function mockClaude(page, { events, enabled = true, askEvents, stored = null } = {}) {
  await page.route('**/api/advisor', async (route) => {
    const response = await route.fetch()
    const json = await response.json()
    await route.fulfill({
      json: {
        ...json,
        claude: { ...json.claude, enabled },
        analysis: stored,
        analysis_fresh: stored !== null,
        analysis_running: false,
      },
    })
  })
  await page.route('**/api/advisor/analyze', (route) => route.fulfill({ status: 200, contentType: 'text/event-stream', body: sseBody(events ?? []) }))
  await page.route('**/api/advisor/ask', (route) => route.fulfill({ status: 200, contentType: 'text/event-stream', body: sseBody(askEvents ?? [{ type: 'delta', text: 'Mock.' }, { type: 'done', cached: false, model: 'mock' }]) }))
}

const insight = (over = {}) => ({
  kind: 'crash_risk', title: 'T-10 looks like T-03 did before it crashed', tank_ids: ['T-10', 'T-03'],
  body: 'Both slowed down first.', suggestion: 'Plate a T-10 sample on TCBS.', confidence: 'medium',
  evidence: [{ tank_id: 'T-10', label: 'gut fullness', value_text: '0.32', when_text: 'yesterday' }],
  step: {
    id: null, scope: 'tank', tank_id: 'T-10', line_id: null, check_id: null, action: 'claude_suggestion', title: 'Plate a T-10 sample on TCBS.',
    cta: 'Approve', done_text: 'Approved', status: 'pending', created_at: null, decided_at: null, decided_by: null, decided_text: null,
    note: null, is_example: false, how: null, dose: null,
  },
  ...over,
})
const STORED = { ...ANALYSIS, insights: [insight()], dropped: 0, model: 'mock', when_text: 'Today, 9:12 AM' }

// ------------------------------------------------------------------ rules only: no Claude
{
  const page = await newPage()
  await mockClaude(page, { enabled: false })
  await page.goto(`${base}/advisor`, { waitUntil: 'networkidle' })
  ok('headline states risks and yield', (await page.locator('h1').innerText()) === '3 risks could turn into a crash. 3 ways to raise yield.')
  ok('without Claude: no brief', (await page.locator('section[aria-label="Today\'s brief"]').count()) === 0)
  ok('without Claude: no chat', (await page.locator('section[aria-label="Ask Thetis"]').count()) === 0)
  const articles = await page.locator('section[aria-label="Crash risks"] article').count()
  ok('without Claude: rules still show 3 risks', articles === 3, String(articles))
  ok('without Claude: yield still shows 3', (await page.locator('section[aria-label="Raise yield"] article').count()) === 3)
  ok('without Claude: plant settings still show', await page.locator('section[aria-label="Your plant"]').isVisible())
  ok('rules-based label on risks and forecast', (await page.getByText('Rules-based').count()) >= 4)
  ok('example data label', await page.getByText('Example data').first().isVisible())
  ok('no console errors', page.errors.length === 0, page.errors.join(' | '))
  await page.close()
}

// ------------------------------------------------------------------ cards open and close
{
  const page = await newPage()
  await mockClaude(page, { enabled: false })
  await page.goto(`${base}/advisor`, { waitUntil: 'networkidle' })
  const line = page.locator('#line-L2')
  const t10 = page.locator('#tank-T-10')
  ok('first risk starts open', await line.getByText('per 1,000 L').isVisible())
  ok('other risks start closed', (await t10.getByRole('button', { name: /Request feed check/ }).count()) === 0)
  ok('a closed card still shows its next step', (await t10.innerText()).includes('Next: Check the algae ration'))
  ok('the title is a real button with its state', (await t10.getByRole('button', { name: /T-10: growing slower/ }).getAttribute('aria-expanded')) === 'false')
  await t10.getByRole('button', { name: /T-10: growing slower/ }).focus()
  await page.keyboard.press('Enter')
  await t10.getByRole('button', { name: /Request feed check/ }).waitFor()
  ok('the keyboard opens a card', (await t10.getByRole('button', { name: /T-10: growing slower/ }).getAttribute('aria-expanded')) === 'true')
  await t10.locator('div.rowbtn').click({ position: { x: 300, y: 8 } })
  await t10.getByRole('button', { name: /Request feed check/ }).waitFor({ state: 'detached' })
  ok('clicking the header closes it', true)
  await t10.locator('a[href="/tanks/T-10"]').click()
  await page.waitForURL(/tanks\/T-10/)
  ok('a tank link goes to the tank, without toggling', true)
  await page.close()
}

// ------------------------------------------------------------------ the Floor's "See how" opens the right card
{
  const page = await newPage()
  await mockClaude(page, { enabled: false })
  await page.goto(`${base}/`, { waitUntil: 'networkidle' })
  await page.getByRole('link', { name: 'See how' }).click()
  await page.waitForURL(/advisor#line-L2/)
  await page.locator('#line-L2').getByText('per 1,000 L').waitFor()
  ok('Floor to Advisor deep link', true)
  await page.goBack()
  await page.getByRole('link', { name: 'Open Advisor' }).click()
  await page.waitForURL(/advisor$/)
  ok('Open Advisor link', true)
  await page.close()
}

// ------------------------------------------------------------------ an analysis in progress, on the real streaming path
{
  const page = await newPage()
  let release
  const gate = new Promise((resolve) => { release = resolve })
  await page.route('**/api/advisor', async (route) => {
    const json = await (await route.fetch()).json()
    await route.fulfill({ json: { ...json, claude: { ...json.claude, enabled: true }, analysis: null, analysis_fresh: false, analysis_running: false } })
  })
  await page.route('**/api/advisor/analyze', async (route) => {
    await gate
    await route.fulfill({ status: 200, contentType: 'text/event-stream', body: sseBody([
      { status: 'writing', looking_at: [], analysis: { headline: ANALYSIS.headline, brief: ANALYSIS.brief }, done: false, error: null, model: 'mock' },
      { status: 'done', looking_at: [], analysis: ANALYSIS, done: true, error: null, model: 'mock', cached: false },
    ]) })
  })
  await page.goto(`${base}/advisor`, { waitUntil: 'domcontentloaded' })
  const brief = page.locator('section[aria-label="Today\'s brief"]')
  await brief.getByText('Claude is reading').waitFor()
  ok('says what Claude is reading', /Claude is reading \d+ checks across \d+ running tanks, 1 past batch and the decision log\./.test(await brief.innerText()))
  ok('no Run again while running', (await brief.getByRole('button', { name: /Run/ }).count()) === 0)
  ok('rules cards are already there while Claude reads', await page.locator('#line-L2').isVisible())
  ok('says it is looking for more', await page.getByText('Claude is looking for anything the rules missed.').isVisible())
  await page.screenshot({ path: `${out}/advisor-reading.png` })
  release()
  await brief.getByRole('button', { name: 'Run analysis' }).waitFor({ timeout: 10000 })
  ok('no stray errors after the stream ends', page.errors.length === 0, page.errors.join(' | '))
  await page.close()
}

// ------------------------------------------------------------------ a stored analysis: brief, insights, steps
{
  const page = await newPage()
  await mockClaude(page, { stored: STORED })
  await page.route('**/api/advisor/answer', (route) => route.fulfill({ json: { ...insight().step, id: 99, status: 'approved', decided_text: 'Dana Ortiz · Today, 9:20 AM' } }))
  await page.goto(`${base}/advisor`, { waitUntil: 'networkidle' })
  const brief = page.locator('section[aria-label="Today\'s brief"]')
  ok('brief headline', (await brief.innerText()).includes(ANALYSIS.headline))
  ok('labelled as written by Claude', await brief.getByText('Written by Claude').isVisible())
  ok('three steps to do first', (await brief.locator('ol li').count()) === 3)
  ok('a step with no card has no link', (await brief.getByRole('button', { name: /Go to steps/ }).count()) === 2)
  await brief.getByRole('button', { name: /Go to steps/ }).nth(1).click()
  await page.locator('#yield-T-07-setting').getByRole('button', { name: 'Schedule grading' }).waitFor()
  await page.waitForTimeout(700)
  const box = await page.locator('#yield-T-07-setting').boundingBox()
  ok('Go to steps scrolls to the card', box.y >= 0 && box.y < 200, `y ${Math.round(box.y)}`)
  const found = page.locator('article', { hasText: 'T-10 looks like T-03' })
  ok('insight tagged as found by Claude', await found.getByText('Found by Claude').isVisible())
  ok('insight confidence shown', await found.getByText('Medium confidence').isVisible())
  ok('evidence shown', (await found.innerText()).includes('gut fullness') && (await found.innerText()).includes('0.32'))
  ok('says the readings were checked', (await found.innerText()).includes('checked against your records'))
  await found.getByRole('button', { name: 'Approve' }).click()
  ok('no stray errors', page.errors.length === 0, page.errors.join(' | '))
  await page.close()
}

// ------------------------------------------------------------------ a stored analysis that's out of date, and failures
{
  const page = await newPage()
  page.allowErrors = true // the browser logs a failed request by itself
  await page.route('**/api/advisor', async (route) => {
    const json = await (await route.fetch()).json()
    await route.fulfill({ json: { ...json, claude: { ...json.claude, enabled: true }, analysis: STORED, analysis_fresh: false, analysis_running: false } })
  })
  await page.route('**/api/advisor/analyze', (route) => route.fulfill({ status: 429, json: { detail: 'Daily Claude limit reached' } }))
  await page.goto(`${base}/advisor`, { waitUntil: 'networkidle' })
  const brief = page.locator('section[aria-label="Today\'s brief"]')
  await brief.getByText('Daily Claude limit reached').waitFor()
  ok('over the limit: says so', true)
  ok('over the limit: the old brief stays, marked out of date', (await brief.innerText()).includes(ANALYSIS.headline) && (await brief.innerText()).includes('Written before the latest changes'))
  ok('over the limit: can try again', await brief.getByRole('button', { name: 'Run again' }).isVisible())
  await page.close()

  const failing = await newPage()
  await mockClaude(failing, { events: [{ status: 'failed', looking_at: [], analysis: null, done: false, error: 'Claude rejected the API key in .env.', model: 'mock' }] })
  await failing.goto(`${base}/advisor`, { waitUntil: 'networkidle' })
  const again = failing.locator('section[aria-label="Today\'s brief"]')
  await again.getByText('Claude rejected the API key in .env.').waitFor()
  ok('a failed run says why', true)
  ok('a failed run can be retried', await again.getByRole('button', { name: 'Run analysis' }).isVisible())
  ok('a failed run leaves the rules cards', await failing.locator('#line-L2').isVisible())
  await failing.close()
}

// ------------------------------------------------------------------ changing a chemical doesn't start a paid run
{
  const page = await newPage()
  await mockClaude(page, { stored: STORED })
  let runs = 0
  page.on('request', (r) => { if (r.url().endsWith('/api/advisor/analyze')) runs += 1 })
  await page.goto(`${base}/advisor`, { waitUntil: 'networkidle' })
  ok('a fresh analysis starts no run', runs === 0)
  const line = page.locator('#line-L2')
  await line.locator('select').selectOption('sodium_hydroxide')
  await line.getByText('Caustic. Dilute it first', { exact: false }).waitFor()
  ok('the dose changes straight away', /\b6 g per 1,000 L/.test(await line.innerText()))
  const plant = page.locator('section[aria-label="Your plant"]')
  ok('the plant card follows', (await plant.locator('select').first().inputValue()) === 'sodium_hydroxide')
  await page.waitForTimeout(500)
  ok('changing a chemical starts no run', runs === 0, String(runs))
  await plant.locator('select').first().selectOption('sodium_carbonate')
  await line.getByText('16 g per 1,000 L').waitFor()
  ok('and back again', true)
  await page.close()
}

// ------------------------------------------------------------------ Ask Thetis
{
  const page = await newPage()
  await mockClaude(page, {
    stored: STORED,
    askEvents: [
      { type: 'delta', text: '**Buffer line 2 first.** T-04 is the worst.\n\n' },
      { type: 'delta', text: '1. Dose it.\n2. Re-check T-05.\n\n- A bullet about <b>markup</b>' },
      { type: 'done', cached: false, model: 'mock' },
    ],
  })
  await page.goto(`${base}/advisor`, { waitUntil: 'networkidle' })
  const ask = page.locator('section[aria-label="Ask Thetis"]')
  ok('suggested questions', (await ask.getByRole('button').count()) >= 5)
  await ask.getByRole('textbox').fill('What should I do first?')
  await page.keyboard.press('Enter')
  await ask.getByRole('button', { name: 'Start a new conversation' }).waitFor()
  await ask.locator('ol li').first().waitFor()
  ok('question stays in the chat', (await ask.innerText()).includes('What should I do first?'))
  ok('bold renders', (await ask.locator('strong').first().innerText()) === 'Buffer line 2 first.')
  ok('numbered list renders', (await ask.locator('ol li').count()) === 2)
  ok('tank ids become links', (await ask.locator('a[href="/tanks/T-05"]').count()) === 1)
  ok('markup from the model stays text', (await ask.locator('b').count()) === 0 && (await ask.innerText()).includes('<b>markup</b>'))
  await ask.getByRole('button', { name: 'Start a new conversation' }).click()
  ok('new conversation clears it', (await ask.innerText()).includes('Ask about any tank'))
  await page.close()

  const failing = await newPage()
  await mockClaude(failing, { stored: STORED, askEvents: [{ type: 'error', message: 'Daily Claude limit reached' }] })
  await failing.goto(`${base}/advisor`, { waitUntil: 'networkidle' })
  const box = failing.locator('section[aria-label="Ask Thetis"]')
  await box.getByRole('textbox').fill('Will this work?')
  await box.getByRole('button', { name: 'Send' }).click()
  await box.getByText('Daily Claude limit reached').waitFor()
  ok('a failed question says why', true)
  await box.locator('button[aria-label="Send"] .spin').waitFor({ state: 'detached' })
  ok('a failed question goes back in the box', (await box.getByRole('textbox').inputValue()) === 'Will this work?')
  await failing.close()
}

// ------------------------------------------------------------------ a chat stream that just stops
{
  const page = await newPage()
  await mockClaude(page, { stored: STORED, askEvents: [{ type: 'delta', text: 'Half an ans' }] })
  await page.goto(`${base}/advisor`, { waitUntil: 'networkidle' })
  const box = page.locator('section[aria-label="Ask Thetis"]')
  await box.getByRole('textbox').fill('Will this finish?')
  await box.getByRole('button', { name: 'Send' }).click()
  await box.getByText("Claude's answer was cut off. Try again.").waitFor()
  ok('a stream that stops says so', true)
  ok('the half answer leaves the conversation', !(await box.innerText()).includes('Half an ans'))
  ok('the question goes back in the box', (await box.getByRole('textbox').inputValue()) === 'Will this finish?')
  await page.close()
}

// ------------------------------------------------------------------ the chat stays in view
{
  const page = await newPage()
  await mockClaude(page, { stored: STORED })
  await page.goto(`${base}/advisor`, { waitUntil: 'networkidle' })
  await page.evaluate(() => window.scrollTo(0, 1600))
  await page.waitForTimeout(250)
  const box = await page.locator('section[aria-label="Ask Thetis"]').boundingBox()
  ok('chat stays in view while scrolling', box.y >= 0 && box.y < 40 && box.y + box.height <= 900, `y ${Math.round(box.y)}, h ${Math.round(box.height)}`)
  await page.screenshot({ path: `${out}/advisor-scrolled.png` })
  await page.close()
}

// ------------------------------------------------------------------ phone and tablet: no sideways scroll
for (const width of [390, 768, 1100, 1280, 1920]) {
  const page = await newPage({ width, height: 844 })
  await mockClaude(page, { stored: STORED })
  await page.goto(`${base}/advisor`, { waitUntil: 'networkidle' })
  await page.waitForTimeout(200)
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)
  ok(`${width} px: no sideways page scroll`, overflow <= 0, String(overflow))
  await page.screenshot({ path: `${out}/advisor-${width}.png`, fullPage: true })
  if (width === 390) {
    const small = await page.evaluate(() => {
      const bad = []
      for (const el of document.querySelectorAll('main button, main a.ghost, main a.solid, main select')) {
        // A card's title sits in a header that's clickable all over, so the header is what a thumb hits
        const r = (el.getAttribute('aria-expanded') !== null ? el.closest('.rowbtn') : el).getBoundingClientRect()
        if (r.width > 0 && r.height > 0 && r.height < 44 && !el.classList.contains('lnk')) bad.push(`${el.tagName} "${(el.innerText || el.getAttribute('aria-label') || '').slice(0, 30)}" ${Math.round(r.height)}`)
      }
      return bad
    })
    ok('390 px: tap targets at least 44 px', small.length === 0, small.slice(0, 6).join('; '))
    ok('390 px: a jump to the chat', await page.getByRole('link', { name: 'Ask Thetis a question' }).isVisible())
  }
  ok(`${width} px: no console errors`, page.errors.length === 0, page.errors.join(' | '))
  await page.close()
}

console.log(`\n${results.filter(Boolean).length} of ${results.length} passed`)
await browser.close()
