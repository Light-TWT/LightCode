import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createWebHistory } from 'vue-router'
import { beforeEach, describe, expect, it } from 'vitest'
import SessionHistoryView from './SessionHistoryView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/workspace/:id/history', name: 'session-history', component: SessionHistoryView },
    { path: '/workspace/:id', name: 'agent-workspace', component: { template: '<div>workspace</div>' } },
  ],
})

describe('SessionHistoryView', () => {
  beforeEach(async () => {
    setActivePinia(createPinia())
    await router.push('/workspace/workspace-login-service/history')
  })

  it('shows 8 timeline entries with filter chips', async () => {
    const wrapper = mount(SessionHistoryView, { global: { plugins: [router] } })
    await flushPromises()

    const entries = wrapper.findAll('[data-testid="task-entry"]')
    expect(entries.length).toBe(8)

    const chips = wrapper.findAll('[data-testid="filter-chip"]')
    expect(chips.length).toBe(5)
    expect(chips[0].text()).toContain('全部')
  })

  it('filters entries by status', async () => {
    const wrapper = mount(SessionHistoryView, { global: { plugins: [router] } })
    await flushPromises()

    const chips = wrapper.findAll('[data-testid="filter-chip"]')
    await chips[2].trigger('click')

    const visible = wrapper.findAll('[data-testid="task-entry"]:not([style*="display: none"])')
    expect(visible.length).toBe(4)
    visible.forEach(e => expect(e.classes()).toContain('status-done'))
  })

  it('search filters by text content', async () => {
    const wrapper = mount(SessionHistoryView, { global: { plugins: [router] } })
    await flushPromises()

    const search = wrapper.get('[data-testid="search-input"]')
    await search.setValue('OA')

    const visible = wrapper.findAll('[data-testid="task-entry"]:not([style*="display: none"])')
    expect(visible.length).toBe(1)
    expect(visible[0].text()).toContain('OAuth2')
  })

  it('waiting entry shows 继续审查 button and does not open detail on click', async () => {
    const wrapper = mount(SessionHistoryView, { global: { plugins: [router] } })
    await flushPromises()

    const firstEntry = wrapper.findAll('[data-testid="task-entry"]')[0]
    expect(firstEntry.find('[data-testid="action-review"]').exists()).toBe(true)

    // click row itself should not open detail for waiting tasks
    await firstEntry.trigger('click')
    expect(wrapper.find('[data-testid="detail-panel"]').exists()).toBe(false)
  })

  it('opens detail drawer for completed task and shows plan/tools/files', async () => {
    const wrapper = mount(SessionHistoryView, { global: { plugins: [router] } })
    await flushPromises()

    const doneEntry = wrapper.findAll('[data-testid="task-entry"]')[1]
    await doneEntry.trigger('click')

    const panel = wrapper.find('[data-testid="detail-panel"]')
    expect(panel.exists()).toBe(true)
    expect(panel.text()).toContain('已完成')
    expect(panel.text()).toContain('日期格式化')
    expect(panel.text()).toContain('Agent 计划')
    expect(panel.text()).toContain('工具调用')
    expect(panel.text()).toContain('文件变更')
    expect(panel.text()).toContain('审批记录')
  })

  it('opens detail for failed task and shows fail alert', async () => {
    const wrapper = mount(SessionHistoryView, { global: { plugins: [router] } })
    await flushPromises()

    const failEntry = wrapper.findAll('[data-testid="task-entry"]')[2]
    await failEntry.trigger('click')

    expect(wrapper.find('[data-testid="detail-panel"]').text()).toContain('依赖缺失')
  })

  it('opens detail for cancelled task and shows cancel info', async () => {
    const wrapper = mount(SessionHistoryView, { global: { plugins: [router] } })
    await flushPromises()

    const cancelEntry = wrapper.findAll('[data-testid="task-entry"]')[7]
    await cancelEntry.trigger('click')

    expect(wrapper.find('[data-testid="detail-panel"]').text()).toContain('用户取消')
  })

  it('closes detail drawer', async () => {
    const wrapper = mount(SessionHistoryView, { global: { plugins: [router] } })
    await flushPromises()

    await wrapper.findAll('[data-testid="task-entry"]')[1].trigger('click')
    expect(wrapper.find('[data-testid="detail-panel"]').exists()).toBe(true)

    await wrapper.get('[data-testid="detail-close-btn"]').trigger('click')
    expect(wrapper.find('[data-testid="detail-panel"]').exists()).toBe(false)
  })

  it('shows waiting entry as primary style with review action', async () => {
    const wrapper = mount(SessionHistoryView, { global: { plugins: [router] } })
    await flushPromises()

    const entries = wrapper.findAll('[data-testid="task-entry"]')
    expect(entries[0].classes()).toContain('primary')
    expect(entries[0].find('[data-testid="action-review"]').exists()).toBe(true)
  })
})
