import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter, type Router } from 'vue-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { ProviderStatus } from '@/types/agent'

function createTestRouter(): Router {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/real', name: 'real-workspace-list', component: { template: '<div>list</div>' } },
      { path: '/real/:id', name: 'real-workspace', component: { template: '<div>ws</div>' } },
    ],
  })
}

function providerHealthMock(status: ProviderStatus) {
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

describe('RealWorkspaceView 模型任务 Provider 门禁（M-02）', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.resetModules()
  })

  async function mountWorkspaceWithProvider(status: ProviderStatus | 'reject') {
    vi.doMock('@/services/provider.service', () => ({
      providerService: {
        getHealth:
          status === 'reject'
            ? vi.fn(async () => {
                throw new Error('health unavailable')
              })
            : vi.fn(async () => providerHealthMock(status)),
      },
    }))
    const { default: RealWorkspaceView } = await import('./RealWorkspaceView.vue')
    const router = createTestRouter()
    await router.push('/real/demo-real-workspace')
    await router.isReady()
    const wrapper = mount(RealWorkspaceView, { global: { plugins: [router] } })
    await flushPromises()
    // 填入标题，使按钮仅受 Provider 状态控制（避免空标题本身禁用）
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

  it('Provider ready 时启用模型任务创建', async () => {
    const { wrapper } = await mountWorkspaceWithProvider('ready')
    expect(wrapper.find('[data-testid="model-provider-note"]').exists()).toBe(false)
    expect(
      wrapper.get('[data-testid="create-model-task-btn"]').attributes('disabled'),
    ).toBeUndefined()
  })

  it.each([
    ['disabled', 'disabled'],
    ['unconfigured', 'unconfigured'],
    ['degraded', 'degraded'],
  ] as const)('Provider %s 时禁用模型任务创建，真实任务创建不受影响', async (_label, status) => {
    const { wrapper } = await mountWorkspaceWithProvider(status)
    expect(wrapper.find('[data-testid="model-provider-note"]').exists()).toBe(true)
    expect(
      wrapper.get('[data-testid="create-model-task-btn"]').attributes('disabled'),
    ).toBeDefined()
    // 真实任务创建不受 Provider 状态影响
    expect(wrapper.get('[data-testid="create-task-btn"]').attributes('disabled')).toBeUndefined()
  })

  it('health 请求失败（状态未知）时安全禁用模型任务创建', async () => {
    const { wrapper } = await mountWorkspaceWithProvider('reject')
    expect(wrapper.find('[data-testid="model-provider-note"]').exists()).toBe(true)
    expect(
      wrapper.get('[data-testid="create-model-task-btn"]').attributes('disabled'),
    ).toBeDefined()
    expect(wrapper.get('[data-testid="create-task-btn"]').attributes('disabled')).toBeUndefined()
  })
})
