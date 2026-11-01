import { chromium } from '@playwright/test'
const browser = await chromium.launch()
const page = await browser.newPage({ viewport: { width: 1440, height: 1740 } })
async function probe(label) {
  const res = await page.evaluate(() => {
    const want = ['Act now', 'Monitor', 'Larvae in hatchery', 'Floor plan', 'Last 14 days', 'Latest check', 'Risk forecast', 'Condition', 'Survival since spawn', 'Recommended actions']
    const out = {}
    const all = [...document.querySelectorAll('span,h1,h2,h3,dt,p,div,a,button')]
    for (const w of want) {
      const el = all.find((e) => e.childElementCount === 0 && e.textContent.trim() === w)
      if (el) { const r = el.getBoundingClientRect(); out[w] = [Math.round(r.x*10)/10, Math.round(r.y*10)/10, Math.round(r.height*10)/10] }
    }
    const h1 = document.querySelector('h1').getBoundingClientRect(); out.h1 = [h1.x, h1.y, h1.height]
    const cs = getComputedStyle(document.querySelector('h1')); out.font = cs.fontFamily.slice(0, 40); out.lh = getComputedStyle(document.body).lineHeight
    const aside = document.querySelector('aside[aria-label="Selected tank"]').getBoundingClientRect(); out.inspector = [aside.x, aside.y, aside.width, aside.height]
    return out
  })
  console.log(label, JSON.stringify(res))
}
await page.goto('file:///Users/bhavinsg/Projects/Thetis/design/html/home.html', { waitUntil: 'load' })
await page.waitForTimeout(500)
await probe('design')
await page.goto('http://localhost:5173/', { waitUntil: 'networkidle' })
await page.waitForTimeout(300)
await probe('mine  ')
await browser.close()
