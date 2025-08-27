// src/types/auth.ts
export type LegacyLoginResponse = {
    username: string;
    showname: string;
    userrole: string;
    id?: number;
  };
  
  export type JwtLoginResponse = {
    access_token: string;
    refresh_token?: string;
    user?: {
      id?: number;
      username: string;
      showname: string;
      userrole: string;
    };
  };
  
  export type LoginResponse = LegacyLoginResponse | JwtLoginResponse;
  
  // 类型守卫（帮助 TS 缩小类型）
  export function isLegacy(resp: LoginResponse): resp is LegacyLoginResponse {
    return (resp as any).username !== undefined && (resp as any).userrole !== undefined;
  }
  
  export function isJwt(resp: LoginResponse): resp is JwtLoginResponse {
    return (resp as any).access_token !== undefined;
  }
  