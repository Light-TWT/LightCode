import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { beforeEach, describe, expect, it } from 'vitest'
import SettingsView from './SettingsView.vue'

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
})
