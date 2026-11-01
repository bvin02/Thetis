// Takes the screens that have a design PNG, at the design's own size. Needs: npm run seed:full
import { chromium } from '@playwright/test'
const out = process.argv[2] ?? '../data/shots'
const browser = await chromium.launch()
const shots = [
  ['home', '/', 1440, 1740, null],
  ['home-t04-selected', '/?tank=T-04', 1440, 1604, null],
  ['home-table-view', '/?tank=T-02', 1440, 1600, 'table'],
  ['photo-library', '/photos', 1440, 900, null],
]
for (const [name, path, width, height, mode] of shots) {
  const page = await browser.newPage({ viewport: { width, height } })
  await page.goto(`http://localhost:5173${path}`, { waitUntil: 'networkidle' })
  if (mode === 'table') await page.getByRole('button', { name: 'Table', exact: true }).click()
  await page.waitForTimeout(400)
  await page.screenshot({ path: `${out}/mine-${name}.png` })
  await page.close()
}
const phone = await browser.newPage({ viewport: { width: 390, height: 844 } })
await phone.goto('http://localhost:5173/', { waitUntil: 'networkidle' })
await phone.waitForTimeout(400)
await phone.screenshot({ path: `${out}/mine-home-phone.png`, fullPage: true })
await browser.close()
