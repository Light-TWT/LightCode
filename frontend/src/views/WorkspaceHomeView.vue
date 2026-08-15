<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import AppSidebar from '@/components/AppSidebar.vue'
import SettingsOverlay from '@/components/SettingsOverlay.vue'
import WorkspacePicker from '@/components/WorkspacePicker.vue'
import { useWorkspaceStore } from '@/stores/workspace.store'
import type {
  ChatSession,
  RegisteredFileEntry,
  RegisteredWorkspace,
} from '@/types/agent'

const store = useWorkspaceStore()
const router = useRouter()
const input = ref('')
const sending = ref(false)
/** 导航栏折叠状态：与正式工作区页一致，支持收缩为窄图标条 */
const sidebarCollapsed = ref(false)
/** 设置层：大型模态层，与正式工作区页一致（不跳转独立设置页） */
const settingsOverlayOpen = ref(false)

function toggleSidebar() {
  sidebarCollapsed.value = !sidebarCollapsed.value
}

const current = computed<RegisteredWorkspace | null>(() =>
  store.workspaces.find((w) => w.id === store.currentWorkspaceId) ?? null,
)
const canSend = computed(() => Boolean(current.value && input.value.trim()))

onMounted(async () => {
  await store.loadWorkspaces()
})

/** 选定工作区：供输入框与文件/会话面板共用，选定后预取文件树与会话列表 */
async function selectWorkspace(ws: RegisteredWorkspace) {
  store.currentWorkspaceId = ws.id
  store.error = null
  await store.loadDirectory()
  await store.loadChatSessions(ws.id)
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

/** 技能管理入口：技能是全局设置，不绑定工作区。
 *  有工作区时取第一个跳转（路由需 workspaceId）；完全没有工作区时提示。 */
function openSkills() {
  const first = store.workspaces[0]
  if (!first) {
    store.error = '暂无工作区，请先添加工作文件夹。'
    return
  }
  router.push(`/workspace/${first.id}/skills`)
}

// ===== 侧边面板（沿用正式工作区页的交互） =====
type NavKey = 'workspace' | 'files' | 'sessions'
/** 当前展开的内容面板；null 表示全部收起。点击导航项展开，再点一次收起 */
const activeNav = ref<NavKey | null>(null)
/** 当前预览的文件标识（文件名）；用于文件行高亮与预览区 toggle */
const openPreviewName = ref<string | null>(null)
const activeHoverSession = ref<ChatSession | null>(null)

function toggleNav(key: NavKey) {
  activeNav.value = activeNav.value === key ? null : key
  // 切换面板时收起旧的预览高亮与菜单元件
  openPreviewName.value = null
  openMenuId.value = null
  cancelRename()
  // 文件/会话面板依赖当前工作区数据，打开时确保已就绪
  if (activeNav.value === 'files' && store.currentWorkspaceId) {
    store.loadDirectory()
  }
  if (activeNav.value === 'sessions' && store.currentWorkspaceId) {
    store.loadChatSessions(store.currentWorkspaceId)
  }
}

function closePreview() {
  openPreviewName.value = null
}

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

const searchInput = ref('')
async function runSearch() {
  await store.runSearch(searchInput.value.trim())
}

// ===== 会话面板：新建/打开/重命名/删除 =====
const newSessionTitle = ref('')

function openSession(id: string) {
  if (!current.value) return
  router.push(`/workspace/${current.value.id}/session/${id}`)
}

function showSessionHover(session: ChatSession) {
  activeHoverSession.value = session
}
function hideSessionHover() {
  activeHoverSession.value = null
}

function formatTime(iso: string): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  const hh = String(d.getHours()).padStart(2, '0')
  const mm = String(d.getMinutes()).padStart(2, '0')
  return `${hh}:${mm}`
}

async function createSession() {
  if (!current.value) return
  const title = newSessionTitle.value.trim() || '新会话'
  const session = await store.createChatSession(current.value.id, title)
  newSessionTitle.value = ''
  if (session) {
    router.push(`/workspace/${current.value.id}/session/${session.id}`)
  }
}

