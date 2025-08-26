import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { router } from '@/router'
import App from './App.vue'   // ★ 引入刚刚新建的 App.vue
import './style.css'

createApp(App).use(createPinia()).use(router).mount('#app')
