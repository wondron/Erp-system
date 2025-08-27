// src/stores/auth.ts
import { defineStore } from "pinia";
import { loginApi, refreshApi, logoutApi } from "@/api/auth";

type User = { id: number; name: string; role: string } | null;

export const useAuthStore = defineStore("auth", {
  state: () => ({
    accessToken: "" as string,
    refreshToken: "" as string, // 如果用 cookie，可不存
    user: null as User,
  }),
  getters: {
    isAuthenticated: (s) => !!s.accessToken || !!s.user, // 视策略调整
  },
  actions: {
    async login(username: string, password: string) {
      const { data } = await loginApi({ username, password });
      this.accessToken = data.access_token;
      if (data.refresh_token) this.refreshToken = data.refresh_token;
      this.user = data.user;
    },
    async refresh() {
      const { data } = await refreshApi();
      this.accessToken = data.access_token;
    },
    async logout() {
      try { await logoutApi(); } catch {}
      this.$reset();
    },
    loadFromStorage() {
      const raw = localStorage.getItem("auth");
      if (raw) {
        const parsed = JSON.parse(raw);
        this.accessToken = parsed.accessToken;
        this.refreshToken = parsed.refreshToken;
        this.user = parsed.user;
      }
    },
  },
});

// 可在 main.ts 里订阅持久化
