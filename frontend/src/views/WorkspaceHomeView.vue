<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useWorkspaceStore } from '@/stores/workspace.store'

const store = useWorkspaceStore()
const router = useRouter()

const firstWorkspace = computed(
  () => store.workspaces.find((ws) => ws.enabled) ?? store.workspaces[0] ?? null,
)

onMounted(async () => {
  await store.loadWorkspaces()
  if (firstWorkspace.value) {
    await router.replace(`/workspace/${firstWorkspace.value.id}`)
  }
})
</script>

<template>
  <div class="home-page">
    <header class="top-bar">
      <div class="brand">
        <span class="brand-dot" aria-hidden="true" />
        LightCode
      </div>
      <span class="settings-link" title="设置" data-testid="settings-link" @click="router.push('/settings')">⚙ 设置</span>
    </header>

    <div v-if="store.loading" class="loading-hint">正在加载已注册工作区…</div>

    <main v-else-if="firstWorkspace" class="main-area">
      <p class="section-label">已注册工作区</p>
      <div class="workspace-list">
        <button
          v-for="ws in store.workspaces"
          :key="ws.id"
          type="button"
          data-testid="registered-workspace-row"
          class="ws-row"
          :class="{ disabled: !ws.enabled }"
          @click="ws.enabled && router.push(`/workspace/${ws.id}`)"
        >
          <span class="ws-name">{{ ws.displayName }}</span>
          <span class="ws-meta">{{ ws.enabled ? '已启用' : '已停用' }} · 策略 {{ ws.policyVersion }}</span>
        </button>
      </div>
    </main>

    <main v-else class="main-area">
      <div class="empty-card" data-testid="empty-state">
        <h1 class="empty-title">还没有可用的工作区</h1>
        <p class="empty-desc">
          真实工作区根路径只来自服务端静态注册表（<code>LIGHTCODE_WORKSPACES_CONFIG</code>
          或 <code>backend/workspaces.json</code>）。请先在服务端注册工作区并重启后端，
          或前往设置完成模型 Provider 配置。
        </p>
        <div class="empty-actions">
          <button type="button" class="primary-btn" data-testid="goto-settings" @click="router.push('/settings')">去设置</button>
        </div>
      </div>
    </main>

    <p v-if="store.error" class="error-hint" data-testid="home-error">{{ store.error }}</p>

    <footer class="footer-bar">
      <span class="footer-lock" aria-hidden="true">🔒</span>
      <span class="footer-note">会话、审批与凭据仅存储在本机</span>
    </footer>
  </div>
</template>

<style scoped>
.home-page {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  padding: 18px 60px 0;
  background: #f5f0e8;
  color: #2a2a2a;
  font-family: 'Architects Daughter', cursive;
}
* { margin: 0; padding: 0; box-sizing: border-box; }
.top-bar {
  display: flex; align-items: center; justify-content: space-between;
  padding-bottom: 12px; border-bottom: 2px solid #2a2a2a;
  margin-bottom: 18px; flex-shrink: 0;
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
.settings-link {
  font-family: 'JetBrains Mono', monospace; font-size: 12px;
  color: #6b7d8e; cursor: pointer; padding: 4px;
}
.settings-link:hover { color: #2a2a2a; }
.main-area { flex: 1; }
.section-label {
  font-family: 'JetBrains Mono', monospace; font-size: 9px;
  text-transform: uppercase; letter-spacing: 2px; color: #6b7d8e;
  margin-bottom: 8px; padding-bottom: 4px;
  border-bottom: 1.5px dashed #ccc;
}
.workspace-list { display: flex; flex-direction: column; gap: 8px; }
.ws-row {
  display: flex; align-items: center; justify-content: space-between; gap: 14px;
  padding: 14px 16px; border: 1.5px solid #d8d0c4; border-radius: 5px;
  background: rgba(255,255,255,.25); cursor: pointer; text-align: left;
  font-family: inherit; transition: background .12s;
}
.ws-row:hover { background: rgba(255,255,255,.45); }
.ws-row.disabled { opacity: .5; cursor: not-allowed; }
.ws-name { font-family: Caveat, cursive; font-size: 20px; font-weight: 700; color: #1a1a1a; }
.ws-meta { font-family: 'JetBrains Mono', monospace; font-size: 10px; color: #888; }
.empty-card {
  margin-top: 40px; padding: 28px 32px;
  border: 2px dashed #c5b9a8; border-radius: 6px;
  background: rgba(255,255,255,.2); text-align: center;
  transform: rotate(-.15deg);
}
.empty-title { font-family: Caveat, cursive; font-size: 24px; color: #1a1a1a; margin-bottom: 10px; }
.empty-desc { font-size: 13px; color: #6b7d8e; line-height: 1.8; max-width: 560px; margin: 0 auto 16px; }
.empty-desc code { font-family: 'JetBrains Mono', monospace; font-size: 11px; background: rgba(0,0,0,.05); padding: 1px 4px; border-radius: 3px; }
.primary-btn {
  font-family: inherit; font-size: 14px; cursor: pointer;
  border: 2px solid #2a2a2a; border-radius: 4px; padding: 8px 22px;
  background: rgba(212,160,23,.15); color: #2a2a2a; font-weight: 600;
}
.primary-btn:hover { background: rgba(212,160,23,.25); }
.loading-hint, .error-hint { color: #999; font-size: 13px; padding: 20px 0; }
.error-hint { color: #b83030; }
.footer-bar {
  flex-shrink: 0; padding: 12px 0 16px;
  border-top: 1.5px dashed #d8d0c4; margin-top: 14px;
  display: flex; align-items: center; justify-content: center; gap: 5px;
}
.footer-lock { font-size: 10px; color: #ccc; }
.footer-note { font-family: 'JetBrains Mono', monospace; font-size: 9px; color: #bbb; }
</style>
