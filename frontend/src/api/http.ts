// src/api/http.ts
import axios, {
  AxiosError,
  AxiosHeaders,
  InternalAxiosRequestConfig,
} from "axios";
import { useAuthStore } from "@/stores/auth";

const http = axios.create({
  baseURL: import.meta.env.VITE_API_BASE ?? "http://127.0.0.1:8000",
  timeout: 15000,
});

// —— 请求拦截器：确保 headers 为 AxiosHeaders，并附加认证头 ——
http.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  // 1) 统一 headers 类型为 AxiosHeaders
  if (!config.headers) {
    config.headers = new AxiosHeaders();
  } else if (!(config.headers as any).set) {
    // 兼容：如果是普通对象，包一层
    config.headers = new AxiosHeaders(config.headers);
  }

  const headers = config.headers as AxiosHeaders;

  // 2) 附加认证（从 Pinia 读取）
  const auth = useAuthStore();
  auth.init?.(); // 恢复一次本地会话（内部有防抖）

  if (auth.accessToken) {
    headers.set("Authorization", `Bearer ${auth.accessToken}`);
  }

  // 3) JSON 请求常用 Content-Type
  if (
    !headers.has("Content-Type") &&
    config.method &&
    ["post", "put", "patch"].includes(config.method.toLowerCase())
  ) {
    headers.set("Content-Type", "application/json");
  }

  return config;
});

// —— 响应拦截器（可选：处理 401 等） ——
http.interceptors.response.use(
  (resp) => resp,
  async (error: AxiosError) => {
    // 例：401 统一登出
    if (error.response?.status === 401) {
      try {
        const auth = useAuthStore();
        await auth.logout();
      } catch {}
    }
    return Promise.reject(error);
  }
);

export default http;
