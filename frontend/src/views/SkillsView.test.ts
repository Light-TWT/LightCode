import { flushPromises, mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import SkillsView from './SkillsView.vue'
import type { SkillDetail, SkillDocument, SkillSummary } from '@/types/agent'

vi.mock('@/services/skills.service', () => ({
  skillsService: {
    list: vi.fn(),
    get: vi.fn(),
    document: vi.fn(),
    upload: vi.fn(),
    setStatus: vi.fn(),
    remove: vi.fn(),
  },
}))

const { skillsService } = await import('@/services/skills.service')

const uploaded: SkillSummary = {
  id: 'skill_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
  name: 'uploaded-helper',
  source: 'uploaded',
  status: 'disabled',
  summary: 'Uploaded helper.',
  documentBytes: 30,
  resourceCount: 1,
  sectionCount: 2,
  createdAt: '2026-08-12T00:00:00Z',
  updatedAt: '2026-08-12T00:00:00Z',
}

const builtin: SkillSummary = {
  id: 'skill_bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb',
  name: 'builtin-helper',
  source: 'builtin',
  status: 'enabled',
  summary: 'Builtin helper.',
  documentBytes: 20,
  resourceCount: 0,
  sectionCount: 1,
  createdAt: '2026-08-12T00:00:00Z',
  updatedAt: '2026-08-12T00:00:00Z',
}

const uploadedDetail: SkillDetail = {
  ...uploaded,
  documentSha256: 'c'.repeat(64),
  packageBytes: 150,
}

const uploadedDocument: SkillDocument = {
  id: uploaded.id,
  name: uploaded.name,
  source: 'uploaded',
  status: 'disabled',
  content: '# uploaded-helper\n\nUploaded helper description.\n',
  documentSha256: 'c'.repeat(64),
}

const mockUpload = vi.mocked(skillsService.upload)
const mockRemove = vi.mocked(skillsService.remove)

async function mountView() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/workspace/:workspaceId/skills', name: 'skills', component: SkillsView },
    ],
  })
  router.push('/workspace/ws-1/skills')
  await router.isReady()
  const wrapper = mount(SkillsView, {
    global: { plugins: [createPinia(), router], stubs: { teleport: true } },
  })
  await flushPromises()
  return wrapper
}

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(skillsService.list).mockResolvedValue([uploaded, builtin])
  vi.mocked(skillsService.get).mockResolvedValue(uploadedDetail)
  vi.mocked(skillsService.document).mockResolvedValue(uploadedDocument)
  vi.mocked(skillsService.setStatus).mockImplementation(async (id, status) => ({
    ...uploadedDetail,
    status,
  }))
})

async function selectFile(wrapper: ReturnType<typeof mount>, file: File) {
  const input = wrapper.get('[data-testid="skill-upload-input"]')
  Object.defineProperty(input.element, 'files', {
    value: [file],
    configurable: true,
  })
  await input.trigger('change')
  await flushPromises()
}

describe('SkillsView', () => {
  it('shows only uploaded Skills after selecting the uploaded filter', async () => {
    const wrapper = await mountView()
    expect(wrapper.findAll('[data-testid="skill-row"]')).toHaveLength(2)

    await wrapper.get('[data-testid="skills-filter-uploaded"]').trigger('click')

    expect(wrapper.text()).toContain('uploaded-helper')
    expect(wrapper.text()).not.toContain('builtin-helper')
    expect(wrapper.findAll('[data-testid="skill-row"]')).toHaveLength(1)
  })

  it('filters by the search query locally', async () => {
    const wrapper = await mountView()
    await wrapper.get('[data-testid="skill-search-input"]').setValue('builtin')

    expect(wrapper.findAll('[data-testid="skill-row"]')).toHaveLength(1)
    expect(wrapper.text()).toContain('builtin-helper')
  })

  it('accepts only zip input and opens a newly uploaded disabled document', async () => {
    mockUpload.mockResolvedValue(uploadedDetail)
    const wrapper = await mountView()

    await selectFile(wrapper, new File(['zip'], 'helper.zip', { type: 'application/zip' }))

    expect(mockUpload).toHaveBeenCalledOnce()
    expect(wrapper.get('[data-testid="skill-detail-overlay"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('启用后可被 Agent 使用')
    expect(wrapper.get('[data-testid="skill-document"]').text()).toContain('# uploaded-helper')
  })

  it('rejects a non-zip selection without uploading', async () => {
    const wrapper = await mountView()

    await selectFile(wrapper, new File(['x'], 'notes.txt', { type: 'text/plain' }))

    expect(mockUpload).not.toHaveBeenCalled()
    expect(wrapper.get('[data-testid="skills-error"]').text()).toBe('仅支持 .zip 技能包。')
  })

  it('requires an in-app confirmation before removing an uploaded Skill', async () => {
    const wrapper = await mountView()

    await wrapper.get('[data-testid="skill-row"]').trigger('click')
    await flushPromises()
    expect(wrapper.get('[data-testid="skill-detail-overlay"]').exists()).toBe(true)

    await wrapper.get('[data-testid="skill-delete-request"]').trigger('click')
    expect(wrapper.get('[data-testid="skill-delete-confirmation"]').exists()).toBe(true)
    expect(mockRemove).not.toHaveBeenCalled()

    await wrapper.get('[data-testid="skill-delete-cancel"]').trigger('click')
    expect(wrapper.find('[data-testid="skill-delete-confirmation"]').exists()).toBe(false)

    await wrapper.get('[data-testid="skill-delete-request"]').trigger('click')
    await wrapper.get('[data-testid="skill-delete-confirm"]').trigger('click')
    await flushPromises()
    expect(mockRemove).toHaveBeenCalledOnce()
    expect(mockRemove).toHaveBeenCalledWith(uploaded.id)
  })

  it('toggle switch calls setStatus and stops row propagation', async () => {
    const wrapper = await mountView()
    const openSpy = vi.mocked(skillsService.get)

    await wrapper.get(`[data-testid="skill-toggle-${uploaded.id}"]`).trigger('click')
    await flushPromises()

    expect(vi.mocked(skillsService.setStatus)).toHaveBeenCalledWith(uploaded.id, 'enabled')
    expect(openSpy).not.toHaveBeenCalled()
  })

  it('never shows a delete control for built-in skills', async () => {
    vi.mocked(skillsService.get).mockResolvedValue({
      ...uploadedDetail,
      id: builtin.id,
      name: builtin.name,
      source: 'builtin',
    })
    vi.mocked(skillsService.document).mockResolvedValue({
      ...uploadedDocument,
      id: builtin.id,
      name: builtin.name,
      source: 'builtin',
    })
    const wrapper = await mountView()

    await wrapper.get(`[data-testid="skill-row"]`).trigger('click')
    await flushPromises()

    expect(wrapper.find('[data-testid="skill-delete-request"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="skill-delete-confirmation"]').exists()).toBe(false)
  })

  it('navigates to the workspace page with the target panel when a nav button is clicked', async () => {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/workspace/:workspaceId/skills', name: 'skills', component: SkillsView },
        { path: '/workspace/:workspaceId', name: 'workspace', component: { template: '<div>ws</div>' } },
      ],
    })
    router.push('/workspace/ws-1/skills')
    await router.isReady()
    const wrapper = mount(SkillsView, {
      global: { plugins: [createPinia(), router], stubs: { teleport: true } },
    })
    await flushPromises()

    await wrapper.get('[data-testid="nav-btn-sessions"]').trigger('click')
    await flushPromises()

    expect(router.currentRoute.value.fullPath).toBe('/workspace/ws-1?panel=sessions')
  })
})