// 会话操作：菜单、重命名弹窗与删除确认（与工作区页一致的交互）
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
  if (!target || !title || renaming.value || !current.value) return
  renaming.value = true
  try {
    const ok = await store.renameChatSession(target.id, title, current.value.id)
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
  if (!target || deleting.value || !current.value) return
  deleting.value = true
  try {
    await store.deleteChatSession(target.id, current.value.id)
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

onMounted(() => {
  document.addEventListener('keydown', onGlobalKeydown)
  document.addEventListener('click', onGlobalClick)
})
</script>

<template>
  <div class="home-page" data-testid="home-page">
    <div class="columns">
      <!-- 左侧沿用正式工作区的共享侧边栏 -->
      <AppSidebar
        :active-nav="activeNav"
        :collapsed="sidebarCollapsed"
        @toggle="toggleNav"
        @toggle-collapse="toggleSidebar"
        @open-settings="settingsOverlayOpen = true"
        @open-skills="openSkills"
      />

      <!-- 内容面板：点击导航项展开，再点一次收起（同工作区页） -->
      <section class="side-panel" :class="{ hidden: !activeNav }" aria-label="侧边面板">
        <div v-if="activeNav === 'workspace'" class="panel-inner" data-testid="panel-workspace">
          <p class="panel-kicker">工作区</p>
          <div class="ws-switch">
            <button
              v-for="ws in store.workspaces"
              :key="ws.id"
              type="button"
              class="ws-switch-row"
              :class="{ active: ws.id === store.currentWorkspaceId, disabled: !ws.enabled }"
              data-testid="ws-switch-row"
              @click="ws.enabled && selectWorkspace(ws)"
            >
              {{ ws.displayName }}
              <span v-if="!ws.enabled" class="off-tag">已停用</span>
            </button>
            <p v-if="store.workspaces.length === 0" class="empty-hint">暂无工作区</p>
          </div>
        </div>

        <div v-else-if="activeNav === 'files'" class="panel-inner" data-testid="panel-files">
          <p class="panel-kicker">文件浏览（只读 · 服务端守卫）</p>
          <p v-if="!current" class="empty-hint">请先在上方选择工作文件夹</p>
          <template v-else>
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
          </template>
        </div>

        <div v-else-if="activeNav === 'sessions'" class="panel-inner session-panel" data-testid="panel-sessions">
          <p class="panel-kicker">会话</p>
          <p v-if="!current" class="empty-hint">请先在上方选择工作文件夹</p>
          <template v-else>
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
            <div class="session-area" @mouseleave="hideSessionHover">
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
                    @mouseenter="showSessionHover(s)"
                    @focus="showSessionHover(s)"
                    @click="openSession(s.id)"
                  >
                    <span class="session-title">{{ s.title }}</span>
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
              <aside v-if="activeHoverSession" class="session-hover-panel" data-testid="session-hover-panel">
                <p class="session-hover-label" data-testid="session-hover-title">{{ activeHoverSession.title }}</p>
                <div class="session-hover-row">
                  <svg class="session-hover-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true" data-testid="session-hover-workspace-icon">
                    <rect x="3" y="4.5" width="18" height="12" rx="1"></rect>
                    <path d="M9 19.5h6M12 16.5v3"></path>
                  </svg>
                  <strong data-testid="session-hover-workspace">{{ current?.displayName ?? '' }}</strong>
                </div>
                <div class="session-hover-row">
                  <svg class="session-hover-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true" data-testid="session-hover-time-icon">
                    <circle cx="12" cy="12" r="8.5"></circle>
                    <path d="M12 7v5l3 2"></path>
                  </svg>
                  <span data-testid="session-hover-updated">会话更新时间：{{ formatTime(activeHoverSession.updatedAt) }}</span>
                </div>
              </aside>
            </div>
          </template>
        </div>
      </section>

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
    </div>

    <!-- 设置层：大型模态层（不再跳转独立设置页） -->
    <SettingsOverlay :open="settingsOverlayOpen" @close="settingsOverlayOpen = false" />

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
.home-page {
  min-height: 100vh; height: 100vh; height: 100dvh;
  display: flex;
  background: #f5f0e8; color: #2a2a2a;
  font-family: 'Architects Daughter', cursive;
}
.home-page * { border-radius: 0; }
* { margin: 0; padding: 0; box-sizing: border-box; }
.columns {
  flex: 1; min-height: 0;
  display: flex; align-items: stretch;
}
.main-area {
  flex: 1; min-width: 0;
  display: flex; flex-direction: column;
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

/* ===== 内容面板（沿用正式工作区页的样式） ===== */
.side-panel {
  width: 300px; flex-shrink: 0; min-height: 0;
  border-right: 1px solid #d8d0c4;
  background: rgba(255,255,255,.25);
  padding: 12px 14px;
  overflow-x: visible;
  transition: width .18s ease;
}
.side-panel.hidden { width: 0; padding: 0; border-right: 0; overflow: hidden; }
.panel-inner { min-width: 268px; height: 100%; overflow-y: auto; }
.session-panel { overflow: visible; }
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
.session-area { position: relative; display: flex; align-items: flex-start; gap: 10px; }
.session-list { flex: 1; min-width: 0; gap: 6px; margin-top: 12px; padding-top: 8px; border-top: 1px solid #d8d0c4; }
.session-hover-panel {
  position: absolute; left: calc(100% + 10px); top: 12px; z-index: 12;
  width: 190px; box-sizing: border-box; display: flex; flex-direction: column; gap: 6px;
  padding: 12px; background: #f5f0e8; border: 1.5px solid #2a2a2a;
  box-shadow: 4px 4px 0 rgba(0,0,0,.12); color: #2a2a2a;
  font-size: 12px; line-height: 1.4;
}
.session-hover-label, .session-hover-panel span { color: #777; }
.session-hover-label { margin: 0; font-family: 'Caveat', cursive; font-size: 17px; color: #c87020; }
.session-hover-panel strong { font-family: 'Architects Daughter', cursive; font-size: 15px; font-weight: 700; }
.session-hover-row { display: flex; align-items: center; gap: 6px; }
.session-hover-icon { width: 15px; height: 15px; flex-shrink: 0; color: #c87020; }
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

@media (max-width: 900px) {
  .columns { flex-direction: column; }
  .side-panel { border-right: 0; }
  .side-panel.hidden { display: none; }
}
</style>