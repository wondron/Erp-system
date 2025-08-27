// frontend/src/api/auth.ts
import http from "./http";
import type { LoginResponse } from "@/types/auth"; // ← 只从这里导入，不要在本文件再声明同名类型

export type LoginPayload = { username: string; password: string };

export function loginApi(payload: LoginPayload) {
  // AxiosResponse<LoginResponse>
  return http.post<LoginResponse>("/login/auth", payload);
}

export function refreshApi() {
  // 示例：如果后端没有这个接口，可以先保留声明或删除
  return http.post<{ access_token: string }>("/auth/refresh");
}

export function logoutApi() {
  // 示例：如果后端没有这个接口，可以先保留声明或删除
  return http.post<void>("/auth/logout");
}

export function registerApi(payload: {
  username: string;
  showname: string;
  userrole: string;
  password: string;
}) {
  return http.post<LoginResponse>("/login/create", payload);
}