import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { flushPromises } from '@vue/test-utils'
import { modelTaskFixture, modelTaskEventsFixture } from '@/fixtures/phase1.fixture'
import type { ModelTaskResponse, TaskEvent } from '@/types/agent'

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

describe('real store 模型任务 SSE（WP7）', () => {
  let capturedOnEvent: ((event: TaskEvent) => void) | null = null
  let capturedOptions: { afterSequence?: number; tail?: boolean; onEnd?: () => void } | null = null
  let getRealTaskCalls: number

  beforeEach(() => {
    setActivePinia(createPinia())
    vi.resetModules()
    capturedOnEvent = null
    capturedOptions = null
    getRealTaskCalls = 0

    // API 模式下才连接 SSE
    vi.doMock('@/config/runtime', () => ({ isApiMode: true }))
    // 捕获订阅回调，便于在测试中手动注入事件帧
    vi.doMock('@/services/event.service', () => ({
      subscribeRealTaskEvents: (
        _id: string,
        onEvent: (e: TaskEvent) => void,
        _onError: (e: Event) => void,
        options?: { afterSequence?: number; tail?: boolean; onEnd?: () => void },
      ) => {
        capturedOnEvent = onEvent
        capturedOptions = options ?? null
        return () => {}
      },
      subscribeTaskEvents: () => () => {},
    }))
    vi.doMock('@/services/real-task.service', () => ({
      realTaskService: {
        getRealTask: vi.fn(async () => {
          getRealTaskCalls++
          return structuredClone(modelTaskFixture)
        }),
        createRealTask: vi.fn(async () => structuredClone(modelTaskFixture)),
        submitApproval: vi.fn(async () => structuredClone(modelTaskFixture)),
      },
    }))
    vi.doMock('@/services/model-task.service', () => ({
      modelTaskService: { createModelTask: vi.fn(async () => null) },
    }))
  })

  it('收到事件后连接状态置为 open，并且 sequence 去重', async () => {
    const { useRealStore } = await import('@/stores/real.store')
    const store = useRealStore()
    await store.loadTask(modelTaskFixture.id)
    await flushPromises()
    expect(capturedOnEvent).not.toBeNull()
    expect(store.eventConnection).toBe('connecting')

    capturedOnEvent!({ sequence: 1, eventType: 'task.planning', payload: {}, createdAt: 't' })
    capturedOnEvent!({ sequence: 1, eventType: 'task.planning', payload: {}, createdAt: 't' })

    expect(store.eventConnection).toBe('open')
    expect(store.events.length).toBe(1)
    expect(store.lastSequence).toBe(1)
  })

  it('sequence 缺口触发全量重同步（loadTask 再次拉取）', async () => {
    const { useRealStore } = await import('@/stores/real.store')
    const store = useRealStore()
    await store.loadTask(modelTaskFixture.id)
    await flushPromises()
    const before = getRealTaskCalls
    expect(before).toBeGreaterThanOrEqual(1)

    capturedOnEvent!({ sequence: 1, eventType: 'task.planning', payload: {}, createdAt: 't' })
    // 收到不连续帧（3），本地 lastSequence=1 → 触发重同步
    capturedOnEvent!({ sequence: 3, eventType: 'task.generating_diff', payload: { changeSetId: 'cs-x', additions: 1, deletions: 0 }, createdAt: 't' })
    await flushPromises()

    expect(getRealTaskCalls).toBeGreaterThan(before)
  })

  it('订阅真实任务时启用 tail=true，stream.end 后将连接置为 closed', async () => {
    const { useRealStore } = await import('@/stores/real.store')
    const store = useRealStore()
    await store.loadTask(modelTaskFixture.id)
    await flushPromises()

    // M-01: 真实任务必须持续订阅（tail=true），否则后端回放完就断开
    expect(capturedOptions).toMatchObject({ afterSequence: 0, tail: true })
    expect(typeof capturedOptions?.onEnd).toBe('function')

    // 服务端正常结束（tail 超时或 stream.end）后连接状态必须是 closed 而非 open
    capturedOptions!.onEnd!()
    expect(store.eventConnection).toBe('closed')
  })

  it('modelLifecycle getter 从事件派生有序阶段（模型任务）', async () => {
    const { useRealStore } = await import('@/stores/real.store')
    const store = useRealStore()
    store.task = structuredClone(modelTaskFixture)
    store.events = structuredClone(modelTaskEventsFixture)

    const steps = store.modelLifecycle
    expect(steps.map((s) => s.stage)).toEqual([
      'planning',
      'reading',
      'generating',
      'awaiting',
    ])
    // 前三个阶段已完成，awaiting 为当前（终态前置）
    expect(steps[0].status).toBe('completed')
    expect(steps[1].status).toBe('completed')
    expect(steps[2].status).toBe('completed')
    expect(steps[3].status).toBe('current')
  })

  it('modelLifecycle 对非模型任务返回空', async () => {
    const { useRealStore } = await import('@/stores/real.store')
    const store = useRealStore()
    store.task = { ...structuredClone(modelTaskFixture), kind: 'real' }
    store.events = structuredClone(modelTaskEventsFixture)
    expect(store.modelLifecycle).toEqual([])
  })

  it('失败事件使时间线末步骤标记为 failed', async () => {
    const { useRealStore } = await import('@/stores/real.store')
    const store = useRealStore()
    store.task = structuredClone(modelTaskFixture)
    store.events = [
      ...structuredClone(modelTaskEventsFixture).slice(0, 3),
      { sequence: 4, eventType: 'task.failed', payload: { code: 'MODEL_DISABLED', message: 'provider 未启用' }, createdAt: 't' },
    ]
    const steps = store.modelLifecycle
    expect(steps.find((s) => s.stage === 'generating')?.status).toBe('failed')
  })
})
