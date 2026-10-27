/**
 * 前端端到端自检（目标检测模型页 · 本地离线识别链路）
 *
 * 验证：登录 -> 上传图片 -> 识别框与结果列表 -> 仅塑料瓶 -> 关闭摄像头清空 -> 加入检测结果明细
 * 依赖：playwright-core + 本机 Chromium（示例路径按需修改）
 *   npm i -D playwright-core
 *   node scripts/browser_check.mjs
 */
import { chromium } from 'playwright-core'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const CHROME = process.env.CHROME_PATH
  || 'C:\\Users\\91965\\AppData\\Local\\ms-playwright\\chromium-1248\\chrome-win64\\chrome.exe'
const BASE = process.env.BASE_URL || 'http://localhost:5173'
const IMAGE = process.env.TEST_IMAGE || path.join(ROOT, 'assets', 'probe-bottle-hand.jpg')

const checks = []
const log = (m) => console.log(m)
function check(ok, message) {
  checks.push([!!ok, message])
  log((ok ? '  ✓ ' : '  ✗ ') + message)
}

const browser = await chromium.launch({
  executablePath: CHROME,
  headless: true,
  args: ['--use-fake-ui-for-media-stream', '--use-fake-device-for-media-stream', '--no-sandbox'],
})
const context = await browser.newContext({ permissions: ['camera'], viewport: { width: 1680, height: 1000 } })
const page = await context.newPage()
const consoleErrors = []
const detectCalls = []
page.on('console', (m) => { if (m.type() === 'error') consoleErrors.push(m.text()) })
page.on('pageerror', (e) => consoleErrors.push(`PAGEERROR: ${e.message}`))
page.on('request', (r) => {
  const u = r.url()
  if (u.includes('/detect') && r.method() === 'POST') detectCalls.push(u)
  if (u.includes('/ai-api')) detectCalls.push(`CLOUD_CALL:${u}`)
})

try {
  log('='.repeat(60))
  log('前端端到端自检 · 本地离线识别')
  log('='.repeat(60))

  await page.goto(`${BASE}/login`, { waitUntil: 'domcontentloaded' })
  if (page.url().includes('/login')) {
    await page.getByPlaceholder('请输入用户名').fill('admin')
    await page.getByPlaceholder('请输入密码').fill('123456')
    await page.locator('.rv-login__submit').click()
    await page.waitForURL((u) => !u.pathname.includes('/login'), { timeout: 15000 })
  }
  check(!page.url().includes('/login'), '登录成功')

  await page.goto(`${BASE}/ai/detection`, { waitUntil: 'domcontentloaded' })
  await page.getByText('摄像头实时识别').waitFor({ timeout: 15000 })
  const tip = (await page.locator('.fp-camera-tip').innerText()).replace(/\s+/g, ' ')
  check(tip.includes('本地离线') || tip.includes('不访问外网'), '页面提示为本地离线模式')

  await page.setInputFiles('input[type=file]', IMAGE)
  let appeared = false
  for (let i = 0; i < 25; i++) {
    await page.waitForTimeout(2000)
    if ((await page.locator('.fp-result').count()) > 0) { appeared = true; break }
  }
  check(appeared, '上传图片后产生识别结果')

  const titles = await page.locator('.fp-result__title').allInnerTexts()
  check(titles.length > 0 && titles.every((t) => t.trim() === '塑料瓶'),
    `识别结果全部为塑料瓶（${JSON.stringify(titles)}）`)

  const meta = (await page.locator('.rv-card').filter({ hasText: '摄像头实时识别' })
    .locator('.rv-card-header .rv-text-secondary').innerText()).trim()
  check(meta.includes('本地 YOLO'), `模型标识为本地 YOLO（${meta}）`)

  const geom = await page.evaluate(() => {
    const frame = document.querySelector('.fp-camera-frame')
    const box = document.querySelector('.fp-box')
    if (!frame || !box) return null
    const fr = frame.getBoundingClientRect()
    const br = box.getBoundingClientRect()
    return {
      left: +(((br.left - fr.left) / fr.width) * 100).toFixed(1),
      top: +(((br.top - fr.top) / fr.height) * 100).toFixed(1),
      width: +((br.width / fr.width) * 100).toFixed(1),
      height: +((br.height / fr.height) * 100).toFixed(1),
    }
  })
  check(!!geom && geom.left >= 0 && geom.top >= 0 && geom.width > 0,
    `识别框在画面内且尺寸正常（${JSON.stringify(geom)}）`)

  const before = await page.locator('.el-table__row').count()
  if (titles.length) {
    await page.locator('.fp-result').first().getByRole('button', { name: '加入检测结果明细' }).click()
    await page.waitForTimeout(800)
    const after = await page.locator('.el-table__row').count()
    check(after === before + 1, `识别结果可写入检测明细（${before} -> ${after} 行）`)
  }

  // 关闭摄像头后应清空识别结果
  await page.getByRole('button', { name: '开启摄像头' }).click()
  await page.waitForTimeout(2200)
  await page.getByRole('button', { name: '关闭摄像头' }).click()
  await page.waitForTimeout(800)
  check((await page.locator('.fp-box').count()) === 0, '关闭摄像头后识别框清空')
  check((await page.locator('.fp-result').count()) === 0, '关闭摄像头后识别结果清空')

  check(detectCalls.length > 0, `前端调用了本地 /detect 接口（${detectCalls.length} 次）`)
  check(!detectCalls.some((u) => u.startsWith('CLOUD_CALL')), '未发起任何云端模型调用（完全离线）')

  const realErrors = consoleErrors.filter((e) => !e.includes('ERR_ABORTED'))
  check(realErrors.length === 0, `控制台无错误（${realErrors.length}）`)

  await page.screenshot({ path: path.join(ROOT, 'reports', 'browser-self-check.png') })
} catch (error) {
  check(false, `执行异常: ${error.message.split('\n')[0]}`)
} finally {
  await browser.close()
}

const passed = checks.filter(([ok]) => ok).length
console.log('='.repeat(60))
console.log(`前端自检: ${passed}/${checks.length} 项通过`)
checks.filter(([ok]) => !ok).forEach(([, m]) => console.log('  - ' + m))
console.log('='.repeat(60))
process.exit(passed === checks.length ? 0 : 1)
