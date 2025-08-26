import { createRouter, createWebHistory } from 'vue-router'
import Users from '@/views/Users.vue' // 若别名未好，改成 '../views/Users.vue'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'Users', component: Users },
  ],
})