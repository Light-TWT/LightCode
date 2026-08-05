<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useWorkspaceStore } from '@/stores/workspace.store'
import { providerService } from '@/services/provider.service'
import type {
  ApprovalDecision,
  ChatMessage,
  ProviderStatus,
  ProviderSettingsResponse,
  RegisteredFileEntry,
} from '@/types/agent'

const route = useRoute()
const router = useRouter()
const store = useWorkspaceStore()

const workspaceId = computed(() => route.params.workspaceId as string)
const sessionId = computed(() => (route.params.sessionId as string | undefined) ?? null)

const draft = ref('')
const newSessionTitle = ref('')
const searchInput = ref('')

/** Provider 设置安全视图（getSettings：无 key、无完整 baseUrl） */
const provider = ref<ProviderSettingsResponse | null>(null)
const providerReady = computed(() => provider.value?.status === 'ready')
const providerStatusLabel = computed(() => {
  switch (provider.value?.status) {
    case 'ready': return '模型就绪'
    case 'unconfigured': return '未配置'
    case 'degraded': return '降级'
    case 'disabled': return '未启用'
    default: return '未知'
  }
})
const providerBadgeClass = computed(() => {
  const status: ProviderStatus | undefined = provider.value?.status
  if (status === 'ready') return 'badge-ready'
  if (status === 'degraded') return 'badge-degraded'
  if (status === 'unconfigured') return 'badge-unconfigured'
  return 'badge-disabled'
})

async function loadProviderSettings() {
  try {
    provider.value = await providerService.getSettings()
  } catch {
    provider.value = null
  }
}

const workspace = computed(
  () => store.workspaces.find((ws) => ws.id === workspaceId.value) ?? null,
)

/** 面包屑：根目录 + 逐级目录（来自令牌导航栈） */
const breadcrumbs = computed(() => {
  const crumbs = [{ label: '根目录' }]
  for (const seg of store.pathStack) {
    crumbs.push({ label: seg.name })
  }
  return crumbs
})

function onEntryClick(entry: RegisteredFileEntry) {
  if (entry.kind === 'dir') {
    store.enterDirectory(entry)
  } else if (entry.kind === 'file' && entry.token) {
    store.openFileByToken(entry.token)
  }
  // link / secret：受安全策略保护，不可读取
}

function kindIcon(kind: RegisteredFileEntry['kind']): string {
  switch (kind) {
    case 'dir': return '📁'
    case 'link': return '🔗'
    case 'secret': return '🔒'
    default: return '·'
  }
}

async function runSearch() {
  await store.runSearch(searchInput.value.trim())
}

/** 待审批任务存在时（edit_summary 且 task 未完成），底部显示审查/拒绝而非仅输入框 */
const pendingTask = computed(
  () =>
    store.task?.state === 'awaiting_approval' &&
    store.task.changeSet?.status === 'active',
)

/** 稳定错误文案白名单（与后端 _FAILURE_TEXT 一致）。error 消息只渲染白名单内
 *  的固定文案，绝不渲染服务端自由 message（M-03：防止敏感内容进入界面）。 */
const KNOWN_ERROR_TEXTS = new Set([
  '模型能力未启用，请在设置中配置 Provider。',
  '模型 Provider 尚未配置，请在设置中完成配置。',
  '模型 Provider 响应超时，请稍后重试。',
  '模型 Provider 触发限流，请稍后重试。',
  '无法连接到模型 Provider，请检查配置。',
  '模型响应无法解析，请重试。',
  '本次请求超出模型资源预算。',
  '模型提出的修改不合法，已拒绝。',
  '已有任务正在运行，请稍后再试。',
  '模型输出不符合协议，请重试。',
  '目标文件已变更，请重新发起任务。',
  '模型任务处理失败，请重试。',
])
const ERROR_FALLBACK_TEXT = '模型处理失败：请稍后重试，或检查 Provider 配置。'
function errorDisplayText(message: ChatMessage): string {
  return KNOWN_ERROR_TEXTS.has(message.content) ? message.content : ERROR_FALLBACK_TEXT
}

