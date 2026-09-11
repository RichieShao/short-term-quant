/**
 * 诊断：以匿名身份 callFunction 是否被环境层面拦截
 * 对照调用 api（本项目函数）与 getQuotes（已有函数）
 */
import { JSDOM } from 'jsdom'
import { createRequire } from 'node:module'
import { fileURLToPath } from 'node:url'

const ENV_ID = 'richieshao-1980-d9f5588r8f7850a1'
const PAGE_URL = 'https://richieshao-1980-d9f5588r8f7850a1-1450128794.tcloudbaseapp.com/quant/'

const dom = new JSDOM('<!doctype html><html><body></body></html>', {
  url: PAGE_URL, pretendToBeVisual: true,
})
const w = dom.window
for (const k of ['window', 'document', 'localStorage', 'sessionStorage',
  'XMLHttpRequest', 'location', 'history', 'Event', 'CustomEvent',
  'MutationObserver', 'getComputedStyle']) {
  try { Object.defineProperty(globalThis, k, { value: w[k], configurable: true, writable: true }) } catch {}
}
Object.defineProperty(globalThis, 'navigator', { value: w.navigator, configurable: true })

const require = createRequire(import.meta.url)
const cloudbase = require(fileURLToPath(
  new URL('../node_modules/@cloudbase/js-sdk/dist/index.cjs.js', import.meta.url)))

const app = cloudbase.init({ env: ENV_ID })
const auth = app.auth({ persistence: 'local' })

const ls = await auth.signInAnonymously()
console.log('匿名 uid =', ls && ls.user && ls.user.uid)

for (const [name, data] of [
  ['api', { action: 'latest' }],
  ['getQuotes', { codes: 'sh000001' }],
  ['cf-fund-api', { action: 'ping' }],
]) {
  try {
    const r = await app.callFunction({ name, data })
    const s = JSON.stringify(r.result)
    console.log(`✓ ${name} -> ${s.slice(0, 120)}`)
  } catch (e) {
    console.log(`✗ ${name} -> ${(e && (e.message || e.code)) || e}`.slice(0, 200))
  }
}
process.exit(0)
