<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useHomeStore } from '@/stores/home.store'
import type { WorkspaceEntry } from '@/types/agent'

const store = useHomeStore()
const router = useRouter()

onMounted(() => store.load())

function openWorkspace(entry: WorkspaceEntry) {
  router.push(`/workspace/${entry.id}`)
}

function onOverlayKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape') store.closeDrawer()
}

const drawerVisible = computed(() => store.drawerOpen)
</script>

<template>
  <div class="home-page">
    <header class="top-bar">
      <div class="brand">
        <span class="brand-dot" aria-hidden="true" />
        LightCode
      </div>
      <div class="top-right">
        <div class="runtime-badge">Local runtime ready</div>
        <button class="real-entry-btn" type="button" data-testid="real-workspaces-link" @click="router.push('/real')">真实工作区</button>
        <span class="settings-icon" title="设置" data-testid="settings-link" @click="router.push('/settings')">⚙</span>
      </div>
    </header>

    <div class="page-header">
      <h1 class="page-title">继续你的工作</h1>
      <p class="page-subtitle">选择一个项目，或打开新的本地目录</p>
    </div>

    <main class="main-area">
      <p class="section-label">最近项目</p>
      <div class="project-scroll">
        <div class="project-list">
          <article
            v-for="(project, index) in store.recentWorkspaces"
            :key="project.id"
            :data-testid="'project-row'"
            class="project-row"
            :class="[index === 0 && project.status === 'waiting' ? 'primary' : 'secondary', { fail: project.status === 'fail' }]"
            @click="openWorkspace(project)"
          >
            <div class="project-info">
              <div class="project-name">{{ project.name }}</div>
              <div class="project-path">{{ project.rootPath }}</div>
              <div class="project-meta">
                <span v-for="tag in project.tags" :key="tag" class="tech-tag">{{ tag }}</span>
                <span class="project-task">{{ project.lastTask }}</span>
              </div>
            </div>
            <div class="status-badge" :class="`status-${project.status}`">{{ statusLabel(project.status) }}</div>
            <time class="project-time">{{ project.timeAgo }}</time>
            <button class="project-action" type="button" @click.stop="openWorkspace(project)">打开工作区</button>
          </article>
        </div>

        <div class="view-all-link">
          <button data-testid="view-all-btn" class="view-all-btn" type="button" @click="store.openDrawer()">查看全部 {{ store.allWorkspaces.length }} 个已注册工作区</button>
        </div>

        <div class="open-local-block">
          <div class="open-local-btn">
            <span class="local-icon" aria-hidden="true">📂</span>
            <span class="local-label">打开本地项目</span>
            <span class="local-hint">桌面版将支持系统文件夹选择</span>
          </div>
        </div>
      </div>
    </main>

    <footer class="footer-bar">
      <span class="footer-lock" aria-hidden="true">🔒</span>
      <span class="footer-note-text">会话和审批记录仅存储在本机</span>
    </footer>

    <div v-if="drawerVisible" data-testid="drawer-overlay" class="drawer-overlay" :class="{ open: drawerVisible }" tabindex="-1" @click="store.closeDrawer()" @keydown="onOverlayKeydown" />
    <aside v-if="drawerVisible" data-testid="workspace-drawer" class="drawer" :class="{ open: drawerVisible }" aria-label="全部工作区">
      <div class="drawer-header">
        <div class="drawer-title-row">
          <h2 class="drawer-title">全部工作区</h2>
          <button class="drawer-close" type="button" @click="store.closeDrawer()">✕</button>
        </div>
        <input data-testid="drawer-search" v-model="store.searchQuery" class="drawer-search" type="text" placeholder="搜索工作区名称或路径…">
      </div>
      <div class="drawer-list">
        <div v-for="entry in store.filteredWorkspaces" :key="entry.id" data-testid="drawer-item" class="drawer-item" @click="openWorkspace(entry); store.closeDrawer()">
          <span class="drawer-item-icon" aria-hidden="true">📁</span>
          <span class="drawer-item-name">{{ entry.name }}</span>
          <span class="drawer-item-path">{{ entry.rootPath }}</span>
          <span class="drawer-item-arrow" aria-hidden="true">→</span>
        </div>
        <div v-if="store.filteredWorkspaces.length === 0" class="drawer-empty">没有匹配的工作区</div>
      </div>
      <div class="drawer-footer">共 {{ store.allWorkspaces.length }} 个已注册工作区 · 本地存储</div>
    </aside>
  </div>
</template>

