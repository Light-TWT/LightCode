<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useHistoryStore } from '@/stores/history.store'
import type { HistoryTaskEntry, HistoryTaskStatus } from '@/types/agent'

const route = useRoute()
const router = useRouter()
const store = useHistoryStore()
const expandedDiffIds = ref<string[]>([])

const workspaceId = computed(() => route.params.id as string)

onMounted(() => store.load(workspaceId.value))

function filterLabel(status: string): string {
  return status === 'all' ? '全部' : status === 'waiting' ? '等待审批' : status === 'done' ? '已完成' : status === 'fail' ? '失败' : '已取消'
}

function statusLabel(status: HistoryTaskStatus): string {
  return status === 'waiting' ? '等待审批' : status === 'done' ? '已完成' : status === 'fail' ? '失败' : '已取消'
}

function planStepMark(state: string): string {
  return state === 'done' ? '✓' : state === 'fail' ? '✕' : state === 'waiting' ? '•' : ''
}

function planStepTag(state: string): string {
  return state === 'done' ? '完成' : state === 'fail' ? '失败' : state === 'waiting' ? '待审批' : '未执行'
}

function planStepClass(state: string): string {
  return state === 'done' ? 'done' : state === 'fail' ? 'fail' : state === 'waiting' ? 'waiting' : 'pending'
}

function toggleDiff(key: string) {
  if (expandedDiffIds.value.includes(key)) {
    expandedDiffIds.value = expandedDiffIds.value.filter(k => k !== key)
  } else {
    expandedDiffIds.value.push(key)
  }
}

function onEntryClick(entry: HistoryTaskEntry) {
  if (entry.status === 'waiting') return
  store.openDetail(entry.id)
}

function goToWorkspace() {
  router.push(`/workspace/${workspaceId.value}`)
}

function onResizeStart(e: MouseEvent) {
  const start = e.clientX
  const startW = store.detailWidth
  const onMove = (me: MouseEvent) => {
    store.detailWidth = Math.min(Math.max(startW + start - me.clientX, 340), Math.round(window.innerWidth * 0.55))
  }
  const onUp = () => {
    window.removeEventListener('mousemove', onMove)
    window.removeEventListener('mouseup', onUp)
  }
  window.addEventListener('mousemove', onMove)
  window.addEventListener('mouseup', onUp)
  e.preventDefault()
}

function statusDotClass(status: HistoryTaskStatus): string {
  return status === 'waiting' ? 'waiting' : status === 'done' ? 'done' : status === 'fail' ? 'fail' : 'cancelled'
}

function entryStatusClass(status: HistoryTaskStatus): string {
  return `s-${status === 'waiting' ? 'waiting' : status === 'done' ? 'done' : status === 'fail' ? 'fail' : 'cancelled'}`
}

function detailStatusClass(status: HistoryTaskStatus): string {
  return `ds-${status === 'waiting' ? 'waiting' : status === 'done' ? 'done' : status === 'fail' ? 'fail' : 'cancelled'}`
}

function testResultClass(result: string): string {
  return `tr-${result}`
}

function testResultText(result: string): string {
  return result === 'pass' ? '✓ 通过' : result === 'fail' ? '✕ 失败' : '— 未运行'
}

const selectedEntry = computed(() => {
  if (!store.detail) return null
  return store.entries.find(e => e.id === store.detail!.id)
})
</script>

