<script setup lang="ts">
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { isApiMode } from '@/config/runtime'
import { useRealStore } from '@/stores/real.store'
import type { RegisteredWorkspace } from '@/types/agent'

const store = useRealStore()
const router = useRouter()

onMounted(() => store.loadWorkspaces())

function open(ws: RegisteredWorkspace) {
  if (!ws.enabled) return
  router.push(`/real/${ws.id}`)
}
</script>

<template>
  <div class="real-list-page">
    <header class="top-bar">
      <button class="back-btn" type="button" data-testid="back-home-btn" @click="router.push('/')">← 返回首页</button>
      <div class="brand">LightCode · 真实工作区</div>
      <div class="mode-badge" :class="{ api: isApiMode }">{{ isApiMode ? 'API 模式' : 'Mock 演示模式' }}</div>
    </header>

    <div class="page-header">
      <h1>已注册工作区（Phase 1）</h1>
      <p>根路径由服务端静态注册表配置，浏览器仅凭 workspaceId 访问，不接触真实路径</p>
    </div>

    <div v-if="store.error" class="error-banner" data-testid="real-error">{{ store.error }}</div>

    <main class="ws-list">
      <article
        v-for="ws in store.workspaces"
        :key="ws.id"
        data-testid="registered-workspace-row"
        class="ws-row"
        :class="{ disabled: !ws.enabled }"
        @click="open(ws)"
      >
        <div class="ws-info">
          <div class="ws-name">{{ ws.displayName }}</div>
          <div class="ws-id">{{ ws.id }}</div>
          <div class="ws-meta">
            <span v-for="cap in ws.capabilities" :key="cap" class="cap-tag">{{ cap }}</span>
            <span class="policy">策略 {{ ws.policyVersion }}</span>
          </div>
        </div>
        <span class="enabled-badge" :class="ws.enabled ? 'on' : 'off'">{{ ws.enabled ? '已启用' : '已停用' }}</span>
      </article>

      <div v-if="!store.loading && store.workspaces.length === 0" class="empty-hint">
        暂无注册工作区。请在后端配置 backend/workspaces.json（参考 workspaces.example.json）后重启服务。
      </div>
    </main>
  </div>
</template>

<style scoped>
.real-list-page {
  min-height: 100vh;
  padding: 24px 60px;
  background: #f5f0e8;
  color: #2a2a2a;
  font-family: 'Architects Daughter', cursive;
}
.top-bar { display: flex; align-items: center; gap: 16px; margin-bottom: 24px; }
.back-btn {
  background: none; border: none; cursor: pointer;
  font-family: inherit; font-size: 13px; color: #6b7d8e; padding: 0;
}
.back-btn:hover { color: #2a2a2a; }
.brand { font-family: 'Caveat', cursive; font-size: 24px; font-weight: 700; }
.mode-badge {
  margin-left: auto;
  font-family: 'JetBrains Mono', monospace; font-size: 10px;
  padding: 3px 10px; border-radius: 4px;
  color: #c87020; border: 1px solid rgba(200,112,32,.3); background: rgba(212,160,23,.1);
}
.mode-badge.api { color: #2d7a3a; border-color: rgba(45,122,58,.3); background: rgba(45,122,58,.06); }
.page-header h1 { font-family: 'Caveat', cursive; font-size: 30px; margin-bottom: 4px; }
.page-header p { font-size: 13px; color: #6b7d8e; margin-bottom: 20px; }
.error-banner {
  border: 1.5px solid rgba(184,48,48,.35); background: rgba(184,48,48,.05);
  color: #b83030; border-radius: 5px; padding: 10px 14px; margin-bottom: 14px; font-size: 13px;
}
.ws-list { display: flex; flex-direction: column; gap: 12px; max-width: 760px; }
.ws-row {
  display: flex; align-items: center; gap: 14px;
  border: 1.5px solid #d8d0c4; border-radius: 6px;
  padding: 14px 18px; background: rgba(255,255,255,.25); cursor: pointer;
}
.ws-row:hover { border-color: #2a2a2a; }
.ws-row.disabled { opacity: .55; cursor: not-allowed; }
.ws-info { flex: 1; min-width: 0; }
.ws-name { font-size: 16px; font-weight: 600; }
.ws-id { font-family: 'JetBrains Mono', monospace; font-size: 11px; color: #888; margin: 2px 0 6px; }
.ws-meta { display: flex; gap: 6px; align-items: center; flex-wrap: wrap; }
.cap-tag {
  font-family: 'JetBrains Mono', monospace; font-size: 10px;
  padding: 2px 8px; border-radius: 3px;
  color: #6b7d8e; border: 1px solid rgba(107,125,144,.25); background: rgba(107,125,144,.06);
}
.policy { font-family: 'JetBrains Mono', monospace; font-size: 10px; color: #aaa; }
.enabled-badge {
  font-family: 'JetBrains Mono', monospace; font-size: 10px;
  padding: 3px 10px; border-radius: 4px; flex-shrink: 0;
}
.enabled-badge.on { color: #2d7a3a; border: 1px solid rgba(45,122,58,.3); background: rgba(45,122,58,.06); }
.enabled-badge.off { color: #b83030; border: 1px solid rgba(184,48,48,.25); background: rgba(184,48,48,.04); }
.empty-hint {
  border: 1.5px dashed #d8d0c4; border-radius: 6px; padding: 20px;
  color: #6b7d8e; font-size: 13px; text-align: center;
}
</style>
