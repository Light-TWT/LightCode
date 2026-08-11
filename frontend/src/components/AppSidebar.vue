<script setup lang="ts">
/** 共享主侧边栏：从 WorkspaceView 抽取，设置页与工作区页共用同一套
 *  品牌区 + 导航 + 底部设置入口，避免两套主导航视觉漂移。
 *  设置按钮只发出 openSettings 事件，由父视图决定结果：工作区页打开设置层，
 *  独立设置页维持当前展示。 */
defineProps<{
  /** 当前展开的导航键；null 表示全部收起（工作区页语义） */
  activeNav: 'workspace' | 'files' | 'sessions' | null
  collapsed: boolean
  /** 设置页当前激活设置按钮（设置分类高亮） */
  settingsActive?: boolean
}>()

const emit = defineEmits<{
  (e: 'toggle', key: 'workspace' | 'files' | 'sessions'): void
  (e: 'toggleCollapse'): void
  (e: 'openSettings'): void
}>()
</script>

<template>
  <aside class="sidebar" :class="{ collapsed }" aria-label="侧边导航">
    <div class="brand">
      <span class="brand-mark" aria-hidden="true">L</span>
      <span class="brand-text">LightCode</span>
      <button
        type="button"
        class="brand-arrow"
        :title="collapsed ? '展开侧边栏' : '折叠为图标'"
        data-testid="sidebar-collapse"
        @click="emit('toggleCollapse')"
      >
        <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M15 6l-6 6 6 6"/></svg>
      </button>
    </div>

    <nav class="nav">
      <button
        type="button"
        class="nav-btn"
        :class="{ active: activeNav === 'workspace' }"
        data-testid="nav-btn-workspace"
        @click="emit('toggle', 'workspace')"
      >
        <span class="icon" aria-hidden="true"><svg viewBox="0 0 24 24"><rect x="4" y="4" width="6" height="6" rx="1"/><rect x="14" y="4" width="6" height="6" rx="1"/><rect x="4" y="14" width="6" height="6" rx="1"/><rect x="14" y="14" width="6" height="6" rx="1"/></svg></span>
        <span class="label">工作区</span>
      </button>
      <button
        type="button"
        class="nav-btn"
        :class="{ active: activeNav === 'files' }"
        data-testid="nav-btn-files"
        @click="emit('toggle', 'files')"
      >
        <span class="icon" aria-hidden="true"><svg viewBox="0 0 24 24"><path d="M5 4.5h10l4 4V19a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V5.5a1 1 0 0 1 1-1Z"/><path d="M14 4.5V9h5"/></svg></span>
        <span class="label">文件浏览</span>
      </button>
      <button
        type="button"
        class="nav-btn"
        :class="{ active: activeNav === 'sessions' }"
        data-testid="nav-btn-sessions"
        @click="emit('toggle', 'sessions')"
      >
        <span class="icon" aria-hidden="true"><svg viewBox="0 0 24 24"><path d="M4 5.5A1.5 1.5 0 0 1 5.5 4h13A1.5 1.5 0 0 1 20 5.5v10a1.5 1.5 0 0 1-1.5 1.5H13l-4 3v-3H5.5A1.5 1.5 0 0 1 4 15.5Z"/></svg></span>
        <span class="label">会话</span>
      </button>
    </nav>

    <div class="bottom">
      <button
        type="button"
        class="settings"
        :class="{ active: settingsActive }"
        title="设置"
        data-testid="settings-btn"
        @click="emit('openSettings')"
      >
        <span class="icon" aria-hidden="true"><svg viewBox="0 0 24 24"><circle cx="14" cy="13" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1-1.7 1.7-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.6v.2h-2.4v-.2a1.7 1.7 0 0 0-1-1.6 1.7 1.7 0 0 0-1.9.3l-.1.1L8 17l.1-.1a1.7 1.7 0 0 0 .3-1.9 1.7 1.7 0 0 0-1.6-1H6v-2.4h.8a1.7 1.7 0 0 0 1.6-1 1.7 1.7 0 0 0-.3-1.9L8 8.6l1.7-1.7.1.1a1.7 1.7 0 0 0 1.9.3 1.7 1.7 0 0 0 1-1.6v-.2h2.4v.2a1.7 1.7 0 0 0 1 1.6 1.7 1.7 0 0 0 1.9-.3l.1-.1 1.7 1.7-.1.1a1.7 1.7 0 0 0-.3 1.9 1.7 1.7 0 0 0-1.6 1h.2V14h-.2a1.7 1.7 0 0 0-1.6 1Z"/></svg></span>
        <span class="label">设置</span>
      </button>
    </div>
  </aside>