/** 关联任务的最新状态（用于 edit_summary 卡片的审批按钮可用性） */
function taskStateFor(taskId: string): string | null {
  if (store.task?.id !== taskId) return null
  return store.task.state
}

/** 审批走 store.submitDecision：先确保 store.task 与卡片任务一致，再提交决定 */
async function decideOnTask(taskId: string, decision: ApprovalDecision) {
  if (store.task?.id !== taskId) {
    await store.loadTask(taskId)
  }
  await store.submitDecision(decision)
}

function viewDiff(taskId: string) {
  router.push(`/workspace/${workspaceId.value}/task/${taskId}`)
}

async function send() {
  const text = draft.value.trim()
  if (!text || !providerReady.value || store.sending) return
  draft.value = ''
  await store.submitChatMessage(text)
}

function openSession(id: string) {
  router.push(`/workspace/${workspaceId.value}/session/${id}`)
}

async function createSession() {
  const title = newSessionTitle.value.trim() || '新会话'
  const session = await store.createChatSession(workspaceId.value, title)
  newSessionTitle.value = ''
  if (session) {
    router.push(`/workspace/${workspaceId.value}/session/${session.id}`)
  }
}

onMounted(async () => {
  await store.openWorkspace(workspaceId.value)
  await store.loadChatSessions(workspaceId.value)
  if (sessionId.value) {
    await store.openChatSession(sessionId.value, workspaceId.value)
  }
  await loadProviderSettings()
})

watch(
  () => route.params.workspaceId,
  async (id) => {
    if (id && id !== store.currentWorkspaceId) {
      await store.openWorkspace(id as string)
      await store.loadChatSessions(id as string)
      await loadProviderSettings()
    }
  },
)

watch(
  () => route.params.sessionId,
  async (sid) => {
    if (sid && sid !== store.currentSessionId) {
      await store.openChatSession(sid as string, workspaceId.value)
    }
  },
)

onUnmounted(() => store.cleanup())
</script>