<script lang="ts">
function statusLabel(status: string): string {
  switch (status) {
    case 'waiting': return '等待审批'
    case 'pass': return '测试通过'
    case 'fail': return '上次运行失败'
    case 'idle': return '空闲'
    default: return status
  }
}
</script>

<style scoped>
.home-page {
  min-height: 100vh; max-height: 100vh; overflow: hidden;
  display: flex; flex-direction: column;
  background: #f5f0e8; color: #2a2a2a;
  font-family: 'Architects Daughter', cursive;
  padding: 18px 150px 0;
}
* { margin: 0; padding: 0; box-sizing: border-box; }
.top-bar {
  display: flex; align-items: center; justify-content: space-between;
  padding-bottom: 12px; border-bottom: 2px solid #2a2a2a;
  margin-bottom: 14px; flex-shrink: 0;
}
.brand {
  font-family: Caveat, cursive; font-size: 26px; font-weight: 700;
  color: #1a1a1a; letter-spacing: .5px;
  transform: rotate(-.4deg); display: flex; align-items: center; gap: 8px;
}
.brand-dot {
  width: 8px; height: 8px; border-radius: 50%;
  background: #2d7a3a; border: 1.5px solid #2d7a3a;
  flex-shrink: 0; position: relative; top: -1px;
}
.top-right { display: flex; align-items: center; gap: 12px; }
.runtime-badge {
  font-family: 'JetBrains Mono', monospace; font-size: 10px;
  color: #2d7a3a; border: 1.5px solid #2d7a3a;
  border-radius: 4px; padding: 3px 8px;
  background: rgba(45,122,58,.06);
  display: flex; align-items: center; gap: 5px; transform: rotate(.2deg);
}
.runtime-badge::before {
  content: ''; width: 5px; height: 5px; border-radius: 50%;
  background: #2d7a3a;
}
.real-entry-btn {
  font-family: 'Architects Daughter', cursive; font-size: 12px;
  color: #c87020; border: 1.5px solid #c87020; border-radius: 4px;
  padding: 3px 10px; background: rgba(212,160,23,.08); cursor: pointer;
}
.real-entry-btn:hover { background: rgba(212,160,23,.16); }
.settings-icon {
  font-family: 'JetBrains Mono', monospace; font-size: 16px;
  color: #999; cursor: pointer; padding: 4px; line-height: 1;
  transform: rotate(.3deg);
}
.settings-icon:hover { color: #2a2a2a; }
.page-header { margin-bottom: 12px; flex-shrink: 0; }
.page-title {
  font-family: Caveat, cursive; font-size: 28px; font-weight: 700;
  color: #1a1a1a; transform: rotate(-.3deg); margin-bottom: 2px;
}
.page-subtitle {
  font-family: 'Patrick Hand', cursive; font-size: 13px;
  color: #6b7d8e; transform: rotate(-.1deg);
}
.main-area {
  flex: 1; min-height: 0; display: flex; flex-direction: column; overflow: hidden;
}
.section-label {
  font-family: 'JetBrains Mono', monospace; font-size: 9px;
  text-transform: uppercase; letter-spacing: 2px; color: #6b7d8e;
  margin-bottom: 6px; padding-bottom: 4px;
  border-bottom: 1.5px dashed #ccc; flex-shrink: 0;
}
.project-scroll {
  flex: 1; min-height: 0; overflow-y: auto; padding-right: 4px;
}
.project-scroll::-webkit-scrollbar { width: 5px; }
.project-scroll::-webkit-scrollbar-track {
  background: rgba(0,0,0,.03); border-radius: 4px;
}
.project-scroll::-webkit-scrollbar-thumb {
  background: #c5b9a8; border-radius: 4px; border: 1px solid rgba(0,0,0,.06);
}
.project-scroll::-webkit-scrollbar-thumb:hover { background: #a99e8d; }
.project-scroll { scrollbar-width: thin; scrollbar-color: #c5b9a8 rgba(0,0,0,.03); }
.project-list { display: flex; flex-direction: column; gap: 8px; }
.project-row {
  display: flex; align-items: center; gap: 14px;
  padding: 14px 16px; border-radius: 5px;
  cursor: pointer; transition: background .12s;
}
.project-row:nth-child(2) { transform: rotate(.1deg); }
.project-row:nth-child(3) { transform: rotate(-.08deg); }
.project-row:nth-child(4) { transform: rotate(.06deg); }
.project-row:nth-child(5) { transform: rotate(-.1deg); }
.project-row:hover { background: rgba(255,255,255,.35); }
.project-row.primary {
  border: 2.5px solid #c87020;
  background: rgba(212,160,23,.06);
  padding: 16px 18px;
}
.project-row.primary .project-name { font-size: 23px; }
.project-row.secondary {
  border: 1.5px solid #d8d0c4;
  background: rgba(255,255,255,.15);
}
.project-row.secondary .project-name { color: #444; }
.project-row.secondary .project-path { color: #aaa; }
.project-row.secondary .project-action {
  border-color: #d8d0c4; color: #999;
}
.project-row.secondary .project-action:hover {
  border-color: #2a2a2a; color: #2a2a2a; background: rgba(0,0,0,.04);
}
.project-row.secondary.fail .project-action {
  border-color: #e0c0c0; color: #c08080;
}
.project-info {
  flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 4px;
}
.project-name {
  font-family: Caveat, cursive; font-size: 20px; font-weight: 700;
  color: #1a1a1a; white-space: nowrap;
  overflow: hidden; text-overflow: ellipsis;
}
.project-path {
  font-family: 'JetBrains Mono', monospace; font-size: 11px; color: #888;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.project-meta { display: flex; align-items: center; gap: 7px; flex-wrap: wrap; }
.tech-tag {
  font-family: 'JetBrains Mono', monospace; font-size: 10px;
  padding: 2px 7px; border: 1px solid #ccc; border-radius: 3px;
  color: #6b7d8e; background: rgba(255,255,255,.4); white-space: nowrap;
}
.project-task {
  font-family: 'Architects Daughter', cursive; font-size: 12px; color: #555;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.status-badge {
  font-family: 'JetBrains Mono', monospace; font-size: 10px;
  padding: 3px 8px; border-radius: 3px; white-space: nowrap;
  display: flex; align-items: center; gap: 4px; flex-shrink: 0;
}
.status-badge::before {
  content: ''; width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0;
}
.status-waiting { color: #c87020; background: rgba(212,160,23,.1); border: 1px solid rgba(200,112,32,.3); }
.status-waiting::before { background: #c87020; }
.status-pass { color: #2d7a3a; background: rgba(45,122,58,.08); border: 1px solid rgba(45,122,58,.25); }
.status-pass::before { background: #2d7a3a; }
.status-fail { color: #b83030; background: rgba(184,48,48,.06); border: 1px solid rgba(184,48,48,.2); }
.status-fail::before { background: #b83030; }
.status-idle { color: #6b7d8e; background: rgba(107,125,142,.06); border: 1px solid rgba(107,125,142,.2); }
.status-idle::before { background: #bbb; }
.project-time {
  font-family: 'JetBrains Mono', monospace; font-size: 10px; color: #aaa;
  white-space: nowrap; flex-shrink: 0;
}
.project-action {
  font-family: Caveat, cursive; font-size: 16px; font-weight: 600;
  padding: 7px 16px; border: 2px solid #2a2a2a; border-radius: 4px;
  background: none; color: #2a2a2a; cursor: pointer;
  white-space: nowrap; flex-shrink: 0; transform: rotate(-.3deg);
  transition: background .12s, border-color .12s, color .12s;
}
.project-action:hover { background: rgba(0,0,0,.04); }
.project-row.primary .project-action {
  border-color: #c87020; color: #c87020;
  background: rgba(212,160,23,.1); font-weight: 700;
}
.view-all-link {
  flex-shrink: 0; padding: 10px 0 0; text-align: center;
}
.view-all-btn {
  font-family: 'Patrick Hand', cursive; font-size: 14px;
  color: #6b7d8e; cursor: pointer; border: none; background: none;
  padding: 4px 8px; transition: color .15s;
  text-decoration: none; display: inline-block;
}
.view-all-btn:hover { color: #2a2a2a; }
.view-all-btn::after { content: ' →'; }
.open-local-block {
  flex-shrink: 0; padding: 14px 0 0; text-align: center;
}
.open-local-btn {
  display: inline-flex; align-items: center; gap: 8px;
  border: 1.5px dashed #bbb; border-radius: 5px;
  padding: 8px 18px; transform: rotate(-.15deg);
  background: none; cursor: default;
}
.local-icon { font-size: 16px; opacity: .5; }
.local-label {
  font-family: Caveat, cursive; font-size: 17px; font-weight: 600; color: #888;
}
.local-hint {
  font-family: 'JetBrains Mono', monospace; font-size: 10px; color: #bbb;
  margin-left: 4px;
}
.footer-bar {
  flex-shrink: 0; padding: 10px 0 14px;
  border-top: 1.5px dashed #d8d0c4; margin-top: 10px;
  display: flex; align-items: center; justify-content: center; gap: 5px;
}
.footer-lock { font-size: 10px; color: #ccc; }
.footer-note-text {
  font-family: 'JetBrains Mono', monospace; font-size: 9px; color: #bbb;
}
.drawer-overlay {
  position: fixed; inset: 0; background: rgba(0,0,0,.18);
  z-index: 100; opacity: 0; pointer-events: none;
  transition: opacity .25s ease;
}
.drawer-overlay.open { opacity: 1; pointer-events: auto; }
.drawer {
  position: fixed; top: 0; right: 0; bottom: 0;
  width: 380px; max-width: 90vw;
  background: #f5f0e8;
  border-left: 2.5px solid #2a2a2a;
  z-index: 101;
  transform: translateX(100%);
  transition: transform .3s cubic-bezier(.22,1,.36,1);
  display: flex; flex-direction: column;
  box-shadow: -4px 0 20px rgba(0,0,0,.08);
}
.drawer.open { transform: translateX(0); }
.drawer-header {
  display: block;
  padding: 18px 20px 12px;
  border-bottom: 1.5px solid #2a2a2a;
  flex-shrink: 0;
}
.drawer-title-row {
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: 10px;
}
.drawer-title {
  font-family: Caveat, cursive; font-size: 22px; font-weight: 700;
  color: #1a1a1a; transform: rotate(-.2deg);
}
.drawer-close {
  font-family: 'JetBrains Mono', monospace; font-size: 18px;
  color: #999; cursor: pointer; padding: 2px 6px; line-height: 1;
  border: 1.5px solid #d8d0c4; border-radius: 4px; background: none;
  transition: color .12s, border-color .12s;
}
.drawer-close:hover { color: #2a2a2a; border-color: #2a2a2a; }
.drawer-search {
  width: 100%; padding: 7px 10px;
  font-family: 'JetBrains Mono', monospace; font-size: 11px;
  color: #2a2a2a; background: rgba(255,255,255,.5);
  border: 1.5px solid #d8d0c4; border-radius: 4px;
  outline: none; transition: border-color .15s;
}
.drawer-search:focus { border-color: #6b7d8e; }
.drawer-search::placeholder { color: #bbb; }
.drawer-list {
  flex: 1; min-height: 0; overflow-y: auto; padding: 10px 16px;
}
.drawer-list::-webkit-scrollbar { width: 5px; }
.drawer-list::-webkit-scrollbar-track { background: rgba(0,0,0,.03); border-radius: 4px; }
.drawer-list::-webkit-scrollbar-thumb { background: #c5b9a8; border-radius: 4px; }
.drawer-list { scrollbar-width: thin; scrollbar-color: #c5b9a8 rgba(0,0,0,.03); }
.drawer-item {
  display: flex; align-items: center; gap: 8px;
  padding: 7px 10px; border: 1.5px dashed #d8d0c4; border-radius: 4px;
  cursor: pointer; transition: background .12s, border-color .12s;
  margin-bottom: 4px; transform: rotate(-.08deg);
}
.drawer-item:nth-child(even) { transform: rotate(.06deg); }
.drawer-item:hover { background: rgba(0,0,0,.025); border-color: #bbb; }
.drawer-item-icon { font-size: 12px; opacity: .5; flex-shrink: 0; }
.drawer-item-name {
  font-family: Caveat, cursive; font-size: 15px; font-weight: 600;
  color: #1a1a1a; flex-shrink: 0;
}
.drawer-item-path {
  font-family: 'JetBrains Mono', monospace; font-size: 9px; color: #aaa;
  flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.drawer-item-arrow {
  font-family: 'JetBrains Mono', monospace; font-size: 11px;
  color: #ccc; flex-shrink: 0; transition: color .12s;
}
.drawer-item:hover .drawer-item-arrow { color: #6b7d8e; }
.drawer-empty {
  font-family: 'Patrick Hand', cursive; font-size: 14px;
  color: #bbb; text-align: center; padding: 30px 0;
}
.drawer-footer {
  flex-shrink: 0; padding: 10px 20px;
  border-top: 1.5px dashed #d8d0c4;
  font-family: 'JetBrains Mono', monospace; font-size: 9px; color: #bbb;
  text-align: center;
}
@media (max-width: 760px) {
  .home-page { padding: 12px 16px 0; }
  .runtime-badge { display: none; }
  .project-row { flex-wrap: wrap; gap: 10px; }
  .project-action { width: 100%; text-align: center; }
  .drawer { width: 100vw; max-width: 100vw; }
}
</style>
