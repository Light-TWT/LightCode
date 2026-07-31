import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import SettingsView from './SettingsView.vue'
import { providerService } from '@/services/provider.service'

// 用可控快照替换 provider.service，便于断言刷新调用次数与新字段渲染
vi.mock('@/services/provider.service', () => ({
  providerService: {
    getHealth: vi.fn().mockResolvedValue({
      status: 'disabled',
      provider: 'none',
      modelId: '',
      detail: '模型提供方未启用（默认关闭）。',
      capabilities: {
        tools: ['read_file', 'search_files'],
        canWriteFiles: false,
        canRunCommands: false,
        maxToolRounds: 8,
        maxRequestsPerTask: 10,
        maxInputBytes: 262144,
        maxOutputTokens: 2048,
        maxConcurrentTasks: 1,
      },
      security: {
        apiKeyConfigured: false,
        transport: 'none',
        originAllowlisted: false,
        followRedirects: false,
        trustEnvProxies: false,
      },
    }),
  },
}))

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

describe('SettingsView', () => {
  it('renders the sidebar with nav items', async () => {
    const { wrapper } = await mountSettings()
    expect(wrapper.text()).toContain('设置')
    expect(wrapper.text()).toContain('通用')
    expect(wrapper.text()).toContain('模型')
    expect(wrapper.text()).toContain('工作区权限')
    expect(wrapper.text()).toContain('命令策略')
    expect(wrapper.text()).toContain('本地数据')
    expect(wrapper.text()).toContain('LightCode v0.1.0')
  })

  it('shows general page content by default', async () => {
    const { wrapper } = await mountSettings()
    expect(wrapper.text()).toContain('Local runtime ready')
    expect(wrapper.text()).toContain('前端 Mock 原型')
  })

  it('switches page on nav item click', async () => {
    const { wrapper } = await mountSettings()
    expect(wrapper.text()).toContain('Local runtime ready')

    const navBtns = wrapper.findAll('button.nav-item')
    expect(navBtns.length).toBe(5)

    await navBtns[1].trigger('click')
    expect(wrapper.text()).toContain('Mock Mode')
    expect(wrapper.text()).toContain('OpenAI Compatible API')
    expect(wrapper.text()).not.toContain('Local runtime ready')

    await navBtns[2].trigger('click')
    expect(wrapper.text()).toContain('授权根目录')
  })

  it('navigates back to home on back button click', async () => {
    const { wrapper, router } = await mountSettings()

    await wrapper.get('button.sidebar-back').trigger('click')
    await flushPromises()

    expect(router.currentRoute.value.fullPath).toBe('/')
  })

  it('renders live provider health (mock mode defaults to disabled)', async () => {
    const { wrapper } = await mountSettings()

    const navBtns = wrapper.findAll('button.nav-item')
    await navBtns[1].trigger('click') // 模型
    await flushPromises()

    expect(wrapper.text()).toContain('Provider 健康状态')
    expect(wrapper.text()).toContain('disabled')
    expect(wrapper.text()).not.toContain('sk-')
    expect(wrapper.text()).toContain('数据源：前端 Mock')
  })

  it('renders full capability and security fields', async () => {
    const { wrapper } = await mountSettings()

    const navBtns = wrapper.findAll('button.nav-item')
    await navBtns[1].trigger('click')
    await flushPromises()

    const text = wrapper.text()
    expect(text).toContain('256 KB') // maxInputBytes 格式化
    expect(text).toContain('2048 tokens') // maxOutputTokens
    expect(text).toContain('跟随重定向')
    expect(text).toContain('信任环境变量代理')
    expect(text).toContain('可写文件')
    expect(text).toContain('可执行命令')
  })

  it('refreshes health when the refresh button is clicked', async () => {
    const { wrapper } = await mountSettings()

    const navBtns = wrapper.findAll('button.nav-item')
    await navBtns[1].trigger('click')
    await flushPromises()

    const callsAfterMount = (providerService.getHealth as ReturnType<typeof vi.fn>).mock.calls.length
    expect(callsAfterMount).toBeGreaterThanOrEqual(1)

    await wrapper.get('button.health-refresh').trigger('click')
    await flushPromises()

    const callsAfterRefresh = (providerService.getHealth as ReturnType<typeof vi.fn>).mock.calls.length
    expect(callsAfterRefresh).toBe(callsAfterMount + 1)
  })
})
