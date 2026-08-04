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

    // M-03: 只展示稳定错误码 + 固定中文文案，不渲染服务端自由 message
    expect(wrapper.get('[data-testid="model-fail-detail"]').text()).toContain('MODEL_DISABLED')
    expect(wrapper.get('[data-testid="model-fail-detail"]').text()).toContain('模型能力未启用。')
    expect(wrapper.get('[data-testid="model-fail-detail"]').text()).not.toContain('provider 未启用')
    // 提示不得泄露真实 API Key（OpenAI 风格 sk- + 20 位以上字母数字）；
    // 注意夹具 id "model-task-mock1" 含 "sk-" 子串，故用精确正则而非朴素子串匹配
    expect(wrapper.text()).not.toMatch(/sk-[A-Za-z0-9]{20,}/)
  })

  it('never renders a sensitive server message inside the failure detail', async () => {
    const { wrapper } = await mountModelTask()
    const store = useRealStore()
    store.task = { ...structuredClone(modelTaskFixture), state: 'failed' }
    store.events = [
      ...structuredClone(modelTaskEventsFixture).slice(0, 3),
      {
        sequence: 4,
        eventType: 'task.failed',
        payload: {
          code: 'MODEL_RESPONSE_INVALID',
          message:
            'Authorization: Bearer secret-value; sk-abcdefghijklmnopqrstuvwxyz; C:\\private\\project',
        },
        createdAt: '2026-07-31T00:00:00+00:00',
      },
    ]
    await flushPromises()

    const detail = wrapper.get('[data-testid="model-fail-detail"]').text()
    expect(detail).toContain('MODEL_RESPONSE_INVALID')
    expect(detail).toContain('模型输出或编排结果无效')
    expect(detail).not.toContain('secret-value')
    expect(detail).not.toContain('sk-abcdefghijklmnopqrstuvwxyz')
    expect(detail).not.toContain('C:\\private\\project')
    expect(detail).not.toContain('Authorization')
    expect(detail).not.toContain('Bearer')
  })

  it('hides SSE connection badge in mock mode (API-mode gate)', async () => {
    const { wrapper } = await mountModelTask()
    // 连接状态徽标仅在 API 模式渲染；Mock 模式隐藏以符合设计约束
    expect(wrapper.find('[data-testid="event-connection"]').exists()).toBe(false)
  })
})

describe('RealTaskView 路由工作区归属（M-06）', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.resetModules()
  })

  it('URL 工作区与任务归属不一致时清理状态并跳转到真实归属路由', async () => {
    vi.doMock('@/services/real-task.service', () => ({
      realTaskService: {
        getRealTask: vi.fn(async () => ({
          ...structuredClone(modelTaskFixture),
          workspaceId: 'workspace-a',
        })),
        createRealTask: vi.fn(),
        submitApproval: vi.fn(),
      },
    }))
    vi.doMock('@/config/runtime', () => ({ isApiMode: false }))
    const { default: RealTaskView } = await import('./RealTaskView.vue')
    const router = createTestRouter()
    // 故意用错误的 workspace-b 访问属于 workspace-a 的任务
    await router.push(`/real/workspace-b/task/${modelTaskFixture.id}`)
    await router.isReady()
    mount(RealTaskView, { global: { plugins: [router] } })
    await flushPromises()

    const store = useRealStore()
    expect(router.currentRoute.value.fullPath).toBe(
      `/real/workspace-a/task/${modelTaskFixture.id}`,
    )
    // 不保留错误工作区上下文下的任务详情与连接
    expect(store.task).toBeNull()
    expect(store.eventConnection).toBe('idle')
  })
})

