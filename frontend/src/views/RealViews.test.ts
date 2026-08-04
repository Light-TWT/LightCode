import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter, type Router } from 'vue-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { realTaskFixture } from '@/fixtures/phase1.fixture'
import { providerService } from '@/services/provider.service'
import { useRealStore } from '@/stores/real.store'
import type { ProviderHealth } from '@/types/agent'
import RealTaskView from './RealTaskView.vue'
import RealWorkspaceListView from './RealWorkspaceListView.vue'
import RealWorkspaceView from './RealWorkspaceView.vue'

function createTestRouter(): Router {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', name: 'home', component: { template: '<div>home</div>' } },
      { path: '/real', name: 'real-workspace-list', component: RealWorkspaceListView },
      { path: '/real/:id', name: 'real-workspace', component: RealWorkspaceView },
      { path: '/real/:id/task/:taskId', name: 'real-task', component: RealTaskView },
    ],
  })
}

/** M-02：模型任务创建门禁为 ready-only，集成测试需显式 mock ready 状态 */
const readyHealth: ProviderHealth = {
  status: 'ready',
  provider: 'openai-compatible',
  modelId: 'demo-model',
  detail: 'Provider 已就绪。',
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

describe('RealWorkspaceListView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('renders registered workspaces with enabled/disabled badges', async () => {
    const router = createTestRouter()
    await router.push('/real')
    await router.isReady()
    const wrapper = mount(RealWorkspaceListView, { global: { plugins: [router] } })
    await flushPromises()

    const rows = wrapper.findAll('[data-testid="registered-workspace-row"]')
    expect(rows.length).toBe(2)
    expect(rows[0].text()).toContain('Demo Real Workspace')
    expect(rows[0].text()).toContain('已启用')
    expect(rows[1].text()).toContain('已停用')
    // 公共视图不显示真实根路径
    expect(wrapper.text()).not.toContain('C:\\')
  })

  it('navigates into an enabled workspace on click', async () => {
    const router = createTestRouter()
    await router.push('/real')
    await router.isReady()
    const wrapper = mount(RealWorkspaceListView, { global: { plugins: [router] } })
    await flushPromises()

    await wrapper.findAll('[data-testid="registered-workspace-row"]')[0].trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.fullPath).toBe('/real/demo-real-workspace')
  })
})

describe('RealWorkspaceView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  async function mountWorkspace() {
    const router = createTestRouter()
    await router.push('/real/demo-real-workspace')
    await router.isReady()
    const wrapper = mount(RealWorkspaceView, { global: { plugins: [router] } })
    await flushPromises()
    return { wrapper, router }
  }

  it('lists directory entries and blocks secret files', async () => {
    const { wrapper } = await mountWorkspace()

    const entries = wrapper.findAll('[data-testid="file-entry"]')
    expect(entries.length).toBe(3)
    const secret = entries.find((e) => e.text().includes('.env'))!
    expect(secret.attributes('disabled')).toBeDefined()
    expect(secret.text()).toContain('禁止读取')
  })

  it('opens file preview on file click', async () => {
    const { wrapper } = await mountWorkspace()

    const fileEntry = wrapper
      .findAll('[data-testid="file-entry"]')
      .find((e) => e.text().includes('NOTES.md'))!
    await fileEntry.trigger('click')
    await flushPromises()

    expect(wrapper.get('[data-testid="preview-path"]').text()).toBe('NOTES.md')
    expect(wrapper.get('[data-testid="preview-content"]').text()).toContain('demo content')
  })

  it('searches content and shows hits', async () => {
    const { wrapper } = await mountWorkspace()

    await wrapper.get('[data-testid="search-input"]').setValue('demo')
    await wrapper.get('[data-testid="search-btn"]').trigger('submit')
    await flushPromises()

    expect(wrapper.findAll('[data-testid="search-hit"]').length).toBeGreaterThan(0)
  })

  it('creates a real task and navigates to the task view', async () => {
    const { wrapper, router } = await mountWorkspace()

    await wrapper.get('[data-testid="task-title-input"]').setValue('追加标记任务')
    await wrapper.get('[data-testid="create-task-btn"]').trigger('submit')
    await flushPromises()

    expect(router.currentRoute.value.fullPath).toBe(
      `/real/demo-real-workspace/task/${realTaskFixture.id}`,
    )
  })

  it('creates a model task and navigates to the task view', async () => {
    // M-02：模型任务创建仅当 Provider ready；集成测试 mock 为 ready
    const healthSpy = vi
      .spyOn(providerService, 'getHealth')
      .mockResolvedValue(readyHealth)
    try {
      const { wrapper, router } = await mountWorkspace()

      await wrapper.get('[data-testid="model-task-title-input"]').setValue('让模型追加标记')
      await wrapper.get('[data-testid="create-model-task-btn"]').trigger('submit')
      await flushPromises()

      // Mock 模式首个模型任务 id 固定为 model-task-mock1
      expect(router.currentRoute.value.fullPath).toBe(
        '/real/demo-real-workspace/task/model-task-mock1',
      )
    } finally {
      healthSpy.mockRestore()
    }
  })
})

describe('RealTaskView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  async function mountTask() {
    const router = createTestRouter()
    await router.push(`/real/demo-real-workspace/task/${realTaskFixture.id}`)
    await router.isReady()
    const wrapper = mount(RealTaskView, { global: { plugins: [router] } })
    await flushPromises()
    return { wrapper, router }
  }

  it('renders awaiting-approval task with version-bound changeset details', async () => {
    const { wrapper } = await mountTask()

    expect(wrapper.get('[data-testid="task-state"]').text()).toBe('等待审批')
    const summary = wrapper.get('[data-testid="changeset-summary"]').text()
    expect(summary).toContain('NOTES.md')
    expect(summary).toContain('+1')
    expect(wrapper.text()).toContain('cs-demo00000001')
    expect(wrapper.find('[data-testid="approval-bar"]').exists()).toBe(true)
  })

  it('approve completes the task and shows success result', async () => {
    const { wrapper } = await mountTask()

    await wrapper.get('[data-testid="approve-btn"]').trigger('click')
    await flushPromises()

    expect(wrapper.get('[data-testid="task-state"]').text()).toBe('已完成')
    expect(wrapper.find('[data-testid="approval-bar"]').exists()).toBe(false)
    expect(wrapper.get('[data-testid="result-bar"]').text()).toContain('原子写入')
  })

  it('reject cancels the task without touching files', async () => {
    const { wrapper } = await mountTask()

    await wrapper.get('[data-testid="reject-btn"]').trigger('click')
    await flushPromises()

    expect(wrapper.get('[data-testid="task-state"]').text()).toBe('已拒绝')
    expect(wrapper.get('[data-testid="result-bar"]').text()).toContain('未接触任何文件')
  })

  it('store keeps changeset binding used for the approval request', async () => {
    await mountTask()
    const store = useRealStore()

    expect(store.task?.changeSet?.changeSetId).toBe('cs-demo00000001')
    expect(store.task?.changeSet?.revision).toBe(1)
    expect(store.task?.changeSet?.diffHash).toBe('demo-diff-hash')
  })
})
