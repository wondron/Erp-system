<script setup lang="ts">
import { ref, computed, watch } from "vue";
import { useUsersStore } from "@/stores/users";

const store = useUsersStore();

const qLastName = ref("");
const firstName = ref("");
const lastName  = ref("");

const searching = computed(() => store.loading && !!qLastName.value.trim());
const creating  = computed(() => store.loading && !qLastName.value.trim());

const canSearch = computed(() => qLastName.value.trim().length > 0);
const canCreate = computed(() =>
  firstName.value.trim().length >= 1 &&
  lastName.value.trim().length  >= 1 &&
  firstName.value.trim().length <= 64 &&
  lastName.value.trim().length  <= 64
);

function onSearch(){
  if(!canSearch.value){
    store.error = "请输入要查询的姓氏（last_name）";
    return;
  }
  store.searchByLastName(qLastName.value.trim());
}

function onCreate(){
  if(!canCreate.value){
    store.error = "请填写名和姓（1–64 个字符）";
    return;
  }
  store.addUser({ first_name:firstName.value.trim(), last_name:lastName.value.trim() });
  if(!store.error){
    firstName.value = "";
    lastName.value  = "";
  }
}

function clearQuery(){
  qLastName.value = "";
  // 清空结果的体验可自定：这里不主动清空 list，只是重置输入
}

function initials(first:string, last:string){
  const f = (first?.[0] ?? "").toUpperCase();
  const l = (last?.[0] ?? "").toUpperCase();
  return (f + l) || "U";
}

// 输入时清除错误
watch([qLastName, firstName, lastName], () => {
  if(store.error) store.error = "";
});
</script>

<template>
  <div class="users-page">
    <!-- 顶部栏 -->
    <div class="page-head">
      <div>
        <h2 class="page-title">Users / 人物管理</h2>
        <div class="subtle">新增、按姓氏精确查询</div>
      </div>
      <div class="badges">
        <span class="chip chip-primary" role="status" aria-live="polite">
          <svg class="dot" width="8" height="8" viewBox="0 0 8 8" aria-hidden="true"><circle cx="4" cy="4" r="4"/></svg>
          API Ready
        </span>
      </div>
    </div>

    <!-- 主体：两栏布局 -->
    <div class="grid-2">
      <!-- 查询 -->
      <section class="card">
        <div class="card-head">
          <h3>按姓氏查询</h3>
          <span class="subtle"><b>GET</b> /users?last_name=</span>
        </div>

        <form class="row" @submit.prevent="onSearch" aria-labelledby="search-label">
          <label id="search-label" class="visually-hidden">按姓氏查询</label>

          <div class="input-wrap">
            <input
              class="input"
              v-model="qLastName"
              placeholder="输入 姓： 例如 王 / 田中 / Smith"
              aria-label="last_name"
              :aria-invalid="!canSearch && !!qLastName"
            />
            <button type="button" class="btn ghost small" @click="clearQuery" v-if="qLastName">清空</button>
          </div>

          <button class="btn" :class="{ loading: searching }" :disabled="!canSearch || store.loading">
            <span v-if="!searching">查询</span>
            <span v-else>查询中…</span>
          </button>
        </form>

        <p class="meta">
          共 {{ store.count }} 条
          <span v-if="store.loading">（加载中…）</span>
        </p>

        <!-- 结果列表 -->
        <ul class="list" v-if="store.list.length">
          <li v-for="u in store.list" :key="u.id" class="item">
            <div class="user">
              <div class="avatar" :title="u.first_name + ' ' + u.last_name">
                {{ initials(u.first_name, u.last_name) }}
              </div>
              <div class="user-main">
                <div class="name">{{ u.first_name }} {{ u.last_name }}</div>
                <div class="subtle">#{{ u.id }}</div>
              </div>
            </div>
            <!-- <button class="btn danger" @click="store.remove(u.id)">删除</button> -->
          </li>
        </ul>

        <!-- 空 / 提示 -->
        <div v-else class="empty">
          <svg width="20" height="20" viewBox="0 0 24 24" aria-hidden="true"><path d="M19 3H4.99C3.88 3 3.01 3.9 3.01 5L3 19a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V7l-4-4Zm-5 1.5V8h5.5V19h-14V5h8.5Z"/></svg>
          <div class="empty-text">
            还没有结果。输入一个<strong>姓氏</strong>后点击「查询」试试～
          </div>
          <div class="hint subtle">例如：<code>王</code> / <code>田中</code> / <code>Garcia</code></div>
        </div>
      </section>

      <!-- 新增 -->
      <section class="card">
        <div class="card-head">
          <h3>新增用户</h3>
          <span class="subtle"><b>POST</b> /users</span>
        </div>

        <form class="row" @submit.prevent="onCreate" aria-labelledby="create-label">
          <label id="create-label" class="visually-hidden">新增用户</label>

          <input
            class="input"
            v-model="firstName"
            placeholder="first_name（名）"
            aria-label="first_name（名）"
            :aria-invalid="firstName && (firstName.length < 1 || firstName.length > 64)"
          />
          <input
            class="input"
            v-model="lastName"
            placeholder="last_name（姓）"
            aria-label="last_name（姓）"
            :aria-invalid="lastName && (lastName.length < 1 || lastName.length > 64)"
          />

          <button class="btn" :class="{ loading: creating }" :disabled="!canCreate || store.loading">
            <span v-if="!creating">新增</span>
            <span v-else>提交中…</span>
          </button>
        </form>

        <p class="meta subtle">后端校验：长度 1–64；重复返回 <code>409</code>。</p>
      </section>
    </div>

    <!-- 全局错误提示 -->
    <p v-if="store.error" class="error" role="alert">⚠ {{ store.error }}</p>
  </div>
</template>
