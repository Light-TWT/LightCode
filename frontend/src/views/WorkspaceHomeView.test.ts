import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createWebHistory } from 'vue-router'
import { beforeEach, describe, expect, it } from 'vitest'
import WorkspaceHomeView from './WorkspaceHomeView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [{ path: '/', name: 'home', component: WorkspaceHomeView }],
})

describe('WorkspaceHomeView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('shows recent workspaces with primary row for waiting status', async () => {
    const wrapper = mount(WorkspaceHomeView, { global: { plugins: [router] } })
    await flushPromises()

    const rows = wrapper.findAll('[data-testid="project-row"]')
    expect(rows.length).toBe(5)
    expect(rows[0].classes()).toContain('primary')
    expect(rows[0].text()).toContain('等待审批')
    expect(rows[1].classes()).toContain('secondary')
  })

  it('drawer is hidden by default, opens on view-all click', async () => {
    const wrapper = mount(WorkspaceHomeView, { global: { plugins: [router] } })
    await flushPromises()

    expect(wrapper.find('[data-testid="workspace-drawer"]').exists()).toBe(false)

    await wrapper.get('[data-testid="view-all-btn"]').trigger('click')
    expect(wrapper.find('[data-testid="workspace-drawer"]').exists()).toBe(true)
  })

  it('closes drawer on escape key', async () => {
    const wrapper = mount(WorkspaceHomeView, { global: { plugins: [router] } })
    await flushPromises()

    await wrapper.get('[data-testid="view-all-btn"]').trigger('click')
    await wrapper.get('[data-testid="drawer-overlay"]').trigger('keydown', { key: 'Escape' })

    expect(wrapper.find('[data-testid="workspace-drawer"]').exists()).toBe(false)
  })

  it('shows all 7 workspaces in drawer with search filtering', async () => {
    const wrapper = mount(WorkspaceHomeView, { global: { plugins: [router] } })
    await flushPromises()

    await wrapper.get('[data-testid="view-all-btn"]').trigger('click')

    const items = wrapper.findAll('[data-testid="drawer-item"]')
    expect(items.length).toBe(7)

    const search = wrapper.get('[data-testid="drawer-search"]')
    await search.setValue('dashboard')

    const filtered = wrapper.findAll('[data-testid="drawer-item"]:not([style*="display: none"])')
    expect(filtered.length).toBe(1)
    expect(filtered[0].text()).toContain('dashboard-ui')
  })
})
