<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useWorkspaceStore } from '@/stores/workspace.store'
import { providerService } from '@/services/provider.service'
import type {
  ApprovalDecision,
  ChatMessage,
  ChatSession,
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

/** 导航栏折叠状态：收缩为窄图标条 */
const sidebarCollapsed = ref(false)
/** 当前展开的内容面板；null 表示全部收起。点击导航项展开，再点一次收起 */
type NavKey = 'workspace' | 'files' | 'sessions'
const activeNav = ref<NavKey | null>(null)
/** 当前预览的文件标识（文件名）；用于文件行高亮与预览区 toggle */
const openPreviewName = ref<string | null>(null)

function toggleSidebar() {
  sidebarCollapsed.value = !sidebarCollapsed.value
}

function toggleNav(key: NavKey) {
  activeNav.value = activeNav.value === key ? null : key
  // 切换面板时收起旧的预览高亮
  openPreviewName.value = null
  openMenuId.value = null
  cancelRename()
}

function closePreview() {
  openPreviewName.value = null
}

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
    openPreviewName.value = null
  } else if (entry.kind === 'file' && entry.token) {
    // 再点一次同一文件：收起预览（toggle）
    if (openPreviewName.value === entry.name) {
      openPreviewName.value = null
      return
    }
    openPreviewName.value = entry.name
    store.openFileByToken(entry.token)
  }
  // link / secret：受安全策略保护，不可读取
}

function onSearchHit(hit: { token?: string; name: string }) {
  if (!hit.token) return
  openPreviewName.value = hit.name
  store.openFileByToken(hit.token)
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

// 会话操作：菜单、重命名弹窗与删除确认
const openMenuId = ref<string | null>(null)
const renameTarget = ref<ChatSession | null>(null)
const renameDraft = ref('')
const renaming = ref(false)
const pendingDelete = ref<ChatSession | null>(null)
const deleting = ref(false)
const cancelBtn = ref<HTMLButtonElement | null>(null)
const renameInput = ref<HTMLInputElement | null>(null)
const renameCancelButton = ref<HTMLButtonElement | null>(null)

function toggleMenu(sessionId: string) {
  openMenuId.value = openMenuId.value === sessionId ? null : sessionId
}

function closeMenu() {
  openMenuId.value = null
}

function startRename(session: ChatSession) {
  closeMenu()
  renameTarget.value = session
  renameDraft.value = session.title
  nextTick(() => {
    if (renameInput.value) {
      renameInput.value.focus()
    } else {
      renameCancelButton.value?.focus()
    }
  })
}

function cancelRename() {
  if (renaming.value) return
  renameTarget.value = null
  renameDraft.value = ''
}

async function commitRename() {
  const target = renameTarget.value
  const title = renameDraft.value.trim()
  if (!target || !title || renaming.value) return
  renaming.value = true
  try {
    const ok = await store.renameChatSession(target.id, title, workspaceId.value)
    if (ok) {
      renameTarget.value = null
      renameDraft.value = ''
    }
  } finally {
    renaming.value = false
  }
}

function requestDelete(session: ChatSession) {
  closeMenu()
  pendingDelete.value = session
  nextTick(() => cancelBtn.value?.focus())
}

function cancelDelete() {
  if (deleting.value) return
  pendingDelete.value = null
}

async function confirmDelete() {
  const target = pendingDelete.value
  if (!target || deleting.value) return
  deleting.value = true
  try {
    const wasCurrent = target.id === store.currentSessionId
    const ok = await store.deleteChatSession(target.id, workspaceId.value)
    if (ok && wasCurrent) {
      const next = store.currentSessionId
      if (next) {
        router.push(`/workspace/${workspaceId.value}/session/${next}`)
      } else {
        router.push(`/workspace/${workspaceId.value}`)
      }
    }
  } finally {
    deleting.value = false
    pendingDelete.value = null
  }
}

function onGlobalKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape') {
    if (renameTarget.value) {
      cancelRename()
      return
    }
    if (pendingDelete.value) {
      cancelDelete()
      return
    }
    closeMenu()
  }
}

