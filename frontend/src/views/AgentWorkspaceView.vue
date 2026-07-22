<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAgentStore } from '@/stores/agent.store'

const route = useRoute()
const router = useRouter()
const store = useAgentStore()
const drawerOpen = ref(false)
const drawerTab = ref<'diff' | 'file' | 'test'>('diff')
const expandedToolIds = ref<string[]>([])
const drawerWidth = ref(500)
const isResizing = ref(false)

const task = computed(() => store.task)
const isPending = computed(() => task.value?.changeSet.status === 'pending')

onMounted(() => store.load())

function toggleTool(id: string) {
  expandedToolIds.value = expandedToolIds.value.includes(id)
    ? expandedToolIds.value.filter((toolId) => toolId !== id)
    : [...expandedToolIds.value, id]
}

function openDrawer(tab: 'diff' | 'file' | 'test' = 'diff') {
  drawerTab.value = tab
  drawerOpen.value = true
}

function startResize(event: MouseEvent) {
  isResizing.value = true
  const onMove = (moveEvent: MouseEvent) => {
    drawerWidth.value = Math.min(Math.max(window.innerWidth - moveEvent.clientX, 320), Math.round(window.innerWidth * 0.55))
  }
  const onUp = () => {
    isResizing.value = false
    window.removeEventListener('mousemove', onMove)
    window.removeEventListener('mouseup', onUp)
  }
  window.addEventListener('mousemove', onMove)
  window.addEventListener('mouseup', onUp)
  event.preventDefault()
}

async function goToHistory() {
  await router.push(`/workspace/${route.params.id}/history`)
}

async function approve() {
  await store.approveCurrentChangeSet()
  drawerTab.value = 'test'
}
</script>

<template>
  <main class="workspace-shell" :class="{ resizing: isResizing }">
    <aside class="sidebar" aria-label="工作区导航">
      <div class="wordmark">LightCode</div>
      <div class="workspace-path">{{ store.workspace?.rootPath }}</div>

      <section class="sidebar-block">
        <h2>文件</h2>
        <button v-for="file in store.workspace?.files" :key="file.id" class="file-row" type="button">
          <span aria-hidden="true">{{ file.kind === 'directory' ? '▸' : '·' }}</span>{{ file.name }}
        </button>
      </section>

      <section class="sessions sidebar-block">
        <h2>会话</h2>
        <button v-for="session in store.sessions" :key="session.id" class="session-row" :class="{ active: session.id === store.activeSessionId }" type="button">
          <span class="session-dot" :class="session.status" aria-hidden="true" />{{ session.title }}
        </button>
      </section>
      <button data-testid="task-history-link" class="settings-link history-link" type="button" @click="goToHistory">📋 历史记录</button>
      <button class="settings-link" type="button">设置</button>
    </aside>

    <section v-if="task" class="execution-panel" aria-label="Agent Workspace">
      <header class="task-header">
        <p class="eyebrow">● 当前任务 · {{ isPending ? '等待审批' : '验证已完成' }}</p>
        <h1>{{ task.title }}</h1>
      </header>

      <section class="plan" aria-label="Agent 计划">
        <p class="section-kicker">Agent 计划</p>
        <ol>
          <li v-for="(step, index) in task.plan" :key="step.id">
            <span class="step-state" :class="step.status">{{ step.status === 'completed' ? '✓' : step.status === 'current' ? '•' : '' }}</span>
            <span class="step-number">{{ index + 1 }}</span>
            <span>{{ step.label }}<strong v-if="step.status === 'current' && isPending"> · 待审批</strong></span>
          </li>
        </ol>
      </section>

      <section class="tool-log" aria-label="工具调用">
        <article v-for="tool in task.toolCalls" :key="tool.id" class="tool-entry">
          <button :data-testid="tool.id" class="tool-row" :class="{ expanded: expandedToolIds.includes(tool.id) }" type="button" @click="toggleTool(tool.id)">
            <span class="tool-status" :class="tool.status" aria-hidden="true" />
            <strong>{{ tool.toolName }}</strong>
            <span class="tool-target">{{ tool.target }}</span>
            <time>{{ tool.duration }}</time>
            <span aria-hidden="true">{{ expandedToolIds.includes(tool.id) ? '⌄' : '›' }}</span>
          </button>
          <pre v-if="expandedToolIds.includes(tool.id)" class="tool-detail"><code v-for="line in tool.detail" :key="line" :class="{ addition: line.startsWith('+'), deletion: line.startsWith('-') }">{{ line }}
