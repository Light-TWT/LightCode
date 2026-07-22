import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import { beforeEach, describe, expect, it } from 'vitest'
import AgentWorkspaceView from './AgentWorkspaceView.vue'
import SessionHistoryView from './SessionHistoryView.vue'
import SettingsView from './SettingsView.vue'
import WorkspaceHomeView from './WorkspaceHomeView.vue'

function createAppRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', name: 'home', component: WorkspaceHomeView },
      { path: '/workspace/:id', name: 'agent-workspace', component: AgentWorkspaceView },
      { path: '/workspace/:id/history', name: 'session-history', component: SessionHistoryView },
      { path: '/settings', name: 'settings', component: SettingsView },
    ],
  })
}

describe('cross-page navigation', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('navigates Workspace Home -> Agent Workspace on project click', async () => {
    const router = createAppRouter()
    await router.push('/')
    await router.isReady()

    const wrapper = mount(WorkspaceHomeView, { global: { plugins: [router] } })
    await flushPromises()

    const rows = wrapper.findAll('[data-testid="project-row"]')
    expect(rows.length).toBeGreaterThanOrEqual(1)

    await rows[0].trigger('click')
    await flushPromises()

    expect(router.currentRoute.value.fullPath).toMatch(/^\/workspace\//)
  })

  it('navigates Agent Workspace -> Task History on history link click', async () => {
    const router = createAppRouter()
    await router.push('/workspace/workspace-login-service')
    await router.isReady()

    const wrapper = mount(AgentWorkspaceView, { global: { plugins: [router] } })
    await flushPromises()

    await wrapper.get('[data-testid="task-history-link"]').trigger('click')
    await flushPromises()

    expect(router.currentRoute.value.fullPath).toBe('/workspace/workspace-login-service/history')
  })

  it('navigates Task History pending task -> Agent Workspace review', async () => {
    const router = createAppRouter()
    await router.push('/workspace/workspace-login-service/history')
    await router.isReady()

    const wrapper = mount(SessionHistoryView, { global: { plugins: [router] } })
    await flushPromises()

    const reviewBtns = wrapper.findAll('[data-testid="action-review"]')
    expect(reviewBtns.length).toBeGreaterThanOrEqual(1)

    await reviewBtns[0].trigger('click')
    await flushPromises()

    expect(router.currentRoute.value.fullPath).toBe('/workspace/workspace-login-service')
  })

  it('navigates Agent Workspace -> Settings on settings button click', async () => {
    const router = createAppRouter()
    await router.push('/workspace/workspace-login-service')
    await router.isReady()

    const wrapper = mount(AgentWorkspaceView, { global: { plugins: [router] } })
    await flushPromises()

    await wrapper.get('[data-testid="settings-btn"]').trigger('click')
    await flushPromises()

    expect(router.currentRoute.value.fullPath).toBe('/settings')
  })

  it('navigates Settings -> Home on back button click', async () => {
    const router = createAppRouter()
    await router.push('/settings')
    await router.isReady()

    const wrapper = mount(SettingsView, { global: { plugins: [router] } })
    await flushPromises()

    await wrapper.get('button.sidebar-back').trigger('click')
    await flushPromises()

    expect(router.currentRoute.value.fullPath).toBe('/')
  })
})
