export const ENV_ID = 'richieshao-1980-d9f5588r8f7850a1'

/**
 * 数据通道：CloudBase HTTP 访问路由（免鉴权、跨域已开）
 *   https://<env>.service.tcloudbase.com/quant-api
 *   该路由由 tcb api CreateCloudBaseGWAPI 创建（CLI 的 routes add 不支持系统内部域名）
 *
 * 注：曾保留 JS SDK callFunction 作备用通道，但本环境匿名登录关闭、匿名角色无云函数策略，
 *     该分支实际不可用，却使产物多出约 750KB 动态分包，故已移除。若日后需恢复，
 *     须先在控制台开启匿名登录并给匿名角色授予云函数调用权限。
 *
 * 覆盖方式：web/.env 写 VITE_HTTP_API=<你的地址>。
 */
const DEFAULT_HTTP = `https://${ENV_ID}.service.tcloudbase.com/quant-api`
const raw = import.meta.env.VITE_HTTP_API
// 智能默认：在 CloudBase 托管域上直连，在其他镜像域（如 WorkBuddy 发布）走同源 /quant-api 代理
const HTTP_BASE =
  raw ||
  (typeof location !== 'undefined' && /tcloudbase/.test(location.hostname)
    ? DEFAULT_HTTP
    : '/quant-api')

export const hasHttp = Boolean(HTTP_BASE)

/** 调用云端 api 函数，返回已解析的 JSON 对象。 */
export async function callApi(action, params = {}) {
  const usp = new URLSearchParams({ action, ...stringify(params) })
  const url = `${HTTP_BASE}?${usp.toString()}`
  let lastErr
  // 冷启动偶发「空响应」：最多重试 3 次（退避 400/900ms），避免首屏直接报错
  for (let i = 0; i < 3; i++) {
    if (i) await new Promise((r) => setTimeout(r, i * 400 + 100))
    try {
      const r = await fetch(url, { cache: 'no-store' })
      if (!r.ok) throw new Error(`接口返回 ${r.status}`)
      const text = await r.text()
      if (!text.trim()) {
        lastErr = new Error('接口返回空数据')
        continue
      }
      return JSON.parse(text)
    } catch (e) {
      lastErr = e
    }
  }
  throw lastErr || new Error('接口调用失败')
}

function stringify(obj) {
  const o = {}
  for (const [k, v] of Object.entries(obj)) {
    if (v !== undefined && v !== null) o[k] = String(v)
  }
  return o
}
