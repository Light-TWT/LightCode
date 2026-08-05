import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import SettingsView from './SettingsView.vue'

const payloads = vi.hoisted(() => {
  const settingsPayload = {
    configured: true,
    status: 'ready',
    provider: 'openai-compatible',
    modelId: 'demo-model',
    detail: 'Provider 已就绪。',
    originAllowlisted: true,
    transport: 'https',
  }
  const healthPayload = {
    status: 'ready',
    provider: 'openai-compatible',
    modelId: 'demo-model',
    detail: 'ok',
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
  return { settingsPayload, healthPayload }
})

vi.mock('@/services/provider.service', () => ({
  providerService: {
    getSettings: vi.fn().mockResolvedValue(payloads.settingsPayload),
    getHealth: vi.fn().mockResolvedValue(payloads.healthPayload),
    saveSettings: vi.fn().mockResolvedValue(payloads.settingsPayload),
    testConnection: vi.fn().mockResolvedValue({ ok: true, code: '', detail: '' }),
    clearSettings: vi.fn().mockResolvedValue({ ...payloads.settingsPayload, configured: false }),
  },
}))

import { providerService } from '@/services/provider.service'

function createTestRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/settings', name: 'settings', component: SettingsView },
      { path: '/', name: 'home', component: { template: '<div>home page</div>' } },
    ],
  })
}

async function mountSettings() {
  const router = createTestRouter()
  await router.push('/settings')
  await router.isReady()
  const wrapper = mount(SettingsView, { global: { plugins: [router] } })
  await flushPromises()
  return { wrapper, router }
}

function getMock<T>(fn: unknown): T {
  return fn as T
}

describe('SettingsView（Provider 配置表单）', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    ;(providerService.getSettings as ReturnType<typeof vi.fn>).mockResolvedValue(
      payloads.settingsPayload,
    )
    ;(providerService.getHealth as ReturnType<typeof vi.fn>).mockResolvedValue(
      payloads.healthPayload,
    )
    ;(providerService.saveSettings as ReturnType<typeof vi.fn>).mockResolvedValue(
      payloads.settingsPayload,
    )
    ;(providerService.testConnection as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: true,
      code: '',
      detail: '',
    })
    ;(providerService.clearSettings as ReturnType<typeof vi.fn>).mockResolvedValue({
      ...payloads.settingsPayload,
      configured: false,
    })
  })

  it('渲染配置表单字段与 getSettings 安全状态卡片', async () => {
    const { wrapper } = await mountSettings()
    // 表单字段
    expect(wrapper.get('[data-testid="input-provider"]').exists()).toBe(true)
    expect(wrapper.get('[data-testid="input-base-url"]').exists()).toBe(true)
    expect(wrapper.get('[data-testid="input-api-key"]').attributes('type')).toBe('password')
    expect(wrapper.get('[data-testid="input-model-id"]').exists()).toBe(true)
    // getSettings 状态卡片
    expect(wrapper.get('[data-testid="settings-status"]').text()).toBe('ready')
    expect(wrapper.get('[data-testid="configured-tag"]').text()).toContain('已配置运行期凭据')
    expect(wrapper.get('[data-testid="settings-model"]').text()).toBe('demo-model')
    // 安全说明文案
    expect(wrapper.text()).toContain('仅保存在后端进程内存')
    expect(wrapper.text()).toContain('Electron 阶段将迁移为系统密钥库')
  })

  it('「测试连接」以表单值调用 testConnection，且响应不含 key/baseUrl', async () => {
    const { wrapper } = await mountSettings()
    await wrapper.get('[data-testid="input-base-url"]').setValue('https://api.example.com/v1')
    await wrapper.get('[data-testid="input-api-key"]').setValue('sk-super-secret-12345')
    await wrapper.get('[data-testid="input-model-id"]').setValue('demo-model')

    await wrapper.get('[data-testid="btn-test"]').trigger('click')
    await flushPromises()

    const testFn = getMock<ReturnType<typeof vi.fn>>(providerService.testConnection)
    expect(testFn).toHaveBeenCalledTimes(1)
    const body = testFn.mock.calls[0][0]
    expect(body).toMatchObject({
      provider: 'openai-compatible',
      baseUrl: 'https://api.example.com/v1',
      apiKey: 'sk-super-secret-12345',
      modelId: 'demo-model',
    })
    // 测试成功提示，且状态卡片（来自响应）不渲染密钥/完整 URL
    expect(wrapper.get('[data-testid="form-message"]').text()).toContain('连接测试成功')
    expect(wrapper.get('[data-testid="form-message"]').text()).not.toContain('sk-super-secret-12345')
    const statusCard = wrapper.get('[aria-label="Provider 状态"]')
    expect(statusCard.text()).not.toContain('sk-super-secret-12345')
    expect(statusCard.text()).not.toContain('https://api.example.com/v1')
  })

  it('「测试并保存」调用 saveSettings，提交后清空 key 输入框', async () => {
    const { wrapper } = await mountSettings()
    await wrapper.get('[data-testid="input-base-url"]').setValue('https://api.example.com/v1')
    await wrapper.get('[data-testid="input-api-key"]').setValue('sk-super-secret-12345')
    await wrapper.get('[data-testid="input-model-id"]').setValue('demo-model')

    // 「测试并保存」是 submit 按钮：jsdom 中按钮 click 不会触发表单 submit，
    // 直接对 form 触发 submit（与真实浏览器行为一致）
    await wrapper.get('[data-testid="provider-form"]').trigger('submit')
    await flushPromises()

    const saveFn = getMock<ReturnType<typeof vi.fn>>(providerService.saveSettings)
    expect(saveFn).toHaveBeenCalledTimes(1)
    expect(saveFn.mock.calls[0][0].apiKey).toBe('sk-super-secret-12345')
    // 提交后清空 key 输入框，绝不把密钥留在 DOM / 前端存储
    expect(wrapper.get('[data-testid="input-api-key"]').element as HTMLInputElement).toHaveProperty(
      'value',
      '',
    )
    expect(wrapper.text()).not.toContain('sk-super-secret-12345')
    expect(wrapper.get('[data-testid="form-message"]').text()).toContain('已保存')
  })

  it('「清除运行期配置」调用 clearSettings 并刷新状态', async () => {
    const { wrapper } = await mountSettings()
    await wrapper.get('[data-testid="btn-clear"]').trigger('click')
    await flushPromises()

    const clearFn = getMock<ReturnType<typeof vi.fn>>(providerService.clearSettings)
    expect(clearFn).toHaveBeenCalledTimes(1)
    expect(wrapper.get('[data-testid="configured-tag"]').text()).toContain('仅环境变量')
  })

  it('返回按钮导航到首页', async () => {
    const { wrapper, router } = await mountSettings()
    await wrapper.get('[data-testid="back-home-btn"]').trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.fullPath).toBe('/')
  })
})
