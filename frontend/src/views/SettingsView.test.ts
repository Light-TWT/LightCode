import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { beforeEach, describe, expect, it } from 'vitest'
import SettingsView from './SettingsView.vue'

describe('SettingsView', () => {
  it('renders the sidebar with nav items', () => {
    const wrapper = mount(SettingsView)
    expect(wrapper.text()).toContain('设置')
    expect(wrapper.text()).toContain('通用')
    expect(wrapper.text()).toContain('模型')
    expect(wrapper.text()).toContain('工作区权限')
    expect(wrapper.text()).toContain('命令策略')
    expect(wrapper.text()).toContain('本地数据')
    expect(wrapper.text()).toContain('LightCode v0.1.0')
  })

  it('shows general page content by default', () => {
    const wrapper = mount(SettingsView)
    expect(wrapper.text()).toContain('Local runtime ready')
    expect(wrapper.text()).toContain('前端 Mock 原型')
  })

  it('switches page on nav item click', async () => {
    const wrapper = mount(SettingsView)
    expect(wrapper.text()).toContain('Local runtime ready')

    const modelBtn = wrapper.findAll('button.nav-item')[1]
    await modelBtn.trigger('click')

    expect(wrapper.text()).toContain('Mock Mode')
    expect(wrapper.text()).toContain('OpenAI Compatible API')
    expect(wrapper.text()).not.toContain('Local runtime ready')
  })

  it('navigates back to home on back button click', async () => {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/', name: 'home', component: SettingsView },
        { path: '/settings', name: 'settings', component: SettingsView },
      ],
    })
    await router.push('/settings')
    await router.isReady()

    const wrapper = mount(SettingsView, {
      global: { plugins: [router] },
    })
    await flushPromises()

    await wrapper.get('button.sidebar-back').trigger('click')
    await flushPromises()

    expect(router.currentRoute.value.fullPath).toBe('/')
  })
})
