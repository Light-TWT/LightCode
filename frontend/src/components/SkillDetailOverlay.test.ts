import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import SkillDetailOverlay from './SkillDetailOverlay.vue'
import type { SkillDetail, SkillDocument } from '@/types/agent'

const uploadedDetail: SkillDetail = {
  id: 'skill_0123456789abcdef0123456789abcdef',
  name: 'uploaded-helper',
  source: 'uploaded',
  status: 'disabled',
  summary: 'Uploaded helper.',
  documentBytes: 30,
  resourceCount: 1,
  sectionCount: 2,
  createdAt: '2026-08-12T00:00:00Z',
  updatedAt: '2026-08-12T00:00:00Z',
  documentSha256: 'a'.repeat(64),
  packageBytes: 120,
}

const uploadedDocument: SkillDocument = {
  id: uploadedDetail.id,
  name: uploadedDetail.name,
  source: 'uploaded',
  status: 'disabled',
  content: '# uploaded-helper\n\nUploaded helper description.\n',
  documentSha256: 'a'.repeat(64),
}

const builtinDetail: SkillDetail = {
  ...uploadedDetail,
  id: 'skill_22222222222222222222222222222222',
  name: 'builtin-helper',
  source: 'builtin',
  status: 'enabled',
}

const builtinDocument: SkillDocument = {
  ...uploadedDocument,
  id: builtinDetail.id,
  name: 'builtin-helper',
  source: 'builtin',
  status: 'enabled',
}

function mountOverlay(props: Record<string, unknown>) {
  return mount(SkillDetailOverlay, {
    attachTo: document.body,
    props,
    global: { stubs: { teleport: true } },
  })
}

beforeEach(() => {
  document.body.innerHTML = ''
})

afterEach(() => {
  document.body.innerHTML = ''
})

describe('SkillDetailOverlay', () => {
  it('renders document content as text without a nested detail sidebar', () => {
    const wrapper = mountOverlay({
      open: true,
      detail: uploadedDetail,
      document: { ...uploadedDocument, content: '# Title\n\n<img src=x onerror=alert(1)>' },
      updating: false,
      deleting: false,
    })

    expect(document.body.textContent).toContain('<img src=x onerror=alert(1)>')
    expect(document.body.querySelector('img')).toBeNull()
    expect(document.body.querySelector('[data-testid="skill-detail-nav"]')).toBeNull()
    expect(document.body.querySelector('[data-testid="skill-document"]')).not.toBeNull()
    wrapper.unmount()
  })

  it('closes through Escape and restores focus to trigger', async () => {
    const trigger = document.createElement('button')
    document.body.append(trigger)
    trigger.focus()
    const wrapper = mountOverlay({
      open: true,
      detail: uploadedDetail,
      document: uploadedDocument,
      updating: false,
      deleting: false,
    })

    await nextTick()
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }))
    await nextTick()

    expect(wrapper.emitted('close')).toHaveLength(1)
    await wrapper.setProps({ open: false })
    await nextTick()
    expect(document.activeElement).toBe(trigger)
    wrapper.unmount()
  })

  it('closes through a backdrop click', async () => {
    const wrapper = mountOverlay({
      open: true,
      detail: uploadedDetail,
      document: uploadedDocument,
      updating: false,
      deleting: false,
    })
    await nextTick()

    await wrapper.get('[data-testid="skill-detail-overlay"]').trigger('click')

    expect(wrapper.emitted('close')).toHaveLength(1)
    wrapper.unmount()
  })

  it('closes through the close button', async () => {
    const wrapper = mountOverlay({
      open: true,
      detail: uploadedDetail,
      document: uploadedDocument,
      updating: false,
      deleting: false,
    })
    await nextTick()

    await wrapper.get('[data-testid="skill-detail-close"]').trigger('click')

    expect(wrapper.emitted('close')).toHaveLength(1)
    wrapper.unmount()
  })

  it('shows the delete button only for uploaded skills', async () => {
    const uploaded = mountOverlay({
      open: true,
      detail: uploadedDetail,
      document: uploadedDocument,
      updating: false,
      deleting: false,
    })
    await nextTick()
    expect(uploaded.get('[data-testid="skill-delete-request"]').exists()).toBe(true)

    const builtin = mountOverlay({
      open: true,
      detail: builtinDetail,
      document: builtinDocument,
      updating: false,
      deleting: false,
    })
    await nextTick()
    expect(builtin.find('[data-testid="skill-delete-request"]').exists()).toBe(false)
    uploaded.unmount()
    builtin.unmount()
  })

  it('emits setStatus with the inverse status and correct labels', async () => {
    const wrapper = mountOverlay({
      open: true,
      detail: uploadedDetail,
      document: uploadedDocument,
      updating: false,
      deleting: false,
    })
    await nextTick()

    expect(document.body.textContent).toContain('启用后可被 Agent 使用')
    await wrapper.get('[data-testid="skill-enable"]').trigger('click')
    expect(wrapper.emitted('setStatus')).toEqual([['enabled']])

    await wrapper.setProps({
      detail: builtinDetail,
      document: builtinDocument,
    })
    await nextTick()
    expect(document.body.textContent).toContain('当前可被 Agent 使用')
    await wrapper.get('[data-testid="skill-disable"]').trigger('click')
    expect(wrapper.emitted('setStatus')).toEqual([['enabled'], ['disabled']])
    wrapper.unmount()
  })

  it('emits requestDelete on the destructive action', async () => {
    const wrapper = mountOverlay({
      open: true,
      detail: uploadedDetail,
      document: uploadedDocument,
      updating: false,
      deleting: false,
    })
    await nextTick()

    await wrapper.get('[data-testid="skill-delete-request"]').trigger('click')

    expect(wrapper.emitted('requestDelete')).toHaveLength(1)
    wrapper.unmount()
  })

  it('renders nothing when closed', () => {
    const wrapper = mountOverlay({
      open: false,
      detail: uploadedDetail,
      document: uploadedDocument,
      updating: false,
      deleting: false,
    })
    expect(document.body.querySelector('[data-testid="skill-detail-overlay"]')).toBeNull()
    wrapper.unmount()
  })
})