import { flushPromises, mount } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'
import { describe, expect, it } from 'vitest'
import SettingsView from './SettingsView.vue'

const router = createRouter({
  history: createMemoryHistory(),
  routes: [
    { path: '/settings', name: 'settings', component: SettingsView },
    { path: '/', name: 'home', component: { template: '<div>home</div>' } },
  ],
})

async function mountSettings() {
  await router.push('/settings')
  await router.isReady()
  const wrapper = mount(SettingsView, { global: { plugins: [router] } })
  await flushPromises()
  return wrapper
}

describe('SettingsView', () => {
  it('shows general category as default', async () => {
    const wrapper = await mountSettings()
    const navItems = wrapper.findAll('[data-testid="settings-nav-item"]')
    expect(navItems.length).toBe(5)
    expect(navItems[0].classes()).toContain('active')
    expect(navItems[0].text()).toBe('通用')
  })

  it('navigates between categories on click', async () => {
    const wrapper = await mountSettings()
    const navItems = wrapper.findAll('[data-testid="settings-nav-item"]')

    await navItems[1].trigger('click')
    expect(navItems[1].classes()).toContain('active')
    expect(navItems[0].classes()).not.toContain('active')
    expect(wrapper.text()).toContain('Mock Mode')

    await navItems[2].trigger('click')
    expect(navItems[2].classes()).toContain('active')
    expect(wrapper.text()).toContain('授权根目录')

    await navItems[3].trigger('click')
    expect(navItems[3].classes()).toContain('active')
    expect(wrapper.text()).toContain('安全预设')

    await navItems[4].trigger('click')
    expect(navItems[4].classes()).toContain('active')
    expect(wrapper.text()).toContain('SQLite 数据库路径')
  })

  it('shows Mock Mode as active with badge', async () => {
    const wrapper = await mountSettings()
    await wrapper.findAll('[data-testid="settings-nav-item"]')[1].trigger('click')

    expect(wrapper.find('[data-testid="mode-mock"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="mode-mock"]').text()).toContain('当前启用')
  })

  it('shows disabled OpenAI Compatible API with placeholder fields', async () => {
    const wrapper = await mountSettings()
    await wrapper.findAll('[data-testid="settings-nav-item"]')[1].trigger('click')

    const apiBlock = wrapper.find('[data-testid="mode-api"]')
    expect(apiBlock.exists()).toBe(true)
    expect(apiBlock.text()).toContain('第二阶段可用')
    expect(apiBlock.text()).toContain('Base URL')
    expect(apiBlock.text()).toContain('API Key')
    expect(apiBlock.text()).toContain('未配置')
  })

  it('shows permission allowed and denied rules', async () => {
    const wrapper = await mountSettings()
    await wrapper.findAll('[data-testid="settings-nav-item"]')[2].trigger('click')

    const columns = wrapper.find('[data-testid="perm-columns"]')
    expect(columns.text()).toContain('读取工作区内文件')
    expect(columns.text()).toContain('访问工作区外路径')
    expect(columns.text()).toContain('删除文件')
    expect(columns.text()).toContain('.env')
  })

  it('shows command safe presets and denied high-risk commands', async () => {
    const wrapper = await mountSettings()
    await wrapper.findAll('[data-testid="settings-nav-item"]')[3].trigger('click')

    expect(wrapper.text()).toContain('pytest')
    expect(wrapper.text()).toContain('npm test')
    expect(wrapper.text()).toContain('rm -rf')
  })

  it('shows local data SQLite path and storage groups', async () => {
    const wrapper = await mountSettings()
    await wrapper.findAll('[data-testid="settings-nav-item"]')[4].trigger('click')

    expect(wrapper.find('[data-testid="data-path"]').text()).toContain('lightcode.db')
    expect(wrapper.find('[data-testid="data-columns"]').text()).toContain('会话记录')
    expect(wrapper.find('[data-testid="data-columns"]').text()).toContain('API Key')
    expect(wrapper.find('[data-testid="data-note"]').text()).toContain('Electron')
  })

  it('has footer with privacy note', async () => {
    const wrapper = await mountSettings()
    const footer = wrapper.find('[data-testid="footer-bar"]')
    expect(footer.exists()).toBe(true)
    expect(footer.text()).toContain('仅存储在本机')
  })
})
