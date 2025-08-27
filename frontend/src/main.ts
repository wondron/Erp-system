import { createApp } from 'vue'
import { createPinia } from 'pinia'
import router from "./router" 
import App from './App.vue'
import './style.css'



const app = createApp(App);
const pinia = createPinia();

app.use(pinia);
app.use(router);

import { useAuthStore } from "./stores/auth";
const auth = useAuthStore();
auth.init();
// 简易持久化
auth.$subscribe((_mutation, state) => {
  localStorage.setItem("auth", JSON.stringify({
    accessToken: state.accessToken,
    refreshToken: state.refreshToken,
    user: state.user,
  }));
});

app.mount("#app");