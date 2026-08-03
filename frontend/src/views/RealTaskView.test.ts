import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter, type Router } from 'vue-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { modelTaskFixture, modelTaskEventsFixture } from '@/fixtures/phase1.fixture'
import { useRealStore } from '@/stores/real.store'
import RealTaskView from './RealTaskView.vue'

function createTestRouter(): Router {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', name: 'home', component: { template: '<div>home</div>' } },
      { path: '/real/:id', name: 'real-workspace', component: { template: '<div>ws</div>' } },
      { path: '/real/:id/task/:taskId', name: 'real-task', component: RealTaskView },
    ],
  })
}

function providerHealthMock(status: 'ready' | 'degraded') {
  return {
    status,
    provider: 'openai-compatible',
    modelId: 'x',
    detail: status,
    capabilities: {
      tools: ['read_file'],
      canWriteFiles: false,
      canRunCommands: false,
      maxToolRounds: 8,
      maxRequestsPerTask: 10,
      maxInputBytes: 262144,
      maxOutputTokens: 2048,
      maxConcurrentTasks: 1,
    },
    security: {
      apiKeyConfigured: true,
      transport: 'https',
      originAllowlisted: true,
      followRedirects: false,
      trustEnvProxies: false,
    },
  }
}

describe('RealTaskView 模型任务（WP7）', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  async function mountModelTask() {
    const router = createTestRouter()
    await router.push(`/real/demo-real-workspace/task/${modelTaskFixture.id}`)
    await router.isReady()
    const wrapper = mount(RealTaskView, { global: { plugins: [router] } })
    await flushPromises()
    return { wrapper, router }
  }

  it('renders model task with kind badge', async () => {
    const { wrapper } = await mountModelTask()
    expect(wrapper.get('[data-testid="task-kind"]').text()).toBe('模型任务')
    expect(wrapper.get('[data-testid="task-state"]').text()).toBe('等待审批')
  })

  it('renders model lifecycle timeline from SSE events + policy version + no-external-commands', async () => {
    const { wrapper } = await mountModelTask()
    const store = useRealStore()
    store.events = structuredClone(modelTaskEventsFixture)
    await flushPromises()

    const lifecycle = wrapper.get('[data-testid="model-lifecycle"]')
    expect(lifecycle.text()).toContain('规划变更')
    expect(lifecycle.text()).toContain('读取目标文件')
    expect(lifecycle.text()).toContain('生成候选变更集')
    expect(lifecycle.text()).toContain('等待审批')
    expect(wrapper.get('[data-testid="cs-policy-version"]').text()).toBe('policy-v1')
    expect(wrapper.get('[data-testid="no-external-cmd"]').exists()).toBe(true)
  })

  it('shows actionable, non-sensitive message for failed model task', async () => {
    const { wrapper } = await mountModelTask()
    const store = useRealStore()
    store.task = { ...structuredClone(modelTaskFixture), state: 'failed' }
    store.events = [
      ...structuredClone(modelTaskEventsFixture).slice(0, 3),
      {
        sequence: 4,
        eventType: 'task.failed',
        payload: { code: 'MODEL_DISABLED', message: 'provider 未启用' },
        createdAt: '2026-07-31T00:00:00+00:00',
      },
    ]
    await flushPromises()

    expect(wrapper.get('[data-testid="model-fail-detail"]').text()).toContain('MODEL_DISABLED')
    expect(wrapper.get('[data-testid="model-fail-detail"]').text()).toContain('provider 未启用')
    // 提示不得泄露真实 API Key（OpenAI 风格 sk- + 20 位以上字母数字）；
    // 注意夹具 id "model-task-mock1" 含 "sk-" 子串，故用精确正则而非朴素子串匹配
    expect(wrapper.text()).not.toMatch(/sk-[A-Za-z0-9]{20,}/)
  })

  it('hides SSE connection badge in mock mode (API-mode gate)', async () => {
    const { wrapper } = await mountModelTask()
    // 连接状态徽标仅在 API 模式渲染；Mock 模式隐藏以符合设计约束
    expect(wrapper.find('[data-testid="event-connection"]').exists()).toBe(false)
  })
})

describe('RealWorkspaceView 模型任务 degraded 门禁（WP7）', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.resetModules()
  })

  async function mountWorkspaceWithProvider(status: 'ready' | 'degraded') {
    vi.doMock('@/services/provider.service', () => ({
      providerService: { getHealth: vi.fn(async () => providerHealthMock(status)) },
    }))
    const { default: RealWorkspaceView } = await import('./RealWorkspaceView.vue')
    const router = createTestRouter()
    await router.push('/real/demo-real-workspace')
    await router.isReady()
    const wrapper = mount(RealWorkspaceView, { global: { plugins: [router] } })
    await flushPromises()
    // 填入两个标题，使按钮仅受 providerDegraded 控制（避免空标题本身禁用）
    const modelInput = wrapper.find('[data-testid="model-task-title-input"]')
    if (modelInput.exists()) {
      await modelInput.setValue('让模型追加标记')
      await flushPromises()
    }
    const realInput = wrapper.find('[data-testid="task-title-input"]')
    if (realInput.exists()) {
      await realInput.setValue('追加标记任务')
      await flushPromises()
    }
    return { wrapper, router }
  }

  it('disables new model task creation when provider is degraded, keeps real-task creation', async () => {
    const { wrapper } = await mountWorkspaceWithProvider('degraded')
    expect(wrapper.find('[data-testid="model-degraded-note"]').exists()).toBe(true)
    expect(wrapper.get('[data-testid="create-model-task-btn"]').attributes('disabled')).toBeDefined()
    // 真实任务创建不受影响
    expect(wrapper.get('[data-testid="create-task-btn"]').attributes('disabled')).toBeUndefined()
  })

  it('enables model task creation when provider ready', async () => {
    const { wrapper } = await mountWorkspaceWithProvider('ready')
    expect(wrapper.find('[data-testid="model-degraded-note"]').exists()).toBe(false)
    expect(wrapper.get('[data-testid="create-model-task-btn"]').attributes('disabled')).toBeUndefined()
  })
})
