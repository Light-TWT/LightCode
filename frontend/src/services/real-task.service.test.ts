import { afterEach, describe, expect, it, vi } from 'vitest'
import { realTaskFixture } from '@/fixtures/phase1.fixture'
import { realTaskService } from './real-task.service'

describe('realTaskService（HTTP-only）', () => {
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

    await realTaskService.createRealTask({ workspaceId: 'ws-1', title: 't' })

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

    await realTaskService.submitApproval('task-1', {
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

  it('gets a task by id and parses the changeset view', async () => {
    const fetchMock = stubFetch(realTaskFixture)
    const task = await realTaskService.getRealTask('real-task-demo0001')
    expect(String(fetchMock.mock.calls[0][0])).toContain('/real-tasks/real-task-demo0001')
    expect(task.state).toBe('awaiting_approval')
    expect(task.changeSet?.changeSetId).toBe('cs-demo00000001')
    expect(JSON.stringify(task)).not.toContain('rootPath')
  })
})