</template>

<style scoped>
/* ===== 导航栏（从 WorkspaceView 原样迁移，保持 testid 与折叠语义） ===== */
.sidebar {
  width: 232px; flex: 0 0 auto; min-width: 0; min-height: 0;
  overflow-y: auto; overflow-x: hidden;
  display: flex; flex-direction: column;
  background: rgba(255,255,255,.25);
  border-right: 1.5px solid #2a2a2a;
  transition: width .18s ease;
}
.sidebar.collapsed { width: 52px; flex-basis: 52px; }
.brand {
  height: 58px; flex-shrink: 0;
  display: flex; align-items: center; gap: 12px;
  padding: 0 16px;
}
.brand-mark {
  width: 26px; height: 26px; flex-shrink: 0;
  display: grid; place-items: center;
  border-radius: 6px; background: #2a2a2a; color: #f5f0e8;
  font-family: 'Caveat', cursive; font-weight: 700; font-size: 14px;
}
.brand-text { flex: 1; font-family: 'Caveat', cursive; font-size: 22px; font-weight: 700; color: #1a1a1a; white-space: nowrap; }
.brand-arrow {
  width: 26px; height: 26px; flex-shrink: 0;
  display: grid; place-items: center;
  border: 0; border-radius: 6px; background: none; cursor: pointer;
  color: #6b7d8e; transition: transform .18s ease;
}
.brand-arrow:hover { background: rgba(0,0,0,.06); color: #2a2a2a; }
.brand-arrow svg { width: 18px; height: 18px; stroke: currentColor; fill: none; stroke-width: 2.2; stroke-linecap: round; stroke-linejoin: round; }
.sidebar.collapsed .brand-arrow svg { transform: rotate(180deg); }
.nav { padding: 16px 10px; display: flex; flex-direction: column; gap: 6px; }
.nav-btn {
  height: 44px; flex-shrink: 0;
  border: 0; border-radius: 6px; background: transparent;
  color: #6b7d8e; display: flex; align-items: center; gap: 12px;
  padding: 0 12px; cursor: pointer;
  font-family: inherit; font-size: 13px; white-space: nowrap;
}
.nav-btn:hover { background: rgba(0,0,0,.05); color: #2a2a2a; }
.nav-btn.active { background: rgba(212,160,23,.22); color: #c87020; border: 1.5px solid rgba(200,112,32,.4); }
.icon { width: 20px; height: 20px; flex-shrink: 0; display: grid; place-items: center; }
.icon svg { width: 20px; height: 20px; stroke: currentColor; fill: none; stroke-width: 1.8; stroke-linecap: round; stroke-linejoin: round; }
.bottom { margin-top: auto; padding: 12px 10px 16px; flex-shrink: 0; }
.settings {
  height: 44px; width: 100%;
  border: 0; border-radius: 6px; background: transparent;
  color: #6b7d8e; display: flex; align-items: center; gap: 12px;
  padding: 0 12px; cursor: pointer;
  font-family: inherit; font-size: 13px; white-space: nowrap;
}
.settings:hover { background: rgba(0,0,0,.05); color: #2a2a2a; }
.settings.active { background: rgba(212,160,23,.22); color: #c87020; border: 1.5px solid rgba(200,112,32,.4); }
.sidebar.collapsed .brand { padding: 0; justify-content: center; height: 48px; }
.sidebar.collapsed .brand-mark, .sidebar.collapsed .brand-text { display: none; }
.sidebar.collapsed .nav { padding: 12px 0; align-items: center; }
.sidebar.collapsed .nav-btn, .sidebar.collapsed .settings { justify-content: center; padding: 0; width: 40px; height: 40px; margin: 0 auto; }
.sidebar.collapsed .bottom { padding: 10px 0 12px; }
.sidebar.collapsed .label { display: none; }

@media (max-width: 860px) {
  .sidebar { width: 100%; flex-direction: row; flex-wrap: wrap; border-right: 0; border-bottom: 1.5px solid #2a2a2a; }
  .sidebar.collapsed { width: 52px; flex-direction: column; }
}
</style>
