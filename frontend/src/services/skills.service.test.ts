import { describe, expect, it, vi } from 'vitest'
import { skillsService } from './skills.service'

const skill = {
  id: 'skill_0123456789abcdef0123456789abcdef',
  name: 'review-helper',
  source: 'uploaded',
  status: 'disabled',
  summary: 'Review code with evidence.',
  documentBytes: 37,
  resourceCount: 0,
  sectionCount: 1,
  createdAt: '2026-08-12T00:00:00Z',
  updatedAt: '2026-08-12T00:00:00Z',
}

const skillDetail = {
  ...skill,
  documentSha256: 'a'.repeat(64),
  packageBytes: 123,
}

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

afterEach(() => {
  vi.unstubAllGlobals()
})

it('uploads only the selected ZIP as the package field', async () => {
  const fetchMock = vi.fn().mockResolvedValue(jsonResponse(skillDetail))
  vi.stubGlobal('fetch', fetchMock)

  await skillsService.upload(new File(['zip'], 'review.zip', { type: 'application/zip' }))

  const [, init] = fetchMock.mock.calls[0]
  expect(init.method).toBe('POST')
  expect(init.body).toBeInstanceOf(FormData)
  expect((init.body as FormData).get('package')).toBeInstanceOf(File)
  expect((init.body as FormData).get('status')).toBeNull()
  expect(init.headers).toBeUndefined()
})

it('rejects a response that leaks a storage path', async () => {
  const { ContractValidationError } = await import('@/contracts/real-task.schema')
  vi.stubGlobal(
    'fetch',
    vi.fn().mockImplementation(() =>
      Promise.resolve(jsonResponse([{ ...skill, storagePath: 'C:/data' }])),
    ),
  )
  await expect(skillsService.list()).rejects.toThrow(ContractValidationError)
  await expect(skillsService.list()).rejects.toThrow(/路径/)
})

it('rejects unknown status values and malformed ids', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse({ ...skill, status: 'active' })))
  await expect(skillsService.list()).rejects.toThrow()

  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue(jsonResponse({ ...skill, id: '../skills' })),
  )
  await expect(skillsService.list()).rejects.toThrow()
})

it('maps HTTP error detail into the thrown error', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: 'SKILL_ALREADY_EXISTS', message: '同名技能已存在。' }), {
        status: 400,
        headers: { 'Content-Type': 'application/json' },
      }),
    ),
  )
  await expect(skillsService.upload(new File(['z'], 'a.zip', { type: 'application/zip' }))).rejects.toThrow(
    'SKILL_ALREADY_EXISTS',
  )
})

it('parses document and delete responses strictly', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue(
      jsonResponse({
        ...skill,
        content: '# review-helper',
        documentSha256: 'a'.repeat(64),
      }),
    ),
  )
  const document = await skillsService.document(skill.id)
  expect(document.content).toBe('# review-helper')

  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue(jsonResponse({ id: skill.id, deleted: true })),
  )
  const result = await skillsService.remove(skill.id)
  expect(result).toEqual({ id: skill.id, deleted: true })
})

it('sends strict json bodies for status updates', async () => {
  const fetchMock = vi.fn().mockResolvedValue(jsonResponse(skillDetail))
  vi.stubGlobal('fetch', fetchMock)

  await skillsService.setStatus(skill.id, 'enabled')

  const [, init] = fetchMock.mock.calls[0]
  expect(init.method).toBe('PATCH')
  expect(JSON.parse(init.body as string)).toEqual({ status: 'enabled' })
})