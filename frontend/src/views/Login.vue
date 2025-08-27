<!-- src/views/Login.vue -->
<script setup lang="ts">
import { ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useAuthStore } from "@/stores/auth";

const route = useRoute();
const router = useRouter();
const auth = useAuthStore();

const username = ref("admin");
const password = ref("123456");
const loading  = ref(false);
const errorMsg = ref("");

async function onSubmit() {
  errorMsg.value = "";
  loading.value = true;
  try {
    // 调用 pinia 的登录动作（内部会请求 /login/auth）
    await auth.login(username.value, password.value);

    // 登录成功后回跳
    const redirect = (route.query.redirect as string) || "/";
    router.replace(redirect);
  } catch (err: any) {
    // 打印出来方便你在控制台看
    console.error("login failed:", err);
    // 统一展示错误
    errorMsg.value = err?.response?.data?.detail || "登录失败，请检查账号或密码";
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <div class="min-h-screen p-10">
    <h1 class="text-5xl font-extrabold mb-10">ERP 登录</h1>

    <form class="flex items-center gap-2" @submit.prevent="onSubmit">
      <input
        v-model="username"
        placeholder="用户名"
        class="border rounded px-3 py-2 w-60"
        autocomplete="username"
      />
      <input
        v-model="password"
        type="password"
        placeholder="密码"
        class="border rounded px-3 py-2 w-80"
        autocomplete="current-password"
      />
      <button
        type="submit"
        class="border rounded px-4 py-2"
        :disabled="loading"
      >
        {{ loading ? "登录中…" : "登录" }}
      </button>
    </form>

    <p v-if="errorMsg" class="text-red-600 mt-4">{{ errorMsg }}</p>
  </div>
</template>
