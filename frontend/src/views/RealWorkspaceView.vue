<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useRealStore } from '@/stores/real.store'
import type { RegisteredFileEntry } from '@/types/agent'

const route = useRoute()
const router = useRouter()
const store = useRealStore()

const workspaceId = computed(() => route.params.id as string)
const searchInput = ref('')
const taskTitle = ref('')

onMounted(() => store.openWorkspace(workspaceId.value))

const workspace = computed(
  () => store.workspaces.find((ws) => ws.id === workspaceId.value) ?? null,
)

/** 面包屑：'' 根 + 逐级目录段 */
const breadcrumbs = computed(() => {
  const segments = store.currentPath ? store.currentPath.split('/') : []
  const crumbs = [{ label: '根目录', path: '' }]
  let acc = ''
  for (const seg of segments) {
    acc = acc ? `${acc}/${seg}` : seg
    crumbs.push({ label: seg, path: acc })
  }
  return crumbs
})

function onEntryClick(entry: RegisteredFileEntry) {
  const path = store.childPath(entry)
  if (entry.kind === 'dir') {
    store.loadDirectory(path)
  } else if (entry.kind === 'file') {
    store.openFile(path)
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

async function createTask() {
  const title = taskTitle.value.trim()
  if (!title) return
  const task = await store.createTask(workspaceId.value, title)
  if (task) {
    await router.push(`/real/${workspaceId.value}/task/${task.id}`)
  }
}
</script>

<template>
  <div class="real-ws-page">
    <header class="top-bar">
      <button class="back-btn" type="button" data-testid="back-real-list-btn" @click="router.push('/real')">← 返回工作区列表</button>
      <div class="brand">{{ workspace?.displayName ?? workspaceId }}</div>
      <span class="policy-badge" v-if="workspace">策略 {{ workspace.policyVersion }}</span>
    </header>

    <div v-if="store.error" class="error-banner" data-testid="real-error">{{ store.error }}</div>

    <div class="columns">
      <section class="panel files-panel" aria-label="文件浏览">
        <p class="panel-kicker">文件浏览（只读，经服务端守卫）</p>
        <nav class="breadcrumbs" aria-label="路径">
          <button
            v-for="crumb in breadcrumbs"
            :key="crumb.path"
            type="button"
            class="crumb"
            @click="store.loadDirectory(crumb.path)"
          >{{ crumb.label }}</button>
        </nav>
        <div class="entry-list">
          <button
            v-for="entry in store.entries"
            :key="entry.relativePath"
            type="button"
            class="entry-row"
            :class="{ blocked: entry.kind === 'link' || entry.kind === 'secret' }"
            :disabled="entry.kind === 'link' || entry.kind === 'secret'"
            data-testid="file-entry"
            @click="onEntryClick(entry)"
          >
            <span class="entry-icon" aria-hidden="true">{{ kindIcon(entry.kind) }}</span>
            <span class="entry-name">{{ entry.name }}</span>
            <span v-if="entry.kind === 'secret'" class="entry-tag">密钥文件 · 禁止读取</span>
            <span v-else-if="entry.kind === 'link'" class="entry-tag">符号链接 · 禁止跟随</span>
          </button>
          <p v-if="!store.loading && store.entries.length === 0" class="empty-hint">目录为空</p>
        </div>
      </section>

      <section class="panel preview-panel" aria-label="文件预览">
        <p class="panel-kicker">文件预览</p>
        <template v-if="store.filePreview">
          <p class="preview-path" data-testid="preview-path">{{ store.filePreview.relativePath }}</p>
          <pre class="code-surface" data-testid="preview-content">{{ store.filePreview.content }}</pre>
        </template>
        <p v-else class="empty-hint">点击左侧文件查看内容</p>
      </section>

      <aside class="side-column">
        <section class="panel" aria-label="工作区内搜索">
          <p class="panel-kicker">内容搜索</p>
          <form class="search-row" @submit.prevent="runSearch">
            <input
              v-model="searchInput"
              data-testid="search-input"
              class="text-input"
              type="text"
              placeholder="搜索文件内容…"
            >
            <button class="primary-btn" type="submit" data-testid="search-btn">搜索</button>
          </form>
          <div v-if="store.searchQuery" class="search-results">
            <button
              v-for="hit in store.searchHits"
              :key="hit.relativePath"
              type="button"
              class="hit-row"
              data-testid="search-hit"
              @click="store.openFile(hit.relativePath)"
            >{{ hit.relativePath }}</button>
            <p v-if="store.searchHits.length === 0" class="empty-hint">无匹配结果</p>
          </div>
        </section>

        <section class="panel" aria-label="创建真实任务">
          <p class="panel-kicker">创建真实任务</p>
          <p class="tpl-note">模板：append-marker（服务端确定性变换，目标文件由服务端配置）</p>
          <form class="task-form" @submit.prevent="createTask">
            <input
              v-model="taskTitle"
              data-testid="task-title-input"
              class="text-input"
              type="text"
              placeholder="任务标题…"
            >
            <button
              class="primary-btn"
              type="submit"
              data-testid="create-task-btn"
              :disabled="store.submitting || !taskTitle.trim()"
            >{{ store.submitting ? '创建中…' : '创建任务' }}</button>
          </form>
        </section>
      </aside>
    </div>
  </div>
</template>

<style scoped>
.real-ws-page {
  min-height: 100vh;
  padding: 24px 40px;
  background: #f5f0e8;
  color: #2a2a2a;
  font-family: 'Architects Daughter', cursive;
}
.top-bar { display: flex; align-items: center; gap: 16px; margin-bottom: 18px; }
.back-btn { background: none; border: none; cursor: pointer; font-family: inherit; font-size: 13px; color: #6b7d8e; padding: 0; }
.back-btn:hover { color: #2a2a2a; }
.brand { font-family: 'Caveat', cursive; font-size: 24px; font-weight: 700; }
.policy-badge { font-family: 'JetBrains Mono', monospace; font-size: 10px; color: #aaa; }
.error-banner {
  border: 1.5px solid rgba(184,48,48,.35); background: rgba(184,48,48,.05);
  color: #b83030; border-radius: 5px; padding: 10px 14px; margin-bottom: 14px; font-size: 13px;
}
.columns { display: grid; grid-template-columns: 280px 1fr 300px; gap: 16px; align-items: start; }
.panel {
  border: 1.5px solid #d8d0c4; border-radius: 6px;
  background: rgba(255,255,255,.25); padding: 14px 16px; margin-bottom: 16px;
}
.panel-kicker {
  font-family: 'JetBrains Mono', monospace; font-size: 10px;
  text-transform: uppercase; letter-spacing: 1.5px; color: #aaa; margin-bottom: 10px;
}
.breadcrumbs { display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 10px; }
.crumb {
  background: none; border: none; cursor: pointer; padding: 0;
  font-family: 'JetBrains Mono', monospace; font-size: 11px; color: #6b7d8e;
}
.crumb:hover { color: #2a2a2a; }
.crumb + .crumb::before { content: '/'; margin-right: 4px; color: #ccc; }
.entry-list { display: flex; flex-direction: column; gap: 2px; }
.entry-row {
  display: flex; align-items: center; gap: 8px;
  background: none; border: none; cursor: pointer; text-align: left;
  font-family: inherit; font-size: 13px; color: #2a2a2a;
  padding: 5px 6px; border-radius: 4px;
}
.entry-row:hover:not(:disabled) { background: rgba(0,0,0,.04); }
.entry-row.blocked { color: #999; cursor: not-allowed; }
.entry-icon { width: 18px; flex-shrink: 0; }
.entry-tag { font-family: 'JetBrains Mono', monospace; font-size: 9px; color: #b83030; margin-left: auto; }
.preview-path { font-family: 'JetBrains Mono', monospace; font-size: 12px; color: #555; margin-bottom: 8px; }
.code-surface {
  font-family: 'JetBrains Mono', monospace; font-size: 12px; line-height: 1.6;
  background: rgba(0,0,0,.03); border: 1px dashed #e0d8cc; border-radius: 4px;
  padding: 12px; white-space: pre-wrap; word-break: break-all;
  max-height: 60vh; overflow-y: auto;
}
.search-row, .task-form { display: flex; gap: 8px; }
.text-input {
  flex: 1; min-width: 0;
  font-family: inherit; font-size: 13px;
  border: 1.5px solid #d8d0c4; border-radius: 4px; padding: 6px 10px;
  background: rgba(255,255,255,.6); color: #2a2a2a;
}
.primary-btn {
  font-family: inherit; font-size: 13px; cursor: pointer;
  border: 1.5px solid #2a2a2a; border-radius: 4px; padding: 6px 14px;
  background: rgba(212,160,23,.15); color: #2a2a2a; flex-shrink: 0;
}
.primary-btn:disabled { opacity: .5; cursor: not-allowed; }
.search-results { margin-top: 10px; display: flex; flex-direction: column; gap: 2px; }
.hit-row {
  background: none; border: none; cursor: pointer; text-align: left; padding: 4px 6px;
  font-family: 'JetBrains Mono', monospace; font-size: 12px; color: #2d5a7a; border-radius: 4px;
}
.hit-row:hover { background: rgba(0,0,0,.04); }
.tpl-note { font-size: 12px; color: #6b7d8e; margin-bottom: 10px; line-height: 1.6; }
.empty-hint { color: #999; font-size: 12px; padding: 6px 0; }
@media (max-width: 1000px) { .columns { grid-template-columns: 1fr; } }
</style>
