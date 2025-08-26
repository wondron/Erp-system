import { defineStore } from "pinia";
import type { UserOut, UserCreateIn } from "@/api/users";
import { createUser, listUsersByLastName } from "@/api/users";

export const useUsersStore = defineStore("users", {
  state: () => ({
    list: [] as UserOut[],
    loading: false,
    error: null as string | null,
    // 记住最近一次搜索的 last_name，便于新增后自动刷新
    lastNameQuery: "" as string,
  }),

  getters: {
    count: (s) => s.list.length,
    fullNames: (s) => s.list.map((u) => `${u.first_name} ${u.last_name}`),
  },

  actions: {
    async searchByLastName(last_name: string) {
      this.loading = true;
      this.error = null;
      this.lastNameQuery = last_name;
      try {
        this.list = await listUsersByLastName(last_name);
      } catch (e: any) {
        this.error = e?.response?.data?.detail ?? e?.message ?? "查询失败";
      } finally {
        this.loading = false;
      }
    },

    async addUser(payload: UserCreateIn) {
      // 前端做点最小校验，配合后端 pydantic 的 min_length 约束
      const fn = payload.first_name?.trim();
      const ln = payload.last_name?.trim();
      if (!fn || !ln) {
        this.error = "姓和名都不能为空";
        return;
      }

      this.loading = true;
      this.error = null;
      try {
        const created = await createUser({ first_name: fn, last_name: ln });
        // 如果当前列表就是查的这个姓氏，新增后刷新列表（保证与后端一致）
        if (this.lastNameQuery && this.lastNameQuery === created.last_name) {
          await this.searchByLastName(this.lastNameQuery);
        } else {
          // 否则不打扰现有结果，也可选择直接插入
          this.list.unshift(created);
        }
      } catch (e: any) {
        const status = e?.response?.status;
        const detail = e?.response?.data?.detail;
        if (status === 409) {
          this.error = detail || "用户已存在";
        } else {
          this.error = detail || e?.message || "新增失败";
        }
      } finally {
        this.loading = false;
      }
    },
  },
});