<template>
  <div class="ws-page">
    <header class="top-bar">
      <button class="back-btn" type="button" data-testid="back-home-btn" @click="router.push('/')">← 首页</button>
      <div class="brand">LightCode</div>
      <span class="ws-title" data-testid="workspace-title">{{ workspace?.displayName ?? workspaceId }}</span>
      <span
        class="provider-badge"
        :class="providerBadgeClass"
        data-testid="provider-status"
      >Provider {{ providerStatusLabel }}</span>
      <span class="settings-link" title="设置" data-testid="settings-btn" @click="router.push('/settings')">⚙ 设置</span>
    </header>

    <div v-if="store.error" class="error-banner" data-testid="ws-error">{{ store.error }}</div>

    <div class="columns">
      <aside class="sidebar">
        <section class="panel" aria-label="工作区切换">
          <p class="panel-kicker">工作区</p>
          <div class="ws-switch">
            <button
              v-for="ws in store.workspaces"
              :key="ws.id"
              type="button"
              class="ws-switch-row"
              :class="{ active: ws.id === workspaceId, disabled: !ws.enabled }"
              data-testid="ws-switch-row"
              @click="ws.enabled && router.push(`/workspace/${ws.id}`)"
            >
              {{ ws.displayName }}
              <span v-if="!ws.enabled" class="off-tag">已停用</span>
            </button>
            <p v-if="store.workspaces.length === 0" class="empty-hint">暂无工作区</p>
          </div>
        </section>

        <section class="panel files-panel" aria-label="文件浏览">
          <p class="panel-kicker">文件浏览（只读 · 服务端守卫）</p>
          <nav class="breadcrumbs" aria-label="路径">
            <button
              v-for="(crumb, idx) in breadcrumbs"
              :key="idx"
              type="button"
              class="crumb"
              :disabled="idx === breadcrumbs.length - 1"
              @click="store.goUp()"
            >{{ crumb.label }}</button>
          </nav>
          <div class="entry-list">
            <button
              v-for="entry in store.entries"
              :key="entry.token || entry.name"
              type="button"
              class="entry-row"
              :class="{ blocked: entry.kind === 'link' || entry.kind === 'secret' }"
              :disabled="entry.kind === 'link' || entry.kind === 'secret'"
              data-testid="file-entry"
              @click="onEntryClick(entry)"
            >
              <span class="entry-icon" aria-hidden="true">{{ kindIcon(entry.kind) }}</span>
              <span class="entry-name">{{ entry.name }}</span>
              <span v-if="entry.kind === 'secret'" class="entry-tag">禁止读取</span>
              <span v-else-if="entry.kind === 'link'" class="entry-tag">禁止跟随</span>
            </button>
            <p v-if="!store.loading && store.entries.length === 0" class="empty-hint">目录为空</p>
          </div>
          <form class="search-row" @submit.prevent="runSearch">
            <input
              v-model="searchInput"
              data-testid="search-input"
              class="text-input"
              type="text"
              placeholder="搜索文件内容…"
            >
            <button class="mini-btn" type="submit">搜</button>
          </form>
          <div v-if="store.searchQuery" class="search-results">
            <button
              v-for="hit in store.searchHits"
              :key="hit.token || hit.name"
              type="button"
              class="hit-row"
              data-testid="search-hit"
              @click="store.openFileByToken(hit.token)"
            >{{ hit.name }}</button>
            <p v-if="store.searchHits.length === 0" class="empty-hint">无匹配结果</p>
          </div>
        </section>

        <section v-if="store.filePreview" class="panel" aria-label="文件预览">
          <p class="panel-kicker">文件预览</p>
          <pre class="code-surface" data-testid="preview-content">{{ store.filePreview.content }}</pre>
        </section>

        <section class="panel sessions-panel" aria-label="会话列表">
          <p class="panel-kicker">会话</p>
          <form class="session-new" @submit.prevent="createSession">
            <input
              v-model="newSessionTitle"
              data-testid="new-session-input"
              class="text-input"
              type="text"
              placeholder="新会话标题…"
            >
            <button class="mini-btn" type="submit" data-testid="new-session-btn" :disabled="store.submitting">
              {{ store.submitting ? '创建中…' : '＋新建' }}
            </button>
          </form>
          <div class="session-list">
            <button
              v-for="s in store.chatSessions"
              :key="s.id"
              type="button"
              class="session-row"
              :class="{ active: s.id === store.currentSessionId }"
              data-testid="session-row"
              @click="openSession(s.id)"
            >
              <span class="session-title">{{ s.title }}</span>
              <span class="session-time">{{ s.updatedAt }}</span>
            </button>
            <p v-if="store.chatSessions.length === 0" class="empty-hint">暂无会话，新建一个开始对话</p>
          </div>
        </section>
      </aside>

      <main class="chat-panel" aria-label="聊天">
        <div class="message-flow">
          <div v-if="store.messages.length === 0" class="chat-placeholder">
            <p class="ph-title">与 LightCode 聊聊这个工作区</p>
            <p class="ph-desc">可以问问题，也可以要求修改代码——修改只会以候选变更集形式提出，由你审批后才写入。</p>
          </div>

          <article
            v-for="msg in store.messages"
            :key="msg.id"
            class="message"
            :class="[msg.role, msg.kind]"
            data-testid="chat-message"
          >
            <div v-if="msg.role === 'user'" class="bubble user-bubble">{{ msg.content }}</div>

            <div v-else-if="msg.kind === 'message'" class="bubble assistant-bubble">{{ msg.content }}</div>

            <div v-else-if="msg.kind === 'error'" class="bubble error-bubble" data-testid="error-message">
              {{ errorDisplayText(msg) }}
            </div>

            <div v-else-if="msg.kind === 'edit_summary'" class="edit-card" data-testid="edit-summary">
              <p class="card-kicker">待审批变更集（模型只提议 · 服务端校验）</p>
              <p class="card-summary">{{ msg.content }}</p>
              <div v-if="msg.taskId" class="card-actions">
                <span v-if="taskStateFor(msg.taskId) === 'awaiting_approval'" class="task-state waiting">等待审批</span>
                <span v-else-if="taskStateFor(msg.taskId) === 'completed'" class="task-state done">已写入</span>
                <span v-else-if="taskStateFor(msg.taskId) === 'cancelled'" class="task-state rejected">已拒绝</span>
                <button type="button" class="diff-btn" data-testid="view-diff-btn" @click="viewDiff(msg.taskId)">查看 Diff</button>
                <button
                  v-if="taskStateFor(msg.taskId) === 'awaiting_approval'"
                  type="button"
                  class="approve-btn"
                  data-testid="card-approve-btn"
                  :disabled="store.submitting"
                  @click="decideOnTask(msg.taskId, 'approve')"
                >批准写入</button>
                <button
                  v-if="taskStateFor(msg.taskId) === 'awaiting_approval'"
                  type="button"
                  class="reject-btn"
                  data-testid="card-reject-btn"
                  :disabled="store.submitting"
                  @click="decideOnTask(msg.taskId, 'reject')"
                >拒绝</button>
              </div>
            </div>
          </article>
        </div>

        <footer class="composer">
          <template v-if="pendingTask">
            <p class="pending-note">当前变更集等待审批：完整 Diff 请到审查页查看</p>
            <div class="pending-actions">
              <button type="button" class="diff-btn" data-testid="pending-view-diff" @click="viewDiff(store.task!.id)">查看 Diff</button>
              <button type="button" class="approve-btn" data-testid="pending-approve" :disabled="store.submitting" @click="store.submitDecision('approve')">
                {{ store.submitting ? '提交中…' : '批准写入' }}
              </button>
              <button type="button" class="reject-btn" data-testid="pending-reject" :disabled="store.submitting" @click="store.submitDecision('reject')">拒绝</button>
            </div>
          </template>

          <template v-else>
            <div class="input-row">
              <textarea
                v-model="draft"
                data-testid="chat-input"
                class="chat-input"
                rows="1"
                placeholder="输入消息，Enter 发送…"
                :disabled="!providerReady || store.sending"
                @keydown.enter.exact.prevent="send"
              />
              <button
                type="button"
                class="send-btn"
                data-testid="chat-send"
                :disabled="!providerReady || store.sending || !draft.trim()"
                @click="send"
              >{{ store.sending ? '处理中…' : '发送' }}</button>
            </div>
            <p v-if="!providerReady" class="provider-hint" data-testid="provider-hint">
              Provider 未就绪，无法开始对话。请先前往
              <button type="button" class="link-btn" @click="router.push('/settings')">设置</button>
              配置模型 Provider。
            </p>
          </template>
        </footer>
      </main>
    </div>
  </div>
