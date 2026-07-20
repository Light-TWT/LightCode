import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
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
})
