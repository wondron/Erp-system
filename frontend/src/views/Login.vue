<script setup lang="ts">
import { ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useAuthStore } from "@/stores/auth";

const username = ref("");
const password = ref("");
const loading = ref(false);
const err = ref("");

const route = useRoute();
const router = useRouter();
const auth = useAuthStore();

const onSubmit = async () => {
  err.value = "";
  loading.value = true;
  try {
    await auth.login(username.value, password.value);
    const redirect = (route.query.redirect as string) || "/";
    router.replace(redirect);
  } catch (e: any) {
    err.value = e?.response?.data?.detail || "登录失败";
  } finally {
    loading.value = false;
  }
};
</script>

<template>
  <div class="min-h-screen flex items-center justify-center bg-gray-50">
    <div class="w-full max-w-sm bg-white p-6 rounded-2xl shadow">
      <h1 class="text-xl font-semibold mb-4">ERP 登录</h1>
      <form @submit.prevent="onSubmit" class="space-y-3">
        <input v-model="username" placeholder="用户名" class="w-full border rounded-xl p-2" />
        <input v-model="password" type="password" placeholder="密码" class="w-full border rounded-xl p-2" />
        <button :disabled="loading" class="w-full rounded-xl p-2 border">
          {{ loading ? "登录中…" : "登录" }}
        </button>
      </form>
      <p v-if="err" class="text-red-600 text-sm mt-3">{{ err }}</p>
    </div>
  </div>
</template>

<style scoped>
/* 你也可以直接用 Tailwind；若未装，可先用简单样式 */
</style>