<template>
  <div class="shell">
    <header class="top-bar">
      <div class="brand"><span class="brand-dot" aria-hidden="true" />LightCode</div>
      <div class="top-right">
        <div class="runtime-badge">Local runtime ready</div>
        <span class="settings-icon" title="设置" @click="router.push('/settings')">⚙</span>
      </div>
    </header>

    <div class="project-context">
      <span class="back-link" @click="goToWorkspace"><span class="arrow" aria-hidden="true">←</span> 返回工作区</span>
      <span class="project-name-inline">{{ workspaceId === 'workspace-login-service' ? 'login-service' : workspaceId }}</span>
      <span class="project-path-inline">{{ workspaceId === 'workspace-login-service' ? '~/workspace/login-service' : '' }}</span>
      <span class="ctx-spacer" />
      <span class="status-chip chip-running">本地运行中</span>
    </div>

    <div class="page-header">
      <h1 class="page-title">任务历史</h1>
      <p class="page-subtitle">Agent 在本项目中执行过的所有任务</p>
    </div>

    <div class="search-bar">
      <input data-testid="search-input" v-model="store.searchQuery" class="search-input" type="text" placeholder="搜索任务描述、文件名、测试命令…">
    </div>

    <div class="filter-bar">
      <button v-for="f in ['all', 'waiting', 'done', 'fail', 'cancelled']" :key="f" data-testid="filter-chip" class="filter-chip" :class="{ active: store.activeFilter === f }" @click="store.setFilter(f as any)">
        {{ filterLabel(f) }} <span class="filter-count">{{ store.filterCounts[f as keyof typeof store.filterCounts] }}</span>
      </button>
    </div>

    <div class="workbench">
      <div class="task-list-panel">
        <div class="main-scroll">
          <div class="timeline">
            <article
              v-for="entry in store.filteredEntries"
              :key="entry.id"
              data-testid="task-entry"
              class="task-entry"
              :class="[
                entry.status === 'waiting' ? 'primary' : 'secondary',
                entry.status === 'fail' ? 'fail-entry' : '',
                entry.status === 'cancelled' ? 'cancelled-entry' : '',
                `status-${entry.status}`,
                { 'active-entry': store.detail?.id === entry.id },
              ]"
              @click="onEntryClick(entry)"
            >
              <div class="tl-dot-col"><div class="tl-dot" :class="statusDotClass(entry.status)" /></div>
              <div class="entry-body">
                <div class="entry-header">
                  <span class="entry-status" :class="entryStatusClass(entry.status)">{{ statusLabel(entry.status) }}</span>
                  <span class="entry-time">{{ entry.time }}</span>
                  <span class="entry-duration">· {{ entry.duration }}</span>
                  <span class="entry-spacer" />
                  <button
                    v-if="entry.status === 'waiting'"
                    data-testid="action-review"
                    class="entry-action action-review"
                    type="button"
                    @click.stop="goToWorkspace()"
                  >继续审查</button>
                  <button
                    v-else
                    class="entry-action"
                    :class="{ 'action-fail-detail': entry.status === 'fail' }"
                    type="button"
                    @click.stop="store.openDetail(entry.id)"
                  >{{ entry.status === 'fail' ? '查看失败详情' : '查看记录' }}</button>
                </div>
                <div class="entry-task">{{ entry.title }}</div>
                <div class="entry-summary">{{ entry.summary }}</div>
                <div class="entry-meta">
                  <span class="meta-files">
                    <span v-for="f in entry.files" :key="f.name" class="file-chip">
                      {{ f.name }} <span class="diff-stat-add">+{{ f.additions }}</span> <span class="diff-stat-del">-{{ f.deletions }}</span>
                    </span>
                  </span>
                  <span class="meta-tests"><span class="test-badge" :class="entry.testResult.badge">{{ entry.testResult.text }}</span></span>
                  <span class="meta-tools">{{ entry.toolCount }} 次工具调用</span>
                </div>
              </div>
            </article>
          </div>
        </div>
      </div>

      <div v-if="store.detailOpen" class="resize-handle visible" aria-hidden="true" @mousedown="onResizeStart" />

      <aside v-if="store.detail && store.detailOpen" data-testid="detail-panel" class="detail-panel open" :style="{ width: store.detailWidth + 'px', minWidth: store.detailWidth + 'px' }" aria-label="任务详情">
        <div class="detail-header">
          <span class="detail-status" :class="detailStatusClass(store.detail.status)">{{ statusLabel(store.detail.status) }}</span>
          <div class="detail-title-group">
            <div class="detail-title">{{ store.detail.title }}</div>
            <div class="detail-meta">
              <span>{{ store.detail.time }}</span>
              <span>· {{ store.detail.duration }}</span>
              <span>· {{ store.detail.toolCount }} 次工具调用</span>
            </div>
          </div>
          <button data-testid="detail-close-btn" class="detail-close" type="button" title="关闭" @click="store.closeDetail()">✕</button>
        </div>

        <div class="detail-scroll">
          <div v-if="store.detail.status === 'fail'" class="fail-alert">
            <div class="fail-alert-title">✕ {{ store.detail.failReason }}</div>
            <div class="fail-alert-body">{{ store.detail.failDetail }}</div>
            <div v-if="store.detail.rejectedCmd" class="fail-alert-cmd">✗ {{ store.detail.rejectedCmd }}</div>
          </div>
          <div v-if="store.detail.status === 'cancelled' && store.detail.cancelInfo" class="cancel-alert">
            <div class="cancel-alert-title">⊘ 用户取消</div>
            <div class="cancel-alert-body">取消发生在<strong>{{ store.detail.cancelInfo.stage }}</strong>。{{ store.detail.cancelInfo.detail }}</div>
          </div>

          <div class="detail-section">
            <div class="detail-section-label">任务摘要</div>
            <div class="detail-summary">{{ store.detail.summary }}</div>
          </div>

          <div class="detail-section">
            <div class="detail-section-label">Agent 计划</div>
            <div class="plan-steps">
              <div v-for="(step, si) in store.detail.plan" :key="si" class="plan-step">
                <div class="step-mark" :class="planStepClass(step.state)">{{ planStepMark(step.state) }}</div>
                <span class="step-label">{{ step.label }}</span>
                <span class="step-tag" :class="'t-' + planStepClass(step.state)">{{ planStepTag(step.state) }}</span>
              </div>
            </div>
          </div>

          <div class="detail-section">
            <div class="detail-section-label">工具调用</div>
            <div class="tool-log">
              <div v-for="(tc, ti) in store.detail.toolCalls" :key="ti" class="tool-line">
                <span class="tool-icon" aria-hidden="true">{{ tc.icon }}</span>
                <span class="tool-name">{{ tc.name }}</span>
                <span class="tool-args">{{ tc.args }}</span>
                <span class="tool-status" :class="tc.ok ? 'ts-ok' : 'ts-fail'">{{ tc.ok ? '✓' : '✕' }}</span>
              </div>
            </div>
          </div>

          <div v-if="store.detail.files.length > 0" class="detail-section">
            <div class="detail-section-label">文件变更</div>
            <div class="file-list">
              <div v-for="(fc, fi) in store.detail.files" :key="fi">
                <div class="file-row" @click="toggleDiff(store.detail!.id + '-' + fi)">
                  <span class="file-name">{{ fc.name }}</span>
                  <span class="file-diff"><span class="diff-stat-add">+{{ fc.additions }}</span><span class="diff-stat-del">-{{ fc.deletions }}</span></span>
                  <span class="file-expand-icon" aria-hidden="true">{{ expandedDiffIds.includes(store.detail.id + '-' + fi) ? '▾' : '▸' }}</span>
                </div>
                <div v-if="expandedDiffIds.includes(store.detail.id + '-' + fi)" class="file-diff-inline show">{{ fc.diff }}</div>
              </div>
            </div>
          </div>

          <div class="detail-section">
            <div class="detail-section-label">审批记录</div>
            <div class="approval-row">
              <span class="approval-dot" :class="'ap-' + store.detail.approval.status" />
              <span>{{ store.detail.approval.text }}</span>
              <span class="approval-time">{{ store.detail.approval.time }}</span>
            </div>
          </div>

          <div class="detail-section">
            <div class="detail-section-label">测试与命令</div>
            <div class="test-block">
              <div class="test-cmd">$ {{ store.detail.test.command }}</div>
              <div class="test-result" :class="testResultClass(store.detail.test.result)">{{ testResultText(store.detail.test.result) }}</div>
              <div class="test-detail">{{ store.detail.test.detail }}</div>
            </div>
          </div>
        </div>

        <div class="detail-footer">
          <button class="detail-close-btn" type="button" @click="store.closeDetail()">关闭</button>
        </div>
      </aside>
    </div>

    <footer class="footer-bar">
      <span class="footer-lock" aria-hidden="true">🔒</span>
      <span class="footer-note-text">会话历史和审批记录仅存储在本机 · 不上传任何数据</span>
    </footer>
  </div>
