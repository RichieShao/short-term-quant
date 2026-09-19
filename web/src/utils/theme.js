// web/src/utils/theme.js —— 深浅色：只翻转 :root[data-theme]
// 组件全部走 CSS 变量，切换即整套生效，无需改组件。
export function currentTheme () {
  let saved = null
  try { saved = localStorage.getItem('stq-theme') } catch (e) { /* 隐私模式忽略 */ }
  if (saved === 'light' || saved === 'dark') return saved
  const prefersDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches
  return prefersDark ? 'dark' : 'light'
}

export function applyTheme (t) {
  document.documentElement.setAttribute('data-theme', t)
  try { localStorage.setItem('stq-theme', t) } catch (e) { /* 忽略 */ }
  document.documentElement.style.colorScheme = t // 影响原生滚动条/表单
}

export function initTheme () { applyTheme(currentTheme()) }