</code></pre>
        </article>
      </section>

      <section class="agent-output">
        <p class="section-kicker">Agent 输出</p>
        <p>{{ task.modelOutput }}</p>
      </section>

      <footer class="command-bar">
        <template v-if="isPending">
          <span class="pending-marker">●</span>
          <span>Diff 等待审批 · {{ task.changeSet.filePath }} +{{ task.changeSet.additions }} -{{ task.changeSet.deletions }}</span>
          <button aria-label="审查修改" class="review-button" type="button" @click="drawerOpen ? (drawerOpen = false) : openDrawer()">审查修改</button>
          <button class="reject-button" type="button">拒绝并输入反馈</button>
        </template>
        <template v-else>
          <span class="passed-marker">●</span>
          <span>验证已完成 · {{ task.verification.command }}</span>
          <button aria-label="查看测试" class="review-button" type="button" @click="openDrawer('test')">查看测试</button>
        </template>
      </footer>
    </section>

    <div v-if="drawerOpen" class="resize-handle" aria-hidden="true" @mousedown="startResize" />
    <aside v-if="drawerOpen && task" data-testid="review-drawer" class="review-drawer" :style="{ width: `${drawerWidth}px` }" aria-label="代码审查">
      <header class="drawer-header">
        <h2>代码审查</h2>
        <button aria-label="关闭审查" type="button" @click="drawerOpen = false">×</button>
      </header>
      <nav class="drawer-tabs" aria-label="审查内容">
        <button :class="{ active: drawerTab === 'diff' }" type="button" @click="drawerTab = 'diff'">Diff</button>
        <button :class="{ active: drawerTab === 'file' }" type="button" @click="drawerTab = 'file'">文件</button>
        <button :class="{ active: drawerTab === 'test' }" type="button" @click="drawerTab = 'test'">测试</button>
      </nav>
      <section v-if="drawerTab === 'diff'" class="drawer-content diff-view">
        <p class="drawer-label">{{ task.changeSet.filePath }} · 左右对比</p>
        <div class="diff-columns">
          <pre><code v-for="(line, index) in task.changeSet.before" :key="line" :class="{ deletion: index === 1 }"><i>{{ index + 1 }}</i>{{ line }}
</code></pre>
          <pre><code v-for="(line, index) in task.changeSet.after" :key="line" :class="{ addition: index < 6 }"><i>{{ index + 1 }}</i>{{ line }}
</code></pre>
        </div>
      </section>
      <section v-else-if="drawerTab === 'file'" class="drawer-content">
        <p class="drawer-label">{{ task.changeSet.filePath }} · 完整文件</p>
        <pre class="code-surface"><code v-for="(line, index) in task.changeSet.before" :key="line"><i>{{ index + 1 }}</i>{{ line }}
</code></pre>
      </section>
      <section v-else class="drawer-content">
        <p class="drawer-label">test_login.py · 测试输出</p>
        <pre class="code-surface test-surface">{{ task.verification.lines.join('\n') }}
{{ task.verification.command }}</pre>
      </section>
      <footer v-if="isPending" class="approval-area">
        <p>需要审批后才能写入文件</p>
        <div>
          <button aria-label="批准修改" class="approve-button" type="button" @click="approve">批准修改</button>
          <button class="reject-button" type="button">拒绝 · 附带反馈</button>
        </div>
      </footer>
    </aside>
  </main>
</template>
