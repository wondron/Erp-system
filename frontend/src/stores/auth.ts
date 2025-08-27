import { defineStore } from "pinia";
import { loginApi, refreshApi, logoutApi } from "@/api/auth";
import type { LoginResponse, LegacyLoginResponse, JwtLoginResponse } from "@/types/auth";
import { isLegacy, isJwt } from "@/types/auth";

export type BackendUser = {
  username: string;
  showname: string;
  userrole: string;
  id?: number;
};
export type User = BackendUser | null;

type PersistedAuth = { accessToken: string; refreshToken: string; user: User };
const STORAGE_KEY = "auth";

export const useAuthStore = defineStore("auth", {
  state: () => ({
    accessToken: "" as string,
    refreshToken: "" as string,
    user: null as User,
    _inited: false,
  }),
  getters: {
    isAuthenticated: (s) => !!s.accessToken || !!s.user,
    role: (s) => s.user?.userrole ?? "",
    displayName: (s) => s.user?.showname || s.user?.username || "",
  },
  actions: {
    init() { /* 同前 */ },

    setSession(payload: Partial<PersistedAuth>) { /* 同前 */ },

    clearSession() { /* 同前 */ },

    async login(username: string, password: string) {
      const { data } = await loginApi({ username, password }); // data: LoginResponse

      if (isLegacy(data)) {
        // 现在的后端
        this.setSession({
          accessToken: this.accessToken || "OK", // 占位，等有 JWT 再替换
          user: {
            username: data.username,
            showname: data.showname,
            userrole: data.userrole,
            id: data.id,
          },
        });
        return;
      }

      if (isJwt(data)) {
        this.setSession({
          accessToken: data.access_token,
          refreshToken: data.refresh_token || "",
          user: data.user
            ? {
                username: data.user.username,
                showname: data.user.showname,
                userrole: data.user.userrole,
                id: data.user.id,
              }
            : null,
        });
        return;
      }

      throw new Error("Unexpected login response");
    },

    async refresh() { /* 同前 */ },
    async logout() { /* 同前 */ },
    attachAuthHeader(headers: Record<string, string>) { /* 同前 */ },
    hasRole(...roles: string[]) { /* 同前 */ },
  },
});
