import { afterEach, describe, expect, it, vi } from 'vitest'
import { httpModelTaskService, mockModelTaskService } from './model-task.service'
import { ContractValidationError } from '@/contracts/real-task.schema'

describe('mockModelTaskService', () => {
  it('returns awaiting_approval with a changeset id', async () => {
    const resp = await mockModelTaskService.createModelTask({
      workspaceId: 'demo-real-workspace',
      title: '让模型追加标记',
    })

    expect(resp.state).toBe('awaiting_approval')
    expect(resp.changeSetId).toBeTruthy()
    expect(resp.workspaceId).toBe('demo-real-workspace')
    expect(resp.detail).toContain('候选变更集')
  })
})

describe('httpModelTaskService', () => {
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

  it('posts only workspaceId + title to /model-tasks (extra=forbid 契约)', async () => {
    const fetchMock = stubFetch({
      id: 'model-task-1',
      workspaceId: 'ws-1',
      state: 'awaiting_approval',
      changeSetId: 'cs-1',
      detail: 'ok',
    })

    await httpModelTaskService.createModelTask({ workspaceId: 'ws-1', title: 't' })

    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit]
    expect(url).toContain('/model-tasks')
    expect(init.method).toBe('POST')
    const body = JSON.parse(init.body as string)
    // 后端 ModelTaskCreateRequest 为 extra=forbid：不得携带 rootPath/path/templateId 等字段
    expect(Object.keys(body).sort()).toEqual(['title', 'workspaceId'])
  })

  it('parses a failed response without a changeset', async () => {
    const fetchMock = stubFetch({
      id: 'model-task-2',
      workspaceId: 'ws-1',
      state: 'failed',
      changeSetId: null,
      detail: 'MODEL_DISABLED: provider 未启用',
    })

    const resp = await httpModelTaskService.createModelTask({ workspaceId: 'ws-1', title: 't' })
    expect(resp.state).toBe('failed')
    expect(resp.changeSetId).toBeNull()
    expect(resp.detail).toContain('MODEL_DISABLED')
    expect(fetchMock).toBeDefined()
  })

  it('rejects a response that smuggles rootPath (契约不兼容)', async () => {
    stubFetch({
      id: 'model-task-3',
      workspaceId: 'ws-1',
      state: 'awaiting_approval',
      changeSetId: 'cs-3',
      detail: 'ok',
      rootPath: '/etc',
    })

    await expect(
      httpModelTaskService.createModelTask({ workspaceId: 'ws-1', title: 't' }),
    ).rejects.toBeInstanceOf(ContractValidationError)
  })
})
