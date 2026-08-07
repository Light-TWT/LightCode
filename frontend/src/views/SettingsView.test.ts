import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import SettingsView from './SettingsView.vue'

const payloads = vi.hoisted(() => {
  const profilesPayload = [
    {
      id: 'default',
      name: 'openai-compatible',
      provider: 'openai-compatible',
      modelId: 'demo-model',
      enabled: true,
      status: 'ready',
      baseUrlHost: 'provider.example',
    },
    {
      id: 'deepseek',
      name: 'deepseek',
      provider: 'openai-compatible',
      modelId: 'deepseek-chat',
      enabled: false,
      status: 'unconfigured',
      baseUrlHost: 'api.deepseek.com',
    },
  ]
  const settingsPayload = {
    configured: true,
    status: 'ready',
    provider: 'openai-compatible',
    modelId: 'demo-model',
    detail: 'Provider 已就绪。',
    originAllowlisted: true,
    transport: 'https',
  }
  return { profilesPayload, settingsPayload }
})

vi.mock('@/services/provider.service', () => ({
  providerService: {
    getSettings: vi.fn().mockResolvedValue(payloads.settingsPayload),
    getHealth: vi.fn().mockResolvedValue({ status: 'ready' }),
    saveSettings: vi.fn().mockResolvedValue(payloads.settingsPayload),
    testConnection: vi.fn().mockResolvedValue({ ok: true, code: '', detail: '' }),
    clearSettings: vi.fn().mockResolvedValue({ ...payloads.settingsPayload, configured: false }),
    listProviders: vi.fn().mockResolvedValue(payloads.profilesPayload),
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

describe('SettingsView（多供应商设置页）', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    ;(providerService.listProviders as ReturnType<typeof vi.fn>).mockResolvedValue(
      payloads.profilesPayload,
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

  it('渲染设置分类（模型与供应商 / 关于）与供应商列表', async () => {
    const { wrapper } = await mountSettings()
    expect(wrapper.get('[data-testid="settings-cat-providers"]').exists()).toBe(true)
    expect(wrapper.get('[data-testid="settings-cat-about"]').exists()).toBe(true)
    // 默认选中第一条并展示详情
    expect(wrapper.get('[data-testid="detail-name"]').text()).toBe('openai-compatible')
    expect(wrapper.get('[data-testid="detail-model"]').text()).toBe('demo-model')
    // 列表状态点：ready 启用 / 未配置等待测试
    expect(wrapper.text()).toContain('2 个配置')
    expect(wrapper.get('[data-testid="provider-row-default"]').exists()).toBe(true)
  })

  it('点击列表第二条供应商后详情区标题切换', async () => {
    const { wrapper } = await mountSettings()
    await wrapper.get('[data-testid="provider-row-deepseek"]').trigger('click')
    await flushPromises()
    expect(wrapper.get('[data-testid="detail-name"]').text()).toBe('deepseek')
    expect(wrapper.get('[data-testid="detail-model"]').text()).toBe('deepseek-chat')
    expect(wrapper.get('[data-testid="detail-badge"]').text()).toBe('等待测试')
  })

  it('搜索过滤供应商并显示空状态', async () => {
    const { wrapper } = await mountSettings()
    await wrapper.get('[data-testid="provider-search"]').setValue('不存在的供应商')
    await flushPromises()
    expect(wrapper.get('[data-testid="provider-empty"]').exists()).toBe(true)
    // 恢复搜索后列表恢复
    await wrapper.get('[data-testid="provider-search"]').setValue('deepseek')
    await flushPromises()
    expect(wrapper.get('[data-testid="provider-row-deepseek"]').exists()).toBe(true)
  })

  it('「关于」分类显示占位面板', async () => {
    const { wrapper } = await mountSettings()
    await wrapper.get('[data-testid="settings-cat-about"]').trigger('click')
    await flushPromises()
    expect(wrapper.get('[data-testid="about-panel"]').exists()).toBe(true)
  })

  it('点击「添加供应商」打开弹层，API Key 为 password 且选择模板更新配置名称', async () => {
    const { wrapper } = await mountSettings()
    await wrapper.get('[data-testid="open-add"]').trigger('click')
    await flushPromises()
    expect(wrapper.get('[data-testid="modal-api-key"]').attributes('type')).toBe('password')
    await wrapper.get('[data-testid="template-DeepSeek"]').trigger('click')
    await flushPromises()
    expect((wrapper.get('[data-testid="modal-name"]').element as HTMLInputElement).value).toBe(
      'DeepSeek',
    )
  })

  it('弹层「测试连接」以表单值调用 testConnection，提示不含密钥', async () => {
    const { wrapper } = await mountSettings()
    await wrapper.get('[data-testid="open-add"]').trigger('click')
    await flushPromises()
    await wrapper.get('[data-testid="modal-base-url"]').setValue('https://api.example.com/v1')
    await wrapper.get('[data-testid="modal-api-key"]').setValue('sk-super-secret-12345')
    await wrapper.get('[data-testid="modal-model-id"]').setValue('demo-model')

    await wrapper.get('[data-testid="modal-test"]').trigger('click')
    await flushPromises()

    const testFn = getMock<ReturnType<typeof vi.fn>>(providerService.testConnection)
    expect(testFn).toHaveBeenCalledTimes(1)
    expect(testFn.mock.calls[0][0]).toMatchObject({
      provider: 'openai-compatible',
      baseUrl: 'https://api.example.com/v1',
      apiKey: 'sk-super-secret-12345',
      modelId: 'demo-model',
    })
    const message = wrapper.get('[data-testid="modal-message"]').text()
    expect(message).toContain('连接测试成功')
    expect(message).not.toContain('sk-super-secret-12345')
    expect(wrapper.text()).not.toContain('sk-super-secret-12345')
    expect(wrapper.text()).not.toContain('https://api.example.com/v1')
  })

  it('「测试并添加」调用 saveSettings，提交后清空 key 输入框', async () => {
    const { wrapper } = await mountSettings()
    await wrapper.get('[data-testid="open-add"]').trigger('click')
    await flushPromises()
    await wrapper.get('[data-testid="modal-base-url"]').setValue('https://api.example.com/v1')
    await wrapper.get('[data-testid="modal-api-key"]').setValue('sk-super-secret-12345')
    await wrapper.get('[data-testid="modal-model-id"]').setValue('demo-model')

    await wrapper.get('[data-testid="modal-save"]').trigger('click')
    await flushPromises()

    const saveFn = getMock<ReturnType<typeof vi.fn>>(providerService.saveSettings)
    expect(saveFn).toHaveBeenCalledTimes(1)
    expect(saveFn.mock.calls[0][0].apiKey).toBe('sk-super-secret-12345')
    // 保存成功后弹层关闭（v-if 销毁），密钥输入框不再存在于 DOM
    expect(wrapper.find('[data-testid="modal-api-key"]').exists()).toBe(false)
    // 成功提示出现，且密钥绝不留在 DOM / 前端存储
    expect(wrapper.get('[data-testid="form-message"]').text()).toContain('供应商已添加')
    expect(wrapper.text()).not.toContain('sk-super-secret-12345')
  })

  it('「清除运行期配置」调用 clearSettings 并显示成功提示', async () => {
    const { wrapper } = await mountSettings()
    await wrapper.get('[data-testid="btn-clear"]').trigger('click')
    await flushPromises()
    const clearFn = getMock<ReturnType<typeof vi.fn>>(providerService.clearSettings)
    expect(clearFn).toHaveBeenCalledTimes(1)
    expect(wrapper.get('[data-testid="form-message"]').text()).toContain('已清除运行期配置')
  })

  it('返回按钮导航到首页', async () => {
    const { wrapper, router } = await mountSettings()
    await wrapper.get('[data-testid="back-home-btn"]').trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.fullPath).toBe('/')
  })

  it('页面文本不泄露密钥或完整 Base URL', async () => {
    const { wrapper } = await mountSettings()
    expect(wrapper.text()).not.toContain('sk-')
    expect(wrapper.text()).not.toContain('https://')
  })
})
