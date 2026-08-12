import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { skillsService } from '@/services/skills.service'
import { useSkillsStore } from './skills.store'
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

const disabledUploaded: SkillSummary = {
  id: 'skill_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
  name: 'uploaded-helper',
  source: 'uploaded',
  status: 'disabled',
  summary: 'Uploaded helper.',
  documentBytes: 12,
  resourceCount: 0,
  sectionCount: 1,
  createdAt: '2026-08-12T00:00:00Z',
  updatedAt: '2026-08-12T00:00:00Z',
}

const enabledBuiltin: SkillSummary = {
  id: 'skill_bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb',
  name: 'builtin-helper',
  source: 'builtin',
  status: 'enabled',
  summary: 'Builtin helper.',
  documentBytes: 10,
  resourceCount: 0,
  sectionCount: 1,
  createdAt: '2026-08-12T00:00:00Z',
  updatedAt: '2026-08-12T00:00:00Z',
}

const disabledUploadedDetail: SkillDetail = {
  ...disabledUploaded,
  documentSha256: 'c'.repeat(64),
  packageBytes: 100,
}

const disabledUploadedDocument: SkillDocument = {
  id: disabledUploaded.id,
  name: disabledUploaded.name,
  source: 'uploaded',
  status: 'disabled',
  content: '# uploaded-helper\n\nUploaded helper.\n',
  documentSha256: 'c'.repeat(64),
}

beforeEach(() => {
  setActivePinia(createPinia())
  vi.clearAllMocks()
})

it('filters loaded summaries locally without modifying the API list', async () => {
  vi.mocked(skillsService.list).mockResolvedValue([disabledUploaded, enabledBuiltin])
  const store = useSkillsStore()
  await store.load()

  store.query = 'upload'
  store.sourceFilter = 'uploaded'

  expect(store.filtered).toEqual([disabledUploaded])
  expect(store.items).toHaveLength(2)

  store.query = ''
  store.sourceFilter = 'all'
  expect(store.filtered).toHaveLength(2)
})

it('opens the uploaded detail still disabled', async () => {
  vi.mocked(skillsService.upload).mockResolvedValue(disabledUploadedDetail)
  vi.mocked(skillsService.document).mockResolvedValue(disabledUploadedDocument)
  const store = useSkillsStore()

  await store.upload(new File(['zip'], 'uploaded.zip', { type: 'application/zip' }))

  expect(store.detail?.status).toBe('disabled')
  expect(store.document?.content).toContain('# uploaded-helper')
  expect(store.uploading).toBe(false)
  expect(store.items[0].status).toBe('disabled')
})

it('rejects non-zip files before any request', async () => {
  const store = useSkillsStore()
  await store.upload(new File(['x'], 'notes.txt', { type: 'text/plain' }))

  expect(skillsService.upload).not.toHaveBeenCalled()
  expect(store.error).toBe('仅支持 .zip 技能包。')
})

it('rolls a toggle back after a rejected status request', async () => {
  vi.mocked(skillsService.setStatus).mockRejectedValue(new Error('SKILL_STORAGE_FAILED'))
  const store = useSkillsStore()
  store.items = [disabledUploaded]
  store.detail = disabledUploadedDetail
  store.document = disabledUploadedDocument

  await store.setStatus(disabledUploaded.id, 'enabled')

  expect(store.items[0].status).toBe('disabled')
  expect(store.detail?.status).toBe('disabled')
  expect(store.document?.status).toBe('disabled')
  expect(store.error).toBe('技能状态更新失败，请稍后重试。')
  expect(store.updatingId).toBeNull()
})

it('applies an accepted status change and does not surface raw errors', async () => {
  vi.mocked(skillsService.setStatus).mockResolvedValue({
    ...disabledUploadedDetail,
    status: 'enabled',
  })
  const store = useSkillsStore()
  store.items = [disabledUploaded]

  await store.setStatus(disabledUploaded.id, 'enabled')

  expect(store.items[0].status).toBe('enabled')
  expect(store.error).toBeNull()
})

it('removes only after the API succeeds and clears the open detail', async () => {
  vi.mocked(skillsService.remove).mockResolvedValue({ id: disabledUploaded.id, deleted: true })
  const store = useSkillsStore()
  store.items = [disabledUploaded, enabledBuiltin]
  store.detail = disabledUploadedDetail
  store.document = disabledUploadedDocument

  await store.remove(disabledUploaded.id)

  expect(store.items.map((item) => item.id)).toEqual([enabledBuiltin.id])
  expect(store.detail).toBeNull()
  expect(store.document).toBeNull()
  expect(store.deletingId).toBeNull()
})

it('keeps the item on a failed delete', async () => {
  vi.mocked(skillsService.remove).mockRejectedValue(new Error('SKILL_DELETE_DENIED'))
  const store = useSkillsStore()
  store.items = [disabledUploaded]

  await store.remove(disabledUploaded.id)

  expect(store.items).toHaveLength(1)
  expect(store.error).toBe('内置技能不可删除。')
})

it('load failure uses the fixed fallback text', async () => {
  vi.mocked(skillsService.list).mockRejectedValue(new Error('raw internal detail'))
  const store = useSkillsStore()

  await store.load()

  expect(store.error).toBe('技能操作失败，请稍后重试。')
  expect(store.loading).toBe(false)
})