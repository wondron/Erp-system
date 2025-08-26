<template>
    <div class="app-wrap">
      <header class="app-header">
        <div class="app-brand">
          <img class="logo" src="/vite.svg" alt="logo" />
          <span class="brand">ERP Demo</span>
        </div>
        <nav class="app-nav">
          <a href="/" class="nav-link active">Users</a>
        </nav>
      </header>
  
      <main class="app-main">
        <div class="app-card">
          <router-view />
        </div>
      </main>
  
      <footer class="app-foot">
        <span>© {{ new Date().getFullYear() }} Your Company</span>
      </footer>
    </div>
  </template>
  
  <style scoped>
  .app-wrap{
    min-height:100svh;
    display:grid;
    grid-template-rows:auto 1fr auto;
    background: radial-gradient(1200px 600px at 10% -10%, #eef2ff 0%, transparent 60%),
                radial-gradient(1000px 500px at 110% 10%, #e0f2fe 0%, transparent 55%),
                linear-gradient(180deg, #fafafa, #f5f7fb 55%, #eef2ff);
  }
  .app-header{
    position:sticky; top:0; z-index:10;
    backdrop-filter:saturate(120%) blur(6px);
    background:color-mix(in oklab, #ffffff 80%, transparent);
    border-bottom:1px solid #eef2ff;
    display:flex; align-items:center; justify-content:space-between;
    padding:14px 20px;
  }
  .app-brand{display:flex; align-items:center; gap:10px}
  .logo{width:24px;height:24px}
  .brand{font-weight:800; letter-spacing:.2px}
  .app-nav{display:flex; gap:10px}
  .nav-link{
    padding:6px 10px;border-radius:10px;text-decoration:none;
    color:#4f46e5;border:1px solid #c7d2fe;background:#eef2ff;
    font-weight:600; font-size:12px;
  }
  .nav-link.active{box-shadow:0 6px 16px rgba(79,70,229,.18)}
  .app-main{display:flex; justify-content:center; padding:28px 16px}
  .app-card{
    width:min(100%, 1000px);
    background:#fff; border-radius:20px; border:1px solid #e9eef7;
    box-shadow:0 12px 32px rgba(0,0,0,.07);
    padding:26px;
  }
  .app-foot{
    color:#6b7280; font-size:12px; text-align:center; padding:16px 10px;
  }
  @media (prefers-color-scheme: dark){
    .app-wrap{background:linear-gradient(180deg,#0b1020,#0e1326 60%,#0b1020)}
    .app-header{background:#0e132690; border-color:#1f2937}
    .app-card{background:#0f152b; border-color:#1f2a44}
    .brand,.app-foot{color:#cbd5e1}
    .nav-link{background:#1e293b; color:#c7d2fe; border-color:#334155}
  }
  </style>
  