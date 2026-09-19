import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import './styles/theme.css'
import { initTheme } from './utils/theme'

// 深浅色：index.html 内联引导已预防首屏闪白；此处再初始化一次，保证与 localStorage / 系统偏好一致
initTheme()

createApp(App).use(createPinia()).mount('#app')