function onGlobalClick(e: MouseEvent) {
  const target = e.target as HTMLElement
  if (!target.closest('.session-item') && !target.closest('.dialog-backdrop')) {
    closeMenu()
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

onMounted(() => {
  document.addEventListener('keydown', onGlobalKeydown)
  document.addEventListener('click', onGlobalClick)
})

onUnmounted(() => {
  store.cleanup()
  document.removeEventListener('keydown', onGlobalKeydown)
  document.removeEventListener('click', onGlobalClick)
})
</script>

<template>
  <div class="ws-page">
    <div class="columns">
      <!-- 导航栏：可折叠为窄图标条 -->
      <aside class="sidebar" :class="{ collapsed: sidebarCollapsed }" aria-label="侧边导航">
        <div class="brand">
          <span class="brand-mark" aria-hidden="true">L</span>
          <span class="brand-text">LightCode</span>
          <button
            type="button"
            class="brand-arrow"
            :title="sidebarCollapsed ? '展开侧边栏' : '折叠为图标'"
            data-testid="sidebar-collapse"
            @click="toggleSidebar"
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
            @click="toggleNav('workspace')"
          >
            <span class="icon" aria-hidden="true"><svg viewBox="0 0 24 24"><rect x="4" y="4" width="6" height="6" rx="1"/><rect x="14" y="4" width="6" height="6" rx="1"/><rect x="4" y="14" width="6" height="6" rx="1"/><rect x="14" y="14" width="6" height="6" rx="1"/></svg></span>
            <span class="label">工作区</span>
          </button>
          <button
            type="button"
            class="nav-btn"
            :class="{ active: activeNav === 'files' }"
            data-testid="nav-btn-files"
            @click="toggleNav('files')"
          >
            <span class="icon" aria-hidden="true"><svg viewBox="0 0 24 24"><path d="M5 4.5h10l4 4V19a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V5.5a1 1 0 0 1 1-1Z"/><path d="M14 4.5V9h5"/></svg></span>
            <span class="label">文件浏览</span>
          </button>
          <button
            type="button"
            class="nav-btn"
            :class="{ active: activeNav === 'sessions' }"
            data-testid="nav-btn-sessions"
            @click="toggleNav('sessions')"
          >
            <span class="icon" aria-hidden="true"><svg viewBox="0 0 24 24"><path d="M4 5.5A1.5 1.5 0 0 1 5.5 4h13A1.5 1.5 0 0 1 20 5.5v10a1.5 1.5 0 0 1-1.5 1.5H13l-4 3v-3H5.5A1.5 1.5 0 0 1 4 15.5Z"/></svg></span>
            <span class="label">会话</span>
          </button>
        </nav>

        <div class="bottom">
          <button
            type="button"
            class="settings"
            title="设置"
            data-testid="settings-btn"
            @click="router.push('/settings')"
          >
            <span class="icon" aria-hidden="true"><svg viewBox="0 0 24 24"><circle cx="14" cy="13" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1-1.7 1.7-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.6v.2h-2.4v-.2a1.7 1.7 0 0 0-1-1.6 1.7 1.7 0 0 0-1.9.3l-.1.1L8 17l.1-.1a1.7 1.7 0 0 0 .3-1.9 1.7 1.7 0 0 0-1.6-1H6v-2.4h.8a1.7 1.7 0 0 0 1.6-1 1.7 1.7 0 0 0-.3-1.9L8 8.6l1.7-1.7.1.1a1.7 1.7 0 0 0 1.9.3 1.7 1.7 0 0 0 1-1.6v-.2h2.4v.2a1.7 1.7 0 0 0 1 1.6 1.7 1.7 0 0 0 1.9-.3l.1-.1 1.7 1.7-.1.1a1.7 1.7 0 0 0-.3 1.9 1.7 1.7 0 0 0 1.6 1h.2V14h-.2a1.7 1.7 0 0 0-1.6 1Z"/></svg></span>
            <span class="label">设置</span>
          </button>
        </div>
      </aside>

      <!-- 内容面板：点击导航项展开，再点一次收起 -->
      <section class="side-panel" :class="{ hidden: !activeNav }" aria-label="侧边面板">
        <div v-if="activeNav === 'workspace'" class="panel-inner" data-testid="panel-workspace">
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
        </div>

        <div v-else-if="activeNav === 'files'" class="panel-inner" data-testid="panel-files">
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
              :class="{ blocked: entry.kind === 'link' || entry.kind === 'secret', active: openPreviewName === entry.name }"
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
              :class="{ active: openPreviewName === hit.name }"
              data-testid="search-hit"
              @click="onSearchHit(hit)"
            >{{ hit.name }}</button>
            <p v-if="store.searchHits.length === 0" class="empty-hint">无匹配结果</p>
          </div>
          <!-- 文件预览区：选中文件后在面板内展开 -->
          <div v-if="openPreviewName && store.filePreview" class="preview" data-testid="file-preview">
            <div class="preview-head">
              <span class="preview-name" data-testid="preview-name">{{ openPreviewName }}</span>
              <button type="button" class="preview-close" data-testid="preview-close" @click="closePreview">✕ 关闭预览</button>
            </div>
            <pre class="code-surface" data-testid="preview-content">{{ store.filePreview.content }}</pre>
          </div>
        </div>

        <div v-else-if="activeNav === 'sessions'" class="panel-inner" data-testid="panel-sessions">
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
            <div
              v-for="s in store.chatSessions"
              :key="s.id"
              class="session-item"
              :class="{ active: s.id === store.currentSessionId }"
            >
              <button
                type="button"
                class="session-row"
                data-testid="session-row"
                @click="openSession(s.id)"
              >
                <span class="session-title">{{ s.title }}</span>
                <span class="session-time">{{ s.updatedAt }}</span>
              </button>
              <button
                type="button"
                class="more-btn"
                :class="{ open: openMenuId === s.id }"
                data-testid="session-more"
                :aria-expanded="openMenuId === s.id ? 'true' : 'false'"
                aria-label="会话操作"
                @click.stop="toggleMenu(s.id)"
              >⋮</button>
              <div v-if="openMenuId === s.id" class="session-menu" data-testid="session-menu">
                <button type="button" class="menu-item" data-testid="session-rename" @click="startRename(s)">
                  <span class="menu-icon" aria-hidden="true">✎</span>重命名
                </button>
                <button type="button" class="menu-item danger" data-testid="session-delete" @click="requestDelete(s)">
                  <span class="menu-icon" aria-hidden="true">⌫</span>删除会话
                </button>
              </div>
            </div>
            <p v-if="store.chatSessions.length === 0" class="empty-hint">暂无会话，新建一个开始对话</p>
          </div>
        </div>
      </section>

      <main class="chat-panel" aria-label="聊天">
        <header class="main-head">
          <button class="back-btn" type="button" data-testid="back-home-btn" @click="router.push('/')">← 首页</button>
          <span class="wordmark">LightCode</span>
          <span class="ws-title" data-testid="workspace-title">{{ workspace?.displayName ?? workspaceId }}</span>
          <span
            class="provider-badge"
            :class="providerBadgeClass"
            data-testid="provider-status"
          >Provider {{ providerStatusLabel }}</span>
        </header>
        <div v-if="store.error" class="error-banner" data-testid="ws-error">{{ store.error }}</div>
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

    <div v-if="renameTarget" class="dialog-backdrop" data-testid="rename-dialog" role="dialog" aria-modal="true" aria-labelledby="rename-dialog-title" @click.self="cancelRename">
      <div class="confirm-dialog rename-dialog">
        <h2 id="rename-dialog-title" class="dialog-title">重命名会话</h2>
        <form data-testid="rename-dialog-form" @submit.prevent="commitRename">
          <input
            ref="renameInput"
            v-model="renameDraft"
            data-testid="rename-dialog-input"
            class="text-input rename-dialog-input"
            type="text"
            :disabled="renaming"
            aria-label="会话标题"
            @keydown.esc.prevent="cancelRename"
          >
          <div class="dialog-actions">
            <button ref="renameCancelButton" type="button" class="dialog-btn" data-testid="rename-dialog-cancel" :disabled="renaming" @click="cancelRename">取消</button>
            <button type="submit" class="dialog-btn accent" data-testid="rename-dialog-confirm" :disabled="renaming || !renameDraft.trim()">
              {{ renaming ? '保存中…' : '保存' }}
            </button>
          </div>
        </form>
      </div>
    </div>

    <div v-if="pendingDelete" class="dialog-backdrop" data-testid="delete-dialog" @click.self="cancelDelete">
      <div class="confirm-dialog" role="dialog" aria-modal="true" aria-labelledby="delete-dialog-title">
        <h2 id="delete-dialog-title" class="dialog-title">删除此会话？</h2>
        <p class="dialog-copy">这会永久删除会话「{{ pendingDelete.title }}」及其中的全部消息，且无法恢复。</p>
        <div class="dialog-actions">
          <button ref="cancelBtn" type="button" class="dialog-btn" data-testid="delete-cancel" :disabled="deleting" @click="cancelDelete">取消</button>
          <button type="button" class="dialog-btn danger" data-testid="delete-confirm" :disabled="deleting" @click="confirmDelete">
            {{ deleting ? '删除中…' : '删除会话' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.ws-page {
  height: 100vh; height: 100dvh;
  display: flex; flex-direction: column;
  background: #f5f0e8; color: #2a2a2a;
  font-family: 'Architects Daughter', cursive;
}
/* 全局直角：去掉所有圆角，保持线性风格 */
.ws-page * { border-radius: 0; }
.main-head {
  height: 58px; flex-shrink: 0;
  display: flex; align-items: center; gap: 14px;
  padding: 0 24px; border-bottom: 1px solid #d8d0c4;
}
.back-btn { background: none; border: none; cursor: pointer; font-family: inherit; font-size: 13px; color: #6b7d8e; padding: 0; }
.back-btn:hover { color: #2a2a2a; }
.wordmark { font-family: 'Caveat', cursive; font-size: 22px; font-weight: 700; }
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
.error-banner {
  border: 1.5px solid rgba(184,48,48,.35); background: rgba(184,48,48,.05);
  color: #b83030; border-radius: 5px; padding: 8px 14px; margin-bottom: 10px; font-size: 13px;
}

.columns {
  flex: 1; min-height: 0;
  display: flex; align-items: stretch;
}

/* ===== 导航栏 ===== */
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
.sidebar.collapsed .brand { padding: 0; justify-content: center; height: 48px; }
.sidebar.collapsed .brand-mark, .sidebar.collapsed .brand-text { display: none; }
.sidebar.collapsed .nav { padding: 12px 0; align-items: center; }
.sidebar.collapsed .nav-btn, .sidebar.collapsed .settings { justify-content: center; padding: 0; width: 40px; height: 40px; margin: 0 auto; }
.sidebar.collapsed .bottom { padding: 10px 0 12px; }
.sidebar.collapsed .label { display: none; }

/* ===== 内容面板：点击导航项展开，再点一次收起 ===== */
.side-panel {
  width: 300px; flex-shrink: 0; min-height: 0;
  border-right: 1px solid #d8d0c4;
  background: rgba(255,255,255,.25);
  padding: 12px 14px;
  overflow-x: hidden;
  transition: width .18s ease;
}
.side-panel.hidden { width: 0; padding: 0; border-right: 0; overflow: hidden; }
.panel-inner { min-width: 268px; height: 100%; overflow-y: auto; }
.panel-kicker {
  font-family: 'JetBrains Mono', monospace; font-size: 9px;
  text-transform: uppercase; letter-spacing: 1.5px; color: #aaa; margin: 4px 0 10px;
}
.ws-switch, .entry-list, .session-list, .search-results { display: flex; flex-direction: column; gap: 2px; }
.ws-switch-row, .entry-row, .session-row, .hit-row {
  background: none; border: none; cursor: pointer; text-align: left;
  font-family: inherit; font-size: 12px; color: #2a2a2a;
  padding: 4px 6px; border-radius: 4px; display: flex; align-items: center; gap: 6px;
}
.ws-switch-row:hover:not(:disabled), .entry-row:hover:not(:disabled), .session-row:hover, .hit-row:hover { background: rgba(0,0,0,.04); }
.ws-switch-row.active, .session-row.active, .entry-row.active, .hit-row.active { background: rgba(212,160,23,.2); border: 1.5px solid #c87020; }
.ws-switch-row.disabled { color: #999; cursor: not-allowed; }
.off-tag { font-family: 'JetBrains Mono', monospace; font-size: 9px; color: #b83030; margin-left: auto; }
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
.empty-hint { color: #999; font-size: 11px; padding: 4px 0; }
/* 文件预览区（并入文件浏览面板） */
.preview {
  margin-top: 10px;
  border: 2px solid #2a2a2a; border-radius: 6px;
  background: rgba(255,255,255,.4); padding: 10px 12px;
}
.preview-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px; }
.preview-name { font-family: 'Caveat', cursive; font-size: 15px; font-weight: 700; color: #1a1a1a; }
.preview-close { background: none; border: 0; cursor: pointer; font-family: inherit; font-size: 11px; color: #999; padding: 0; }
.preview-close:hover { color: #2a2a2a; }
.code-surface {
  font-family: 'JetBrains Mono', monospace; font-size: 10px; line-height: 1.5;
  background: rgba(0,0,0,.03); border: 1px dashed #e0d8cc; border-radius: 4px;
  padding: 8px; white-space: pre-wrap; word-break: break-all;
  max-height: 26vh; overflow-y: auto; margin: 0;
}

/* ===== 会话操作：列表间距、更大行高、菜单与确认框 ===== */
.session-list { gap: 6px; margin-top: 12px; padding-top: 8px; border-top: 1px solid #d8d0c4; }
.session-item {
  position: relative;
  display: flex; align-items: center; gap: 2px;
  border-radius: 4px; border: 1.5px solid transparent;
}
.session-item.active { background: rgba(212,160,23,.2); border-color: #c87020; }
.session-row {
  flex: 1; min-width: 0;
  padding: 8px 10px; font-size: 13px; gap: 8px;
  background: none; border: none; cursor: pointer; text-align: left;
  font-family: inherit; color: #2a2a2a;
  display: flex; align-items: center;
}
.session-item:hover .session-row { background: rgba(0,0,0,.04); }
.session-title { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-weight: 500; }
.session-time { font-family: 'JetBrains Mono', monospace; font-size: 10px; color: #aaa; flex-shrink: 0; }
.more-btn {
  width: 28px; height: 28px; flex-shrink: 0;
  display: grid; place-items: center;
  border: 0; background: none; cursor: pointer;
  font-family: inherit; font-size: 14px; line-height: 1; color: #999;
  opacity: 0; border-radius: 4px;
}
.session-item:hover .more-btn, .more-btn:focus-visible, .more-btn.open { opacity: 1; color: #2a2a2a; }
.more-btn:hover { background: rgba(0,0,0,.05); }
.more-btn:focus-visible { outline: 1.5px solid #c87020; outline-offset: 1px; }
.session-menu {
  position: absolute; right: 0; top: calc(100% + 4px); z-index: 20;
  min-width: 140px;
  background: #f5f0e8; border: 1.5px solid #2a2a2a;
  box-shadow: 3px 3px 0 rgba(0,0,0,.12);
  padding: 4px; display: flex; flex-direction: column; gap: 2px;
}
.menu-item {
  display: flex; align-items: center; gap: 8px;
  border: 0; background: none; cursor: pointer; text-align: left;
  font-family: inherit; font-size: 13px; color: #2a2a2a;
  padding: 7px 10px; border-radius: 4px;
}
.menu-item:hover { background: rgba(0,0,0,.05); }
.menu-item.danger { color: #b83030; }
.menu-item.danger:hover { background: rgba(184,48,48,.08); }
.menu-icon { width: 16px; text-align: center; flex-shrink: 0; }
/* ===== 删除确认对话框（项目纸张风格） ===== */
.dialog-backdrop {
  position: fixed; inset: 0; z-index: 50;
  display: flex; align-items: center; justify-content: center;
  background: rgba(42,42,42,.18); padding: 16px;
}
.confirm-dialog {
  width: min(100%, 360px);
  background: #f5f0e8; border: 2px solid #2a2a2a;
  box-shadow: 4px 4px 0 rgba(0,0,0,.14);
  padding: 20px 22px;
}
.dialog-title { font-family: 'Caveat', cursive; font-size: 20px; font-weight: 700; color: #1a1a1a; margin: 0 0 8px; }
.dialog-copy { font-size: 13px; line-height: 1.7; color: #444; margin: 0 0 16px; }
.dialog-actions { display: flex; justify-content: flex-end; gap: 8px; }
.dialog-btn {
  font-family: inherit; font-size: 13px; cursor: pointer;
  border: 1.5px solid #2a2a2a; border-radius: 4px; padding: 6px 14px;
  background: transparent; color: #2a2a2a;
}
.dialog-btn.accent { border-color: #c87020; color: #c87020; background: rgba(212,160,23,.12); }
.dialog-btn.accent:hover { background: rgba(212,160,23,.22); }
.dialog-btn.danger { border-color: #b83030; color: #b83030; }
.dialog-btn.danger:hover { background: rgba(184,48,48,.08); }
.dialog-btn:disabled { opacity: .5; cursor: not-allowed; }
.rename-dialog-input { display: block; width: 100%; box-sizing: border-box; font-size: 14px; padding: 8px 10px; margin-bottom: 16px; }
.rename-dialog-input:focus { outline: 1.5px solid #c87020; outline-offset: 1px; }

/* ===== 聊天面板 ===== */
.chat-panel {
  flex: 1; min-width: 0; min-height: 0;
  display: flex; flex-direction: column;
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
  flex-shrink: 0; padding: 12px 18px;
  border-top: 1px solid #d8d0c4;
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
  .columns { flex-direction: column; }
  .sidebar { width: 100%; flex-direction: row; flex-wrap: wrap; border-right: 0; border-bottom: 1.5px solid #2a2a2a; }
  .sidebar.collapsed { width: 52px; flex-direction: column; }
  .side-panel { border-right: 0; }
  .side-panel.hidden { display: none; }
}
</style>