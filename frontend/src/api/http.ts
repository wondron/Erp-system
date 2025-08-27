// src/api/http.ts
import axios from "axios";
import { useAuthStore } from "@/stores/auth";

const http = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL,
  withCredentials: true, // 若使用 httpOnly cookie，需开启
});

http.interceptors.request.use((config) => {
  const auth = useAuthStore();
  if (auth.accessToken) {
    config.headers = config.headers || {};
    (config.headers as any).Authorization = `Bearer ${auth.accessToken}`;
  }
  return config;
});

let isRefreshing = false;
let pending: Array<() => void> = [];

http.interceptors.response.use(
  (res) => res,
  async (err) => {
    const auth = useAuthStore();
    const status = err.response?.status;

    // 401 尝试刷新
    if (status === 401 && auth.refreshToken && !isRefreshing) {
      isRefreshing = true;
      try {
        await auth.refresh(); // 刷新成功会更新 accessToken
        isRefreshing = false;
        pending.forEach((cb) => cb());
        pending = [];
        // 重试原请求
        err.config.headers.Authorization = `Bearer ${auth.accessToken}`;
        return http.request(err.config);
      } catch (e) {
        isRefreshing = false;
        pending = [];
        auth.logout();
        return Promise.reject(e);
      }
    } else if (status === 401 && isRefreshing) {
      // 将请求挂起，等刷新完成后重试
      return new Promise((resolve) => {
        pending.push(async () => {
          err.config.headers.Authorization = `Bearer ${auth.accessToken}`;
          resolve(http.request(err.config));
        });
      });
    }

    return Promise.reject(err);
  }
);

export default http;