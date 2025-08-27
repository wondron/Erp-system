// frontend/src/router/index.ts
import { createRouter, createWebHistory, RouteRecordRaw } from "vue-router";
import { useAuthStore } from "@/stores/auth";

// ---- 给 meta 扩展类型（可选但推荐）----
declare module "vue-router" {
  interface RouteMeta {
    requiresAuth?: boolean; // 需要登录
    public?: boolean;       // 公共页面（不需要登录）
    title?: string;         // 页面标题（可选）
  }
}

const routes: RouteRecordRaw[] = [
  {
    path: "/login",
    name: "Login",
    meta: { public: true, title: "登录" },
    component: () => import("@/views/Login.vue"),
  },
  {
    path: "/logout",
    name: "Logout",
    meta: { public: true, title: "退出登录" },
    // 退出后清理并跳到登录页
    beforeEnter: () => {
      const auth = useAuthStore();
      auth.logout?.(); // 确保在 auth store 里实现 logout()
      return { name: "Login" };
    },
    component: { render: () => null }, // 占位即可
  },
  {
    path: "/",
    component: () => import("@/layouts/AppLayout.vue"),
    meta: { requiresAuth: true },
    children: [
      {
        path: "",
        name: "Dashboard",
        meta: { requiresAuth: true, title: "仪表盘" },
        component: () => import("@/views/Dashboard.vue"),
      },
      {
        path: "users",
        name: "Users",
        meta: { requiresAuth: true, title: "用户管理" },
        component: () => import("@/views/Users.vue"),
      },
    ],
  },
  {
    path: "/:pathMatch(.*)*",
    name: "NotFound",
    meta: { public: true, title: "页面不存在" },
    component: () => import("@/views/NotFound.vue"),
  },
];

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
  scrollBehavior() {
    return { top: 0 };
  },
});

// 全局前置守卫：恢复会话 -> 鉴权 -> 重定向
router.beforeEach(async (to) => {
  const auth = useAuthStore();

  // 1) 确保从本地恢复会话（只做一次；在 store 内部自行防抖）
  // 建议在 auth store 里实现 init(): 从 localStorage 读 token/user 并设置 isAuthenticated
  auth.init()

  const isPublic = !!to.meta.public;
  const isAuthed = !!auth.isAuthenticated;

  // 2) 访问受保护路由且未登录 -> 去登录并带上回跳
  if (!isPublic && !isAuthed) {
    return { name: "Login", query: { redirect: to.fullPath } };
  }

  // 3) 已登录访问 /login -> 回到 redirect 或首页
  if (to.name === "Login" && isAuthed) {
    const redirect = (to.query.redirect as string) || { name: "Dashboard" };
    return redirect;
  }

  // 4) 可选：动态设置标题
  if (to.meta?.title) {
    document.title = String(to.meta.title);
  }
});

export default router;
