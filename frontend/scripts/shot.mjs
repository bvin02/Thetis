// Screenshot helper: node scripts/shot.mjs <path> <out.png> [width] [height] [--full]
import { chromium } from '@playwright/test'

const [, , path = '/', out = 'shot.png', width = '1440', height = '900', ...rest] = process.argv
const full = rest.includes('--full')
const browser = await chromium.launch()
const page = await browser.newPage({ viewport: { width: Number(width), height: Number(height) } })
const logs = []
page.on('console', (m) => { if (['error', 'warning'].includes(m.type())) logs.push(`[${m.type()}] ${m.text()}`) })
page.on('pageerror', (e) => logs.push(`[pageerror] ${e.message}`))
await page.goto(`http://localhost:5173${path}`, { waitUntil: 'networkidle' })
await page.waitForTimeout(400)
await page.screenshot({ path: out, fullPage: full })
const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)
console.log(JSON.stringify({ out, overflowX: overflow, logs }))
await browser.close()
