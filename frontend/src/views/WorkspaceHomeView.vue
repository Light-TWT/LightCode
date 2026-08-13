<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import WorkspacePicker from '@/components/WorkspacePicker.vue'
import { useWorkspaceStore } from '@/stores/workspace.store'
import type { RegisteredWorkspace } from '@/types/agent'

const store = useWorkspaceStore()
const router = useRouter()
const input = ref('')
const sending = ref(false)

const current = computed<RegisteredWorkspace | null>(() =>
  store.workspaces.find((w) => w.id === store.currentWorkspaceId) ?? null,
)
const canSend = computed(() => Boolean(current.value && input.value.trim()))

onMounted(async () => {
  await store.loadWorkspaces()
})

function selectWorkspace(ws: RegisteredWorkspace) {
  store.currentWorkspaceId = ws.id
}

async function submit() {
  const content = input.value.trim()
  if (!current.value || !content || sending.value) return
  sending.value = true
  store.error = null
  try {
    const sessionId = await store.homeCreateAndSend(current.value.id, content)
    if (sessionId) {
      await router.push(`/workspace/${current.value.id}/session/${sessionId}`)
    }
  } finally {
    sending.value = false
  }
}
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

    <main class="main-area">
      <h1 class="home-title" data-testid="home-title">LightCode</h1>
      <p class="home-subtitle">计划、审查与验证都可见的本地编码智能体</p>

      <div class="composer">
        <textarea
          v-model="input"
          class="chat-input"
          data-testid="home-chat-input"
          :placeholder="current ? '输入你想让智能体做的事…' : '先选择工作文件夹'"
          :disabled="!current"
          @keydown.enter.exact.prevent="submit"
        />
        <div class="composer-footer">
          <WorkspacePicker data-testid="home-workspace-picker" @select="selectWorkspace" />
          <button
            type="button"
            class="send-btn"
            data-testid="home-send"
            :disabled="!canSend || sending"
            @click="submit"
          >
            {{ sending ? '提交中…' : '发送' }}
          </button>
        </div>
      </div>

      <p v-if="store.error" class="error-hint" data-testid="home-error">{{ store.error }}</p>
    </main>

    <footer class="footer-bar">
      <span class="footer-lock" aria-hidden="true">🔒</span>
      <span class="footer-note">会话、审批与凭据仅存储在本机</span>
    </footer>
  </div>
</template>

<style scoped>
.home-page {
  min-height: 100vh;
  display: flex; flex-direction: column;
  padding: 18px 60px 0;
  background: #f5f0e8; color: #2a2a2a;
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
.main-area {
  flex: 1; display: flex; flex-direction: column;
  align-items: center; justify-content: center;
  padding: 0 20px 60px;
}
.home-title {
  font-family: Caveat, cursive; font-size: 46px; font-weight: 700;
  color: #1a1a1a; margin-bottom: 10px; transform: rotate(-.6deg);
}
.home-subtitle {
  font-family: 'JetBrains Mono', monospace; font-size: 12px;
  color: #6b7d8e; letter-spacing: .5px; margin-bottom: 30px;
}
.composer {
  width: 100%; max-width: 640px;
  border: 2px solid #d8d0c4; border-radius: 8px;
  background: rgba(255,255,255,.35); padding: 14px;
}
.chat-input {
  width: 100%; min-height: 64px; max-height: 140px; resize: vertical;
  font-family: inherit; font-size: 15px; line-height: 1.6;
  border: none; outline: none; background: transparent; color: #2a2a2a;
}
.chat-input:disabled { opacity: .55; }
.composer-footer {
  display: flex; align-items: center; justify-content: space-between;
  margin-top: 10px; border-top: 1.5px dashed #d8d0c4; padding-top: 10px;
}
.send-btn {
  font-family: inherit; font-size: 14px; cursor: pointer;
  border: 2px solid #2a2a2a; border-radius: 4px; padding: 7px 20px;
  background: rgba(212,160,23,.15); color: #2a2a2a; font-weight: 600;
}
.send-btn:disabled { opacity: .5; cursor: not-allowed; }
.error-hint { margin-top: 16px; color: #b83030; font-size: 13px; }
.footer-bar {
  flex-shrink: 0; padding: 12px 0 16px;
  border-top: 1.5px dashed #d8d0c4; margin-top: 14px;
  display: flex; align-items: center; justify-content: center; gap: 5px;
}
.footer-lock { font-size: 10px; color: #ccc; }
.footer-note { font-family: 'JetBrains Mono', monospace; font-size: 9px; color: #bbb; }
</style>