</template>

<style scoped>
.ws-page {
  height: 100vh; height: 100dvh;
  display: flex; flex-direction: column;
  padding: 16px 24px;
  background: #f5f0e8; color: #2a2a2a;
  font-family: 'Architects Daughter', cursive;
}
.top-bar { display: flex; align-items: center; gap: 14px; padding-bottom: 12px; border-bottom: 2px solid #2a2a2a; margin-bottom: 14px; flex-shrink: 0; }
.back-btn { background: none; border: none; cursor: pointer; font-family: inherit; font-size: 13px; color: #6b7d8e; padding: 0; }
.back-btn:hover { color: #2a2a2a; }
.brand { font-family: 'Caveat', cursive; font-size: 22px; font-weight: 700; }
.ws-title { font-family: 'Caveat', cursive; font-size: 18px; font-weight: 600; color: #1a1a1a; }
.provider-badge {
  margin-left: auto;
  font-family: 'JetBrains Mono', monospace; font-size: 10px;
  padding: 3px 10px; border-radius: 12px;
  border: 1px solid #d8d0c4; color: #888;
}
.provider-badge.badge-ready { color: #2d7a3a; border-color: rgba(45,122,58,.3); background: rgba(45,122,58,.08); }
.provider-badge.badge-unconfigured { color: #c87020; border-color: rgba(200,112,32,.3); background: rgba(212,160,23,.1); }
.provider-badge.badge-degraded { color: #b83030; border-color: rgba(184,48,48,.25); background: rgba(184,48,48,.05); }
.settings-link { font-family: 'JetBrains Mono', monospace; font-size: 12px; color: #6b7d8e; cursor: pointer; padding: 4px; }
.settings-link:hover { color: #2a2a2a; }
.error-banner {
  border: 1.5px solid rgba(184,48,48,.35); background: rgba(184,48,48,.05);
  color: #b83030; border-radius: 5px; padding: 8px 14px; margin-bottom: 10px; font-size: 13px;
}
.columns { flex: 1; min-height: 0; display: grid; grid-template-columns: 300px 1fr; gap: 14px; }
.sidebar { min-height: 0; overflow-y: auto; display: flex; flex-direction: column; gap: 10px; padding-right: 4px; }
.panel {
  border: 1.5px solid #d8d0c4; border-radius: 6px;
  background: rgba(255,255,255,.25); padding: 10px 12px;
}
.panel-kicker {
  font-family: 'JetBrains Mono', monospace; font-size: 9px;
  text-transform: uppercase; letter-spacing: 1.5px; color: #aaa; margin-bottom: 8px;
}
.ws-switch, .entry-list, .session-list, .search-results { display: flex; flex-direction: column; gap: 2px; }
.ws-switch-row, .entry-row, .session-row, .hit-row {
  background: none; border: none; cursor: pointer; text-align: left;
  font-family: inherit; font-size: 12px; color: #2a2a2a;
  padding: 4px 6px; border-radius: 4px; display: flex; align-items: center; gap: 6px;
}
.ws-switch-row:hover:not(:disabled), .entry-row:hover:not(:disabled), .session-row:hover, .hit-row:hover { background: rgba(0,0,0,.04); }
.ws-switch-row.active, .session-row.active { background: rgba(212,160,23,.2); border: 1.5px solid #c87020; }
.ws-switch-row.disabled { color: #999; cursor: not-allowed; }
.off-tag { font-family: 'JetBrains Mono', monospace; font-size: 9px; color: #b83030; margin-left: auto; }
.files-panel { flex: 0 0 auto; }
.breadcrumbs { display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 6px; }
.crumb {
  background: none; border: none; cursor: pointer; padding: 0;
  font-family: 'JetBrains Mono', monospace; font-size: 10px; color: #6b7d8e;
}
.crumb:hover { color: #2a2a2a; }
.crumb + .crumb::before { content: '/'; margin-right: 4px; color: #ccc; }
.entry-row.blocked { color: #999; cursor: not-allowed; }
.entry-icon { width: 16px; flex-shrink: 0; }
.entry-tag { font-family: 'JetBrains Mono', monospace; font-size: 9px; color: #b83030; margin-left: auto; }
.search-row, .session-new { display: flex; gap: 6px; margin-top: 8px; }
.text-input {
  flex: 1; min-width: 0;
  font-family: inherit; font-size: 12px;
  border: 1.5px solid #d8d0c4; border-radius: 4px; padding: 5px 8px;
  background: rgba(255,255,255,.6); color: #2a2a2a;
}
.mini-btn {
  font-family: inherit; font-size: 12px; cursor: pointer;
  border: 1.5px solid #2a2a2a; border-radius: 4px; padding: 4px 10px;
  background: rgba(212,160,23,.15); color: #2a2a2a; flex-shrink: 0;
}
.mini-btn:disabled { opacity: .5; cursor: not-allowed; }
.code-surface {
  font-family: 'JetBrains Mono', monospace; font-size: 10px; line-height: 1.5;
  background: rgba(0,0,0,.03); border: 1px dashed #e0d8cc; border-radius: 4px;
  padding: 8px; white-space: pre-wrap; word-break: break-all;
  max-height: 24vh; overflow-y: auto;
}
.session-title { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.session-time { font-family: 'JetBrains Mono', monospace; font-size: 9px; color: #bbb; }
.empty-hint { color: #999; font-size: 11px; padding: 4px 0; }

.chat-panel {
  min-width: 0; min-height: 0;
  display: flex; flex-direction: column;
  border: 2.5px solid #2a2a2a; border-radius: 6px;
  background: rgba(255,255,255,.2);
}
.message-flow { flex: 1; min-height: 0; overflow-y: auto; padding: 16px 18px; display: flex; flex-direction: column; gap: 10px; }
.chat-placeholder { margin: auto; text-align: center; color: #aaa; }
.ph-title { font-family: 'Caveat', cursive; font-size: 22px; margin-bottom: 6px; }
.ph-desc { font-size: 13px; max-width: 420px; line-height: 1.7; }
.message { display: flex; }
.message.user { justify-content: flex-end; }
.message.assistant { justify-content: flex-start; }
.bubble {
  max-width: 78%;
  padding: 10px 14px; border-radius: 8px;
  font-size: 13px; line-height: 1.7; white-space: pre-wrap; word-break: break-word;
}
.user-bubble {
  background: rgba(45,90,122,.12); border: 1.5px solid rgba(45,90,122,.3);
  transform: rotate(.15deg);
}
.assistant-bubble { background: rgba(255,255,255,.55); border: 1.5px solid #d8d0c4; transform: rotate(-.1deg); }
.error-bubble { background: rgba(184,48,48,.05); border: 1.5px solid rgba(184,48,48,.25); color: #b83030; }
.edit-card {
  max-width: 82%;
  border: 2px solid #c87020; border-radius: 6px;
  background: rgba(212,160,23,.06); padding: 12px 14px;
}
.card-kicker { font-family: 'JetBrains Mono', monospace; font-size: 9px; text-transform: uppercase; letter-spacing: 1.2px; color: #c87020; margin-bottom: 6px; }
.card-summary { font-size: 13px; color: #444; line-height: 1.7; margin-bottom: 10px; }
.card-actions { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.task-state { font-family: 'JetBrains Mono', monospace; font-size: 10px; padding: 2px 8px; border-radius: 3px; }
.task-state.waiting { color: #c87020; border: 1px solid rgba(200,112,32,.3); }
.task-state.done { color: #2d7a3a; border: 1px solid rgba(45,122,58,.3); }
.task-state.rejected { color: #b83030; border: 1px solid rgba(184,48,48,.25); }
.diff-btn, .approve-btn, .reject-btn { font-family: inherit; font-size: 12px; cursor: pointer; border-radius: 4px; padding: 5px 12px; }
.diff-btn { border: 1.5px solid #2d5a7a; color: #2d5a7a; background: rgba(45,90,122,.08); }
.approve-btn { border: 1.5px solid #2d7a3a; color: #2d7a3a; background: rgba(45,122,58,.1); font-weight: 600; }
.reject-btn { border: 1.5px dashed #b83030; color: #b83030; background: none; }
.diff-btn:disabled, .approve-btn:disabled, .reject-btn:disabled { opacity: .5; cursor: not-allowed; }

.composer {
  flex-shrink: 0; padding: 10px 14px;
  border-top: 2.5px solid #2a2a2a;
  background: rgba(212,160,23,.04);
}
.input-row { display: flex; gap: 8px; align-items: flex-end; }
.chat-input {
  flex: 1; min-height: 40px; max-height: 120px; resize: vertical;
  font-family: inherit; font-size: 13px; line-height: 1.5;
  border: 1.5px solid #d8d0c4; border-radius: 4px; padding: 8px 10px;
  background: rgba(255,255,255,.6); color: #2a2a2a;
}
.chat-input:disabled { opacity: .55; }
.send-btn {
  font-family: inherit; font-size: 13px; cursor: pointer;
  border: 2px solid #2a2a2a; border-radius: 4px; padding: 8px 18px;
  background: rgba(212,160,23,.15); color: #2a2a2a; font-weight: 600;
}
.send-btn:disabled { opacity: .5; cursor: not-allowed; }
.provider-hint { margin-top: 8px; font-size: 12px; color: #c87020; }
.link-btn { background: none; border: none; cursor: pointer; color: #c87020; text-decoration: underline; font-size: inherit; padding: 0; }
.pending-note { font-size: 13px; color: #555; margin-bottom: 8px; }
.pending-actions { display: flex; gap: 8px; }
@media (max-width: 900px) {
  .columns { grid-template-columns: 1fr; }
  .sidebar { flex-direction: row; flex-wrap: wrap; }
}
</style>
