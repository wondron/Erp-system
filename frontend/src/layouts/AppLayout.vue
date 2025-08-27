<script setup lang="ts">
import { useAuthStore } from "@/stores/auth";
import { useRouter } from "vue-router";
const auth = useAuthStore();
const router = useRouter();
const onLogout = async () => {
  await auth.logout();
  router.replace({ name: "Login" });
};
</script>

<template>
  <div class="min-h-screen grid" style="grid-template-columns: 220px 1fr; grid-template-rows: 56px 1fr;">
    <!-- Sidebar -->
    <aside class="row-span-2 bg-gray-100 p-4">
      <div class="font-semibold mb-4">ERP</div>
      <nav class="space-y-2">
        <RouterLink to="/" class="block">仪表盘</RouterLink>
        <RouterLink to="/users" class="block">用户管理</RouterLink>
      </nav>
    </aside>

    <!-- Header -->
    <header class="col-start-2 bg-white border-b flex items-center justify-between px-4">
      <div>欢迎，{{ auth.user?.name || "用户" }}</div>
      <button class="border rounded-lg px-3 py-1" @click="onLogout">退出登录</button>
    </header>

    <!-- Main -->
    <main class="col-start-2 p-4">
      <RouterView />
    </main>
  </div>
</template>
