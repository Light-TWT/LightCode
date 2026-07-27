import { afterEach, describe, expect, it, vi } from 'vitest'
import { realTaskFixture } from '@/fixtures/phase1.fixture'
import { httpRealTaskService, mockRealTaskService } from './real-task.service'

describe('mockRealTaskService', () => {
  it('creates a real task in awaiting_approval with an active changeset', async () => {
    const task = await mockRealTaskService.createRealTask({
      workspaceId: 'demo-real-workspace',
      title: '测试任务',
    })

    expect(task.kind).toBe('real')
    expect(task.state).toBe('awaiting_approval')
    expect(task.title).toBe('测试任务')
    expect(task.changeSet?.status).toBe('active')
    expect(task.changeSet?.revision).toBe(1)
  })

  it('approve moves task to completed with applied changeset and passed verification', async () => {
    const cs = realTaskFixture.changeSet!
    const task = await mockRealTaskService.submitApproval(realTaskFixture.id, {
      decision: 'approve',
      changeSetId: cs.changeSetId,
      revision: cs.revision,
      diffHash: cs.diffHash,
      idempotencyKey: 'idem-test-1',
    })

    expect(task.state).toBe('completed')
    expect(task.changeSet?.status).toBe('applied')
    expect(task.verification.status).toBe('passed')
  })

  it('reject moves task to cancelled with rejected changeset', async () => {
    const cs = realTaskFixture.changeSet!
    const task = await mockRealTaskService.submitApproval(realTaskFixture.id, {
      decision: 'reject',
      changeSetId: cs.changeSetId,
      revision: cs.revision,
      diffHash: cs.diffHash,
      idempotencyKey: 'idem-test-2',
    })

    expect(task.state).toBe('cancelled')
    expect(task.changeSet?.status).toBe('rejected')
  })
})

describe('httpRealTaskService', () => {
  afterEach(() => {
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
  })

  function stubFetch(payload: unknown) {
    const fetchMock = vi.fn(async () => ({
      ok: true,
      json: async () => payload,
    }))
    vi.stubGlobal('fetch', fetchMock)
    return fetchMock
  }

  it('posts create request with exactly the contract fields', async () => {
    const fetchMock = stubFetch(realTaskFixture)

    await httpRealTaskService.createRealTask({ workspaceId: 'ws-1', title: 't' })

    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit]
    expect(url).toContain('/real-tasks')
    expect(init.method).toBe('POST')
    const body = JSON.parse(init.body as string)
    // 后端 CreateRealTaskRequest 为 extra=forbid：字段必须严格一致
    expect(Object.keys(body).sort()).toEqual(['templateId', 'title', 'workspaceId'])
    expect(body.templateId).toBe('append-marker')
  })

  it('posts approval with exactly the version-bound contract fields', async () => {
    const fetchMock = stubFetch(realTaskFixture)

    await httpRealTaskService.submitApproval('task-1', {
      decision: 'approve',
      changeSetId: 'cs-1',
      revision: 1,
      diffHash: 'hash',
      idempotencyKey: 'idem-1',
    })

    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit]
    expect(url).toContain('/real-tasks/task-1/approval')
    const body = JSON.parse(init.body as string)
    // 后端 ApprovalRequest 为 extra=forbid：不得携带 rootPath/filePath/patch 等字段
    expect(Object.keys(body).sort()).toEqual([
      'changeSetId',
      'decision',
      'diffHash',
      'idempotencyKey',
      'revision',
    ])
  })
})
