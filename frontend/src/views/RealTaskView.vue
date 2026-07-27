<script setup lang="ts">
import { computed, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { isApiMode } from '@/config/runtime'
import { useRealStore } from '@/stores/real.store'
import type { RealTaskState } from '@/types/agent'

const route = useRoute()
const router = useRouter()
const store = useRealStore()

const workspaceId = computed(() => route.params.id as string)
const taskId = computed(() => route.params.taskId as string)

onMounted(() => {
  if (store.task?.id !== taskId.value) {
    store.loadTask(taskId.value)
  }
})
onUnmounted(() => store.cleanup())

const task = computed(() => store.task)
const changeSet = computed(() => store.task?.changeSet ?? null)
const canDecide = computed(
  () => task.value?.state === 'awaiting_approval' && changeSet.value?.status === 'active',
)

const stateLabels: Record<RealTaskState, string> = {
  awaiting_approval: '等待审批',
  applying_change: '写入中',
  completed: '已完成',
  failed: '失败',
  cancelled: '已拒绝',
}

function shortHash(hash: string): string {
  return hash.length > 16 ? `${hash.slice(0, 16)}…` : hash
}
</script>

<template>
  <div class="real-task-page">
    <header class="top-bar">
      <button class="back-btn" type="button" data-testid="back-real-ws-btn" @click="router.push(`/real/${workspaceId}`)">← 返回工作区</button>
      <div class="brand">真实任务</div>
      <span v-if="task" class="state-badge" :class="task.state" data-testid="task-state">{{ stateLabels[task.state] }}</span>
    </header>

    <div v-if="store.error" class="error-banner" data-testid="real-error">{{ store.error }}</div>

    <main v-if="task" class="task-body">
      <section class="panel">
        <h1 class="task-title">{{ task.title }}</h1>
        <div class="meta-grid">
          <span class="meta-key">任务 ID</span><span class="meta-val">{{ task.id }}</span>
          <span class="meta-key">目标文件</span><span class="meta-val">{{ task.targetFile ?? '—' }}</span>
          <span class="meta-key">创建时间</span><span class="meta-val">{{ task.createdAt }}</span>
        </div>
      </section>

      <section class="panel" aria-label="执行计划">
        <p class="panel-kicker">执行计划</p>
        <ol class="plan-list">
          <li v-for="step in task.plan" :key="step.id" :class="step.status">
            <span class="step-mark">{{ step.status === 'completed' ? '✓' : step.status === 'current' ? '•' : '○' }}</span>
            {{ step.label }}
          </li>
        </ol>
      </section>

      <section v-if="changeSet" class="panel" aria-label="变更集">
        <p class="panel-kicker">变更集（服务端生成 · 版本绑定）</p>
        <div class="cs-summary" data-testid="changeset-summary">
          <span class="cs-path">{{ changeSet.logicalRelativePath }}</span>
          <span class="cs-add">+{{ changeSet.additions }}</span>
          <span class="cs-del">-{{ changeSet.deletions }}</span>
          <span class="cs-status" :class="changeSet.status">{{ changeSet.status }}</span>
        </div>
        <div class="meta-grid">
          <span class="meta-key">changeSetId</span><span class="meta-val">{{ changeSet.changeSetId }}</span>
          <span class="meta-key">revision</span><span class="meta-val">{{ changeSet.revision }}</span>
          <span class="meta-key">diffHash</span><span class="meta-val">{{ shortHash(changeSet.diffHash) }}</span>
          <span class="meta-key">有效期至</span><span class="meta-val">{{ changeSet.expiresAt || '不限' }}</span>
        </div>
        <div class="diff-columns">
          <div>
            <p class="diff-label">变更前</p>
            <pre class="code-surface"><code v-for="(line, idx) in changeSet.before" :key="`b-${idx}`"><i>{{ idx + 1 }}</i>{{ line }}
</code></pre>
          </div>
          <div>
            <p class="diff-label">变更后</p>
            <pre class="code-surface"><code v-for="(line, idx) in changeSet.after" :key="`a-${idx}`" :class="{ addition: idx >= changeSet.before.length }"><i>{{ idx + 1 }}</i>{{ line }}
</code></pre>
          </div>
        </div>
      </section>

      <section class="panel" aria-label="验证结果">
        <p class="panel-kicker">写入验证</p>
        <div class="verify-row" data-testid="verification-status">
          <span class="verify-badge" :class="task.verification.status">{{ task.verification.status }}</span>
          <span class="verify-cmd">{{ task.verification.command }}</span>
        </div>
        <pre v-if="task.verification.lines.length" class="code-surface">{{ task.verification.lines.join('\n') }}</pre>
      </section>

      <section class="panel" aria-label="事件流">
        <p class="panel-kicker">事件流（SSE · 支持断点续传）</p>
        <template v-if="isApiMode">
          <div v-for="event in store.events" :key="event.sequence" class="event-row" data-testid="task-event">
            <span class="event-seq">#{{ event.sequence }}</span>
            <span class="event-type">{{ event.eventType }}</span>
            <span class="event-time">{{ event.createdAt }}</span>
          </div>
          <p v-if="store.events.length === 0" class="empty-hint">暂无事件</p>
        </template>
        <p v-else class="empty-hint">Mock 演示模式下不连接事件流；API 模式将回放持久化事件</p>
      </section>

      <footer v-if="canDecide" class="approval-bar" data-testid="approval-bar">
        <p>审批后服务端将重检基线哈希并原子写入；拒绝则不接触任何文件</p>
        <div class="approval-actions">
          <button
            class="approve-btn"
            type="button"
            data-testid="approve-btn"
            :disabled="store.submitting"
            @click="store.submitDecision('approve')"
          >{{ store.submitting ? '提交中…' : '批准写入' }}</button>
          <button
            class="reject-btn"
            type="button"
            data-testid="reject-btn"
            :disabled="store.submitting"
            @click="store.submitDecision('reject')"
          >拒绝</button>
        </div>
      </footer>
      <footer v-else-if="task.state === 'completed'" class="result-bar ok" data-testid="result-bar">
        ✓ 变更已原子写入并通过内建完整性验证
      </footer>
      <footer v-else-if="task.state === 'cancelled'" class="result-bar rejected" data-testid="result-bar">
        ✕ 变更已拒绝，未接触任何文件
      </footer>
      <footer v-else-if="task.state === 'failed'" class="result-bar fail" data-testid="result-bar">
        ✕ 写入失败：{{ task.verification.lines.join(' ') || '详见事件流' }}
      </footer>
    </main>

    <p v-else-if="store.loading" class="empty-hint loading-hint">加载中…</p>
  </div>
</template>

<style scoped>
.real-task-page {
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
.state-badge {
  font-family: 'JetBrains Mono', monospace; font-size: 10px;
  padding: 3px 10px; border-radius: 4px;
}
.state-badge.awaiting_approval { color: #c87020; border: 1px solid rgba(200,112,32,.3); background: rgba(212,160,23,.1); }
.state-badge.applying_change { color: #2d5a7a; border: 1px solid rgba(45,90,122,.3); background: rgba(45,90,122,.06); }
.state-badge.completed { color: #2d7a3a; border: 1px solid rgba(45,122,58,.3); background: rgba(45,122,58,.06); }
.state-badge.failed, .state-badge.cancelled { color: #b83030; border: 1px solid rgba(184,48,48,.25); background: rgba(184,48,48,.04); }
.error-banner {
  border: 1.5px solid rgba(184,48,48,.35); background: rgba(184,48,48,.05);
  color: #b83030; border-radius: 5px; padding: 10px 14px; margin-bottom: 14px; font-size: 13px;
}
.task-body { max-width: 900px; }
.panel {
  border: 1.5px solid #d8d0c4; border-radius: 6px;
  background: rgba(255,255,255,.25); padding: 14px 18px; margin-bottom: 14px;
}
.panel-kicker {
  font-family: 'JetBrains Mono', monospace; font-size: 10px;
  text-transform: uppercase; letter-spacing: 1.5px; color: #aaa; margin-bottom: 10px;
}
.task-title { font-family: 'Caveat', cursive; font-size: 26px; margin-bottom: 10px; }
.meta-grid {
  display: grid; grid-template-columns: 110px 1fr; gap: 4px 12px; margin-top: 8px;
}
.meta-key { font-family: 'JetBrains Mono', monospace; font-size: 11px; color: #888; }
.meta-val { font-family: 'JetBrains Mono', monospace; font-size: 11px; color: #2a2a2a; word-break: break-all; }
.plan-list { list-style: none; display: flex; flex-direction: column; gap: 6px; }
.plan-list li { display: flex; align-items: baseline; gap: 8px; font-size: 13px; color: #555; }
.plan-list li.completed { color: #2d7a3a; }
.plan-list li.current { color: #c87020; font-weight: 600; }
.step-mark { width: 16px; flex-shrink: 0; }
.cs-summary { display: flex; align-items: center; gap: 10px; margin-bottom: 6px; }
.cs-path { font-family: 'JetBrains Mono', monospace; font-size: 13px; font-weight: 500; }
.cs-add { color: #2d7a3a; font-family: 'JetBrains Mono', monospace; font-size: 12px; }
.cs-del { color: #b83030; font-family: 'JetBrains Mono', monospace; font-size: 12px; }
.cs-status { font-family: 'JetBrains Mono', monospace; font-size: 10px; padding: 2px 8px; border-radius: 3px; border: 1px solid #d8d0c4; color: #888; }
.cs-status.active { color: #c87020; border-color: rgba(200,112,32,.3); }
.cs-status.applied { color: #2d7a3a; border-color: rgba(45,122,58,.3); }
.cs-status.rejected, .cs-status.failed { color: #b83030; border-color: rgba(184,48,48,.25); }
.diff-columns { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-top: 12px; }
.diff-label { font-family: 'JetBrains Mono', monospace; font-size: 10px; color: #aaa; margin-bottom: 6px; }
.code-surface {
  font-family: 'JetBrains Mono', monospace; font-size: 12px; line-height: 1.6;
  background: rgba(0,0,0,.03); border: 1px dashed #e0d8cc; border-radius: 4px;
  padding: 10px 12px; overflow-x: auto;
}
.code-surface code { display: block; white-space: pre; }
.code-surface code i {
  display: inline-block; width: 28px; color: #bbb; font-style: normal; user-select: none;
}
.code-surface code.addition { background: rgba(45,122,58,.08); }
.verify-row { display: flex; align-items: center; gap: 10px; margin-bottom: 8px; }
.verify-badge { font-family: 'JetBrains Mono', monospace; font-size: 10px; padding: 2px 8px; border-radius: 3px; border: 1px solid #d8d0c4; color: #888; }
.verify-badge.passed { color: #2d7a3a; border-color: rgba(45,122,58,.3); }
.verify-badge.failed { color: #b83030; border-color: rgba(184,48,48,.25); }
.verify-badge.running { color: #2d5a7a; border-color: rgba(45,90,122,.3); }
.verify-cmd { font-family: 'JetBrains Mono', monospace; font-size: 12px; color: #555; }
.event-row { display: flex; gap: 10px; font-family: 'JetBrains Mono', monospace; font-size: 11px; padding: 3px 0; }
.event-seq { color: #aaa; width: 40px; flex-shrink: 0; }
.event-type { color: #2a2a2a; }
.event-time { color: #bbb; margin-left: auto; }
.approval-bar {
  border: 2px solid #c87020; border-radius: 6px;
  background: rgba(212,160,23,.06); padding: 14px 18px;
  display: flex; align-items: center; gap: 16px; flex-wrap: wrap;
}
.approval-bar p { font-size: 13px; color: #555; flex: 1; min-width: 240px; }
.approval-actions { display: flex; gap: 10px; }
.approve-btn {
  font-family: inherit; font-size: 14px; cursor: pointer;
  border: 1.5px solid #2d7a3a; border-radius: 4px; padding: 8px 18px;
  background: rgba(45,122,58,.1); color: #2d7a3a; font-weight: 600;
}
.reject-btn {
  font-family: inherit; font-size: 14px; cursor: pointer;
  border: 1.5px solid #b83030; border-radius: 4px; padding: 8px 18px;
  background: rgba(184,48,48,.05); color: #b83030;
}
.approve-btn:disabled, .reject-btn:disabled { opacity: .5; cursor: not-allowed; }
.result-bar { border-radius: 6px; padding: 12px 18px; font-size: 14px; }
.result-bar.ok { border: 1.5px solid rgba(45,122,58,.3); background: rgba(45,122,58,.05); color: #2d7a3a; }
.result-bar.rejected, .result-bar.fail { border: 1.5px solid rgba(184,48,48,.25); background: rgba(184,48,48,.03); color: #b83030; }
.empty-hint { color: #999; font-size: 12px; }
.loading-hint { padding: 20px; }
</style>