</template>

<style scoped>
.shell { min-height: 100vh; max-height: 100vh; overflow: hidden; display: flex; flex-direction: column; background: #f5f0e8; color: #2a2a2a; font-family: 'Architects Daughter', cursive; padding: 18px 150px 0; }
* { margin: 0; padding: 0; box-sizing: border-box; }

.top-bar { display: flex; align-items: center; justify-content: space-between; padding-bottom: 12px; border-bottom: 2px solid #2a2a2a; margin-bottom: 14px; flex-shrink: 0; }
.brand { font-family: Caveat, cursive; font-size: 26px; font-weight: 700; color: #1a1a1a; letter-spacing: .5px; transform: rotate(-.4deg); display: flex; align-items: center; gap: 8px; }
.brand-dot { width: 8px; height: 8px; border-radius: 50%; background: #2d7a3a; border: 1.5px solid #2d7a3a; flex-shrink: 0; position: relative; top: -1px; }
.top-right { display: flex; align-items: center; gap: 12px; }
.runtime-badge { font-family: 'JetBrains Mono', monospace; font-size: 10px; color: #2d7a3a; border: 1.5px solid #2d7a3a; border-radius: 4px; padding: 3px 8px; background: rgba(45,122,58,.06); display: flex; align-items: center; gap: 5px; transform: rotate(.2deg); }
.runtime-badge::before { content: ''; width: 5px; height: 5px; border-radius: 50%; background: #2d7a3a; }
.settings-icon { font-family: 'JetBrains Mono', monospace; font-size: 16px; color: #999; cursor: pointer; padding: 4px; line-height: 1; transform: rotate(.3deg); }
.settings-icon:hover { color: #2a2a2a; }

.project-context { display: flex; align-items: center; gap: 10px; margin-bottom: 14px; flex-shrink: 0; padding-bottom: 10px; border-bottom: 1.5px dashed #ccc; }
.back-link { font-family: 'Architects Daughter', cursive; font-size: 13px; color: #6b7d8e; cursor: pointer; display: flex; align-items: center; gap: 4px; }
.back-link:hover { color: #2a2a2a; }
.arrow { font-size: 11px; }
.project-name-inline { font-family: Caveat, cursive; font-size: 18px; font-weight: 700; color: #1a1a1a; transform: rotate(-.2deg); }
.project-path-inline { font-family: 'JetBrains Mono', monospace; font-size: 10px; color: #999; }
.ctx-spacer { flex: 1; }
.status-chip { font-family: 'JetBrains Mono', monospace; font-size: 9px; padding: 2px 7px; border-radius: 3px; display: flex; align-items: center; gap: 4px; }
.status-chip::before { content: ''; width: 5px; height: 5px; border-radius: 50%; flex-shrink: 0; }
.chip-running { color: #2d7a3a; background: rgba(45,122,58,.08); border: 1px solid rgba(45,122,58,.25); }
.chip-running::before { background: #2d7a3a; }

.page-header { margin-bottom: 10px; flex-shrink: 0; }
.page-title { font-family: Caveat, cursive; font-size: 28px; font-weight: 700; color: #1a1a1a; transform: rotate(-.3deg); margin-bottom: 2px; }
.page-subtitle { font-family: 'Patrick Hand', cursive; font-size: 13px; color: #6b7d8e; transform: rotate(-.1deg); }

.search-bar { display: flex; align-items: center; gap: 8px; margin-bottom: 10px; flex-shrink: 0; }
.search-input { flex: 1; padding: 8px 12px; font-family: 'JetBrains Mono', monospace; font-size: 11px; color: #2a2a2a; background: rgba(255,255,255,.5); border: 1.5px solid #d8d0c4; border-radius: 4px; outline: none; }
.search-input:focus { border-color: #6b7d8e; }
.search-input::placeholder { color: #bbb; }

.filter-bar { display: flex; align-items: center; gap: 5px; margin-bottom: 14px; flex-shrink: 0; flex-wrap: wrap; }
.filter-chip { font-family: 'Architects Daughter', cursive; font-size: 12px; padding: 4px 10px; border: 1.5px solid #d8d0c4; border-radius: 4px; background: none; color: #888; cursor: pointer; white-space: nowrap; }
.filter-chip:hover { border-color: #bbb; color: #2a2a2a; }
.filter-chip.active { border-color: #2a2a2a; color: #2a2a2a; background: rgba(0,0,0,.04); font-weight: 600; }
.filter-count { font-family: 'JetBrains Mono', monospace; font-size: 9px; color: #bbb; margin-left: 2px; }

.workbench { flex: 1; min-height: 0; display: flex; gap: 0; }
.task-list-panel { flex: 1; min-width: 0; display: flex; flex-direction: column; overflow: hidden; }
.main-scroll { flex: 1; min-height: 0; overflow-y: auto; padding-right: 4px; scrollbar-width: thin; scrollbar-color: #c5b9a8 rgba(0,0,0,.03); }
.main-scroll::-webkit-scrollbar { width: 5px; }
.main-scroll::-webkit-scrollbar-track { background: rgba(0,0,0,.03); border-radius: 4px; }
.main-scroll::-webkit-scrollbar-thumb { background: #c5b9a8; border-radius: 4px; border: 1px solid rgba(0,0,0,.06); }
.main-scroll::-webkit-scrollbar-thumb:hover { background: #a99e8d; }

.timeline { display: flex; flex-direction: column; gap: 0; position: relative; }
.timeline::before { content: ''; position: absolute; left: 11px; top: 0; bottom: 0; width: 2px; background: repeating-linear-gradient(to bottom, #d8d0c4 0px, #d8d0c4 4px, transparent 4px, transparent 8px); }

.task-entry { display: flex; gap: 14px; padding: 10px 0; position: relative; cursor: pointer; }
.task-entry:hover { background: rgba(0,0,0,.015); }
.task-entry.active-entry { background: rgba(0,0,0,.03); }
.task-entry.primary { border: 2.5px solid #c87020; border-radius: 6px; background: rgba(212,160,23,.04); padding: 12px 16px; transform: rotate(-.15deg); margin-bottom: 4px; }
.task-entry.secondary { border: 1.5px solid #e0d8cc; border-radius: 5px; background: rgba(255,255,255,.15); padding: 10px 14px; margin-bottom: 4px; }
.task-entry.secondary.fail-entry { border-color: rgba(184,48,48,.25); background: rgba(184,48,48,.02); }
.task-entry.secondary.cancelled-entry { border-style: dashed; border-color: #d8d0c4; opacity: .7; }

.tl-dot-col { flex-shrink: 0; width: 24px; display: flex; justify-content: center; padding-top: 6px; position: relative; z-index: 1; }
.tl-dot { width: 10px; height: 10px; border-radius: 50%; border: 2px solid #2a2a2a; background: #f5f0e8; flex-shrink: 0; }
.tl-dot.waiting { background: #c87020; border-color: #c87020; }
.tl-dot.done { background: #2d7a3a; border-color: #2d7a3a; }
.tl-dot.fail { background: #b83030; border-color: #b83030; }
.tl-dot.cancelled { background: #bbb; border-color: #bbb; border-style: dashed; }

.entry-body { flex: 1; min-width: 0; }
.entry-header { display: flex; align-items: center; gap: 8px; margin-bottom: 4px; flex-wrap: wrap; }
.entry-status { font-family: 'JetBrains Mono', monospace; font-size: 9px; padding: 1px 6px; border-radius: 3px; display: flex; align-items: center; gap: 4px; flex-shrink: 0; }
.entry-status::before { content: ''; width: 5px; height: 5px; border-radius: 50%; flex-shrink: 0; }
.s-waiting { color: #c87020; background: rgba(212,160,23,.1); border: 1px solid rgba(200,112,32,.3); }.s-waiting::before { background: #c87020; }
.s-done { color: #2d7a3a; background: rgba(45,122,58,.08); border: 1px solid rgba(45,122,58,.25); }.s-done::before { background: #2d7a3a; }
.s-fail { color: #b83030; background: rgba(184,48,48,.06); border: 1px solid rgba(184,48,48,.2); }.s-fail::before { background: #b83030; }
.s-cancelled { color: #6b7d8e; background: rgba(107,125,142,.06); border: 1px solid rgba(107,125,142,.2); }.s-cancelled::before { background: #bbb; }
.entry-time { font-family: 'JetBrains Mono', monospace; font-size: 9px; color: #aaa; flex-shrink: 0; }
.entry-duration { font-family: 'JetBrains Mono', monospace; font-size: 9px; color: #ccc; flex-shrink: 0; }
.entry-spacer { flex: 1; }
.entry-task { font-family: Caveat, cursive; font-size: 17px; font-weight: 700; color: #1a1a1a; margin-bottom: 3px; transform: rotate(-.15deg); line-height: 1.3; }
.task-entry.secondary .entry-task { font-size: 15px; }
.entry-summary { font-family: 'Architects Daughter', cursive; font-size: 12px; color: #555; line-height: 1.5; margin-bottom: 5px; }
.entry-meta { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.meta-files { font-family: 'JetBrains Mono', monospace; font-size: 10px; color: #3a6090; display: flex; align-items: center; gap: 4px; flex-wrap: wrap; }
.file-chip { padding: 1px 5px; border: 1px solid rgba(58,96,144,.25); border-radius: 3px; background: rgba(58,96,144,.04); white-space: nowrap; }
.diff-stat-add { color: #2d7a3a; font-weight: 500; }
.diff-stat-del { color: #b83030; font-weight: 500; }
.meta-tests { font-family: 'JetBrains Mono', monospace; font-size: 10px; display: flex; align-items: center; gap: 4px; }
.test-badge { padding: 1px 5px; border-radius: 3px; }
.test-badge.pass { color: #2d7a3a; background: rgba(45,122,58,.08); border: 1px solid rgba(45,122,58,.2); }
.test-badge.fail { color: #b83030; background: rgba(184,48,48,.06); border: 1px solid rgba(184,48,48,.15); }
.test-badge.none { color: #bbb; background: rgba(0,0,0,.02); border: 1px solid #e0d8cc; }
.meta-tools { font-family: 'JetBrains Mono', monospace; font-size: 9px; color: #bbb; }

.entry-action { font-family: Caveat, cursive; font-size: 14px; font-weight: 600; padding: 5px 12px; border: 2px solid #2a2a2a; border-radius: 4px; background: none; color: #2a2a2a; cursor: pointer; white-space: nowrap; flex-shrink: 0; transform: rotate(-.3deg); align-self: flex-start; margin-top: 2px; }
.entry-action:hover { background: rgba(0,0,0,.04); }
.action-review { border-color: #c87020; color: #c87020; background: rgba(212,160,23,.1); font-weight: 700; }
.action-review:hover { background: rgba(212,160,23,.18); }
.action-fail-detail { border-color: #b83030; color: #b83030; }
.action-fail-detail:hover { background: rgba(184,48,48,.06); }

.resize-handle { width: 8px; cursor: col-resize; flex-shrink: 0; display: flex; align-items: center; justify-content: center; opacity: 0; position: relative; z-index: 5; }
.resize-handle.visible { opacity: 1; }
.resize-handle::after { content: ''; width: 2px; height: 40px; border-radius: 1px; background: #ccc; }
.resize-handle:hover::after { background: #c87020; }

.detail-panel { width: 0; min-width: 0; border: none; border-radius: 0; padding: 0; background: none; overflow: hidden; display: flex; flex-direction: column; flex-shrink: 0; }
.detail-panel.open { border: 2px solid #2a2a2a; border-radius: 6px; padding: 10px 14px; background: rgba(255,255,255,.25); }

.detail-header { display: flex; align-items: flex-start; gap: 10px; padding-bottom: 10px; border-bottom: 1.5px dashed #d8d0c4; flex-shrink: 0; }
.detail-status { font-family: 'JetBrains Mono', monospace; font-size: 10px; padding: 2px 8px; border-radius: 3px; display: flex; align-items: center; gap: 4px; flex-shrink: 0; margin-top: 2px; }
.detail-status::before { content: ''; width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0; }
.ds-done { color: #2d7a3a; background: rgba(45,122,58,.08); border: 1px solid rgba(45,122,58,.25); }.ds-done::before { background: #2d7a3a; }
.ds-fail { color: #b83030; background: rgba(184,48,48,.06); border: 1px solid rgba(184,48,48,.2); }.ds-fail::before { background: #b83030; }
.ds-cancelled { color: #6b7d8e; background: rgba(107,125,142,.06); border: 1px solid rgba(107,125,142,.2); }.ds-cancelled::before { background: #bbb; }
.detail-title-group { flex: 1; min-width: 0; }
.detail-title { font-family: Caveat, cursive; font-size: 18px; font-weight: 700; color: #1a1a1a; transform: rotate(-.2deg); line-height: 1.3; }
.detail-meta { font-family: 'JetBrains Mono', monospace; font-size: 9px; color: #aaa; margin-top: 3px; display: flex; gap: 8px; }
.detail-close { font-family: 'JetBrains Mono', monospace; font-size: 16px; color: #999; cursor: pointer; padding: 3px 5px; line-height: 1; border: 1.5px solid #d8d0c4; border-radius: 4px; background: none; flex-shrink: 0; }
.detail-close:hover { color: #2a2a2a; border-color: #bbb; background: rgba(0,0,0,.03); }

.detail-scroll { flex: 1; overflow-y: auto; padding-top: 12px; scrollbar-width: thin; scrollbar-color: #c5b9a8 transparent; }
.detail-scroll::-webkit-scrollbar { width: 4px; }
.detail-scroll::-webkit-scrollbar-thumb { background: #c5b9a8; border-radius: 4px; }
.detail-section { margin-bottom: 14px; }
.detail-section-label { font-family: 'JetBrains Mono', monospace; font-size: 9px; text-transform: uppercase; letter-spacing: 1.5px; color: #6b7d8e; margin-bottom: 6px; padding-bottom: 4px; border-bottom: 1px dashed #e0d8cc; }
.detail-summary { font-family: 'Architects Daughter', cursive; font-size: 12px; color: #444; line-height: 1.6; }

.fail-alert { border: 2px solid #b83030; border-radius: 5px; background: rgba(184,48,48,.04); padding: 10px 12px; margin-bottom: 12px; }
.fail-alert-title { font-family: Caveat, cursive; font-size: 15px; font-weight: 700; color: #b83030; margin-bottom: 4px; }
.fail-alert-body { font-family: 'Architects Daughter', cursive; font-size: 12px; color: #555; line-height: 1.5; }
.fail-alert-cmd { font-family: 'JetBrains Mono', monospace; font-size: 10px; color: #b83030; background: rgba(184,48,48,.06); border: 1px solid rgba(184,48,48,.15); border-radius: 3px; padding: 3px 6px; margin-top: 6px; display: inline-block; }
.cancel-alert { border: 1.5px dashed #6b7d8e; border-radius: 5px; background: rgba(107,125,142,.04); padding: 10px 12px; margin-bottom: 12px; }
.cancel-alert-title { font-family: Caveat, cursive; font-size: 15px; font-weight: 700; color: #6b7d8e; margin-bottom: 4px; }
.cancel-alert-body { font-family: 'Architects Daughter', cursive; font-size: 12px; color: #555; line-height: 1.5; }

.plan-steps { display: flex; flex-direction: column; gap: 3px; }
.plan-step { display: flex; align-items: center; gap: 6px; font-family: 'Architects Daughter', cursive; font-size: 12px; color: #555; padding: 3px 0; }
.step-mark { width: 14px; height: 14px; border: 1.5px solid #2a2a2a; border-radius: 3px; display: flex; align-items: center; justify-content: center; font-size: 9px; flex-shrink: 0; background: rgba(255,255,255,.5); }
.step-mark.done { background: rgba(45,122,58,.15); border-color: #2d7a3a; color: #2d7a3a; }
.step-mark.fail { background: rgba(184,48,48,.1); border-color: #b83030; color: #b83030; }
.step-mark.waiting { background: rgba(212,160,23,.1); border-color: #c87020; color: #c87020; }
.step-mark.pending { color: #ccc; }
.step-label { flex: 1; }
.step-tag { font-family: 'JetBrains Mono', monospace; font-size: 8px; padding: 1px 4px; border-radius: 2px; flex-shrink: 0; }
.t-done { color: #2d7a3a; background: rgba(45,122,58,.08); }
.t-fail { color: #b83030; background: rgba(184,48,48,.06); }
.t-waiting { color: #c87020; background: rgba(212,160,23,.08); }
.t-pending { color: #ccc; background: rgba(0,0,0,.02); }

.tool-log { display: flex; flex-direction: column; gap: 2px; }
.tool-line { display: flex; align-items: center; gap: 6px; font-family: 'JetBrains Mono', monospace; font-size: 10px; padding: 3px 6px; border-radius: 3px; color: #555; background: rgba(255,255,255,.25); border: 1px solid #eee; }
.tool-icon { font-size: 9px; flex-shrink: 0; width: 14px; text-align: center; }
.tool-name { color: #3a6090; font-weight: 500; }
.tool-args { color: #999; flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.tool-status { font-size: 9px; flex-shrink: 0; }
.ts-ok { color: #2d7a3a; }
.ts-fail { color: #b83030; }

.file-list { display: flex; flex-direction: column; gap: 4px; }
.file-row { display: flex; align-items: center; gap: 8px; font-family: 'JetBrains Mono', monospace; font-size: 10px; padding: 5px 8px; border: 1px solid #e0d8cc; border-radius: 4px; background: rgba(255,255,255,.2); cursor: pointer; }
.file-row:hover { background: rgba(255,255,255,.45); }
.file-name { color: #3a6090; font-weight: 500; flex: 1; }
.file-diff { display: flex; gap: 4px; flex-shrink: 0; }
.file-diff span { font-weight: 500; }
.file-expand-icon { color: #ccc; font-size: 9px; flex-shrink: 0; }
.file-diff-inline { margin-top: 4px; padding: 6px 8px; border: 1px solid #e0d8cc; border-radius: 3px; background: rgba(0,0,0,.02); font-family: 'JetBrains Mono', monospace; font-size: 9px; line-height: 1.6; color: #555; white-space: pre; overflow-x: auto; }
.file-diff-inline.show { display: block; }

.approval-row { display: flex; align-items: center; gap: 8px; font-family: 'Architects Daughter', cursive; font-size: 12px; padding: 6px 0; color: #555; }
.approval-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.ap-approved { background: #2d7a3a; }
.ap-rejected { background: #b83030; }
.ap-none { background: #ccc; border: 1.5px dashed #bbb; }
.approval-time { font-family: 'JetBrains Mono', monospace; font-size: 9px; color: #aaa; margin-left: auto; }

.test-block { border: 1.5px solid #e0d8cc; border-radius: 4px; padding: 8px 10px; background: rgba(255,255,255,.2); }
.test-cmd { font-family: 'JetBrains Mono', monospace; font-size: 10px; color: #6b7d8e; margin-bottom: 4px; }
.test-result { font-family: Caveat, cursive; font-size: 16px; font-weight: 700; }
.tr-pass { color: #2d7a3a; }
.tr-fail { color: #b83030; }
.tr-none { color: #bbb; }
.test-detail { font-family: 'JetBrains Mono', monospace; font-size: 9px; color: #999; margin-top: 2px; }

.detail-footer { flex-shrink: 0; padding-top: 10px; border-top: 1.5px dashed #d8d0c4; margin-top: 10px; display: flex; justify-content: flex-end; }
.detail-close-btn { font-family: Caveat, cursive; font-size: 14px; font-weight: 600; padding: 6px 16px; border: 1.5px solid #d8d0c4; border-radius: 4px; background: none; color: #888; cursor: pointer; }
.detail-close-btn:hover { border-color: #bbb; color: #2a2a2a; background: rgba(0,0,0,.03); }

.footer-bar { flex-shrink: 0; padding: 10px 0 14px; border-top: 1.5px dashed #d8d0c4; margin-top: 10px; display: flex; align-items: center; justify-content: center; gap: 5px; }
.footer-lock { font-size: 10px; color: #ccc; }
.footer-note-text { font-family: 'JetBrains Mono', monospace; font-size: 9px; color: #bbb; }

@media (max-width: 900px) { .detail-panel.open { width: 80vw !important; min-width: 0 !important; max-width: none !important; } }
@media (max-width: 640px) { .shell { padding: 12px 24px 0; } }
</style>
