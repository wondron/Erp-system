// src/api/auth.ts
import http from "./http";

export interface LoginPayload {
  username: string;
  password: string;
}

export interface LoginResponse {
  access_token: string;
  refresh_token?: string; // 如果你用 cookie，也可不返回
  token_type: "bearer";
  user: { id: number; name: string; role: string };
}

export const loginApi = (data: LoginPayload) =>
  http.post<LoginResponse>("/auth/login", data);

export const refreshApi = () =>
  http.post<{ access_token: string; token_type: "bearer" }>(
    "/auth/refresh",
    {}
  );

export const logoutApi = () => http.post("/auth/logout", {});
