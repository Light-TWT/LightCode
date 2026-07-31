import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import type { ModelTaskResponse } from '@/types/agent'

// 通过 vi.doMock 隔离 model-task.service，验证 store 对 awaiting_approval / failed 的路由。
const okResp: ModelTaskResponse = {
  id: 'model-task-1',
  workspaceId: 'ws-1',
  state: 'awaiting_approval',
  changeSetId: 'cs-1',
  detail: '候选变更集已生成',
}
const failedResp: ModelTaskResponse = {
  id: 'model-task-2',
  workspaceId: 'ws-1',
  state: 'failed',
  changeSetId: null,
  detail: 'MODEL_DISABLED: provider 未启用',
}

describe('real store createModelTask', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.resetModules()
  })

  it('返回响应、不报错（awaiting_approval）', async () => {
    vi.doMock('@/services/model-task.service', () => ({
      modelTaskService: { createModelTask: vi.fn(async () => okResp) },
    }))
    const { useRealStore } = await import('@/stores/real.store')
    const store = useRealStore()

    const resp = await store.createModelTask('ws-1', 't')

    expect(resp).toEqual(okResp)
    expect(store.error).toBeNull()
  })

  it('failed 时设置 error 并返回 null，供 UI 显示而不导航', async () => {
    vi.doMock('@/services/model-task.service', () => ({
      modelTaskService: { createModelTask: vi.fn(async () => failedResp) },
    }))
    const { useRealStore } = await import('@/stores/real.store')
    const store = useRealStore()

    const resp = await store.createModelTask('ws-1', 't')

    expect(resp).toBeNull()
    expect(store.error).toContain('MODEL_DISABLED')
  })
})
