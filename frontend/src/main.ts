import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { router } from '@/router'
import App from './App.vue'   // ★ 引入刚刚新建的 App.vue
import './style.css'

// createApp(App).use(createPinia()).use(router).mount('#app')


const app = createApp(App);
const pinia = createPinia();

app.use(pinia);
app.use(router);

import { useAuthStore } from "./stores/auth";
const auth = useAuthStore();
auth.loadFromStorage();
// 简易持久化
auth.$subscribe((_mutation, state) => {
  localStorage.setItem("auth", JSON.stringify({
    accessToken: state.accessToken,
    refreshToken: state.refreshToken,
    user: state.user,
  }));
});

app.mount("#app");