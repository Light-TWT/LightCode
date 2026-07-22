import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import { beforeEach, describe, expect, it } from 'vitest'
import AgentWorkspaceView from './AgentWorkspaceView.vue'

describe('AgentWorkspaceView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('opens the full diff only in the review drawer', async () => {
    const wrapper = mount(AgentWorkspaceView)
    await flushPromises()

    expect(wrapper.find('[data-testid="review-drawer"]').exists()).toBe(false)

    await wrapper.get('button[aria-label="审查修改"]').trigger('click')

    expect(wrapper.get('[data-testid="review-drawer"]').text()).toContain('左右对比')
    expect(wrapper.get('[data-testid="review-drawer"]').text()).toContain('Invalid username')
  })

  it('expands a tool result and displays verification after approval', async () => {
    const wrapper = mount(AgentWorkspaceView)
    await flushPromises()

    await wrapper.get('[data-testid="tool-read-login"]').trigger('click')
    expect(wrapper.text()).toContain('Missing credentials')

    await wrapper.get('button[aria-label="审查修改"]').trigger('click')
    await wrapper.get('button[aria-label="批准修改"]').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('3 passed in 0.12s')
  })

  it('opens the current workspace task history from the sidebar', async () => {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/workspace/:id', component: AgentWorkspaceView },
        { path: '/workspace/:id/history', name: 'session-history', component: AgentWorkspaceView },
      ],
    })
    await router.push('/workspace/workspace-login-service')
    await router.isReady()

    const wrapper = mount(AgentWorkspaceView, {
      global: { plugins: [router] },
    })
    await flushPromises()

    await wrapper.get('[data-testid="task-history-link"]').trigger('click')
    await flushPromises()

    expect(router.currentRoute.value.fullPath).toBe('/workspace/workspace-login-service/history')
  })
})
