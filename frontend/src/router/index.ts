import { createRouter, createWebHistory, RouteRecordRaw } from "vue-router";
import { useAuthStore } from "@/stores/auth";

const routes: RouteRecordRaw[] = [
  { path: "/login", name: "Login", component: () => import("@/views/Login.vue") },
  {
    path: "/",
    component: () => import("@/layouts/AppLayout.vue"),
    meta: { requiresAuth: true },
    children: [
      { path: "", name: "Dashboard", component: () => import("@/views/Dashboard.vue") },
      { path: "users", name: "Users", component: () => import("@/views/Users.vue") },
    ],
  },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

router.beforeEach(async (to) => {
  const auth = useAuthStore();
  if (to.meta.requiresAuth && !auth.isAuthenticated) {
    return { name: "Login", query: { redirect: to.fullPath } };
  }
  if (to.name === "Login" && auth.isAuthenticated) {
    return { name: "Dashboard" };
  }
});

export default router;
