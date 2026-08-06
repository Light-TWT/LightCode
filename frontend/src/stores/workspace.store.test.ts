import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { flushPromises } from '@vue/test-utils'
import { modelTaskFixture, modelTaskEventsFixture } from '@/fixtures/phase1.fixture'
import type { ChatMessage, ChatSession, TaskEvent } from '@/types/agent'

const { chatMocks, taskMocks, eventMocks, wsMocks } = vi.hoisted(() => ({
  chatMocks: {
    listChatSessions: vi.fn(),
    createChatSession: vi.fn(),
    getChatSession: vi.fn(),
    submitMessage: vi.fn(),
    renameChatSession: vi.fn(),
    deleteChatSession: vi.fn(),
  },
  taskMocks: {
    createRealTask: vi.fn(),
    getRealTask: vi.fn(),
    submitApproval: vi.fn(),
  },
  eventMocks: {
    subscribeRealTaskEvents: vi.fn(),
    subscribeChatEvents: vi.fn(),
  },
  wsMocks: {
    listRegisteredWorkspaces: vi.fn(),
    listFiles: vi.fn(),
    readFile: vi.fn(),
    search: vi.fn(),
  },
}))

vi.mock('@/services/chat.service', () => ({ chatService: chatMocks }))
vi.mock('@/services/real-task.service', () => ({ realTaskService: taskMocks }))
vi.mock('@/services/event.service', () => eventMocks)
vi.mock('@/services/registered-workspace.service', () => ({
  registeredWorkspaceService: wsMocks,
}))

import { useWorkspaceStore } from './workspace.store'

function chatSession(overrides: Partial<ChatSession> = {}): ChatSession {
  return {
    id: 'chat-1',
    workspaceId: 'ws-1',
    title: '新会话',
    status: 'active',
    createdAt: 't',
    updatedAt: 't',
    ...overrides,
  }
}

function chatMessage(sequence: number, overrides: Partial<ChatMessage> = {}): ChatMessage {
  return {
    id: `msg-${sequence}`,
    sessionId: 'chat-1',
    sequence,
    role: 'assistant',
    content: '回答',
    kind: 'message',
    taskId: '',
    createdAt: 't',
    ...overrides,
  }
}

function captureChatSubscription() {
  const calls = eventMocks.subscribeChatEvents.mock.calls
  const last = calls[calls.length - 1]
  return {
    sessionId: last[0] as string,
    onEvent: last[1] as (m: ChatMessage) => void,
    onError: last[2] as (e: Event) => void,
    options: last[3] as { afterSequence?: number; tail?: boolean; onEnd?: () => void },
  }
}

function captureTaskSubscription() {
  const calls = eventMocks.subscribeRealTaskEvents.mock.calls
  const last = calls[calls.length - 1]
  return {
    onEvent: last[1] as (e: TaskEvent) => void,
    options: last[3] as { afterSequence?: number; tail?: boolean; onEnd?: () => void },
  }
}

describe('workspace store：聊天会话与消息（核心 Agent 更新阶段 A）', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    chatMocks.listChatSessions.mockReset().mockResolvedValue([])
    chatMocks.createChatSession.mockReset().mockResolvedValue(chatSession())
    chatMocks.getChatSession.mockReset().mockResolvedValue({ session: chatSession(), messages: [] })
    chatMocks.submitMessage.mockReset().mockResolvedValue({ message: chatMessage(1), taskId: '' })
    chatMocks.renameChatSession.mockReset().mockResolvedValue(chatSession({ title: '新标题' }))
    chatMocks.deleteChatSession.mockReset().mockResolvedValue({ ok: true })
    taskMocks.getRealTask.mockReset().mockResolvedValue(structuredClone(modelTaskFixture))
    taskMocks.submitApproval.mockReset().mockResolvedValue({
      ...structuredClone(modelTaskFixture),
      state: 'completed',
      changeSet: { ...structuredClone(modelTaskFixture.changeSet!), status: 'applied' },
    })
    eventMocks.subscribeChatEvents.mockReset().mockReturnValue(() => {})
    eventMocks.subscribeRealTaskEvents.mockReset().mockReturnValue(() => {})
    wsMocks.listRegisteredWorkspaces.mockReset().mockResolvedValue([])
    wsMocks.listFiles.mockReset().mockResolvedValue([])
    wsMocks.readFile.mockReset().mockResolvedValue({ content: '' })
    wsMocks.search.mockReset().mockResolvedValue([])
  })

  it('createChatSession 创建会话、置为当前会话并订阅 chat 事件流（tail）', async () => {
    const store = useWorkspaceStore()
    const session = await store.createChatSession('ws-1', '新会话')
    expect(session.id).toBe('chat-1')
    expect(store.currentSessionId).toBe('chat-1')
    expect(store.chatSessions).toHaveLength(1)
    const sub = captureChatSubscription()
    expect(sub.sessionId).toBe('chat-1')
    expect(sub.options.tail).toBe(true)
    expect(sub.options.afterSequence).toBe(0)
  })

  it('openChatSession 拉取历史消息并按最新 sequence 续传订阅', async () => {
    const store = useWorkspaceStore()
    chatMocks.getChatSession.mockResolvedValue({
      session: chatSession(),
      messages: [chatMessage(1), chatMessage(2)],
    })
    await store.openChatSession('chat-1', 'ws-1')
    expect(store.messages).toHaveLength(2)
    expect(store.lastChatSequence).toBe(2)
    expect(chatMocks.getChatSession).toHaveBeenCalledWith('chat-1', 'ws-1')
    const sub = captureChatSubscription()
    expect(sub.options.afterSequence).toBe(2)
    expect(sub.options.tail).toBe(true)
  })

  it('submitChatMessage 把返回的持久化消息追加到 messages', async () => {
    const store = useWorkspaceStore()
    store.currentSessionId = 'chat-1'
    store.messages = [chatMessage(1)]
    store.lastChatSequence = 1
    chatMocks.submitMessage.mockResolvedValue({
      message: chatMessage(2, { content: '这是模型回复' }),
      taskId: '',
    })
    await store.submitChatMessage('你好')
    expect(chatMocks.submitMessage).toHaveBeenCalledWith('chat-1', '你好')
    expect(store.messages).toHaveLength(2)
    expect(store.messages[1].content).toBe('这是模型回复')
    expect(store.sending).toBe(false)
  })

  it('taskId 非空时加载关联任务以便审查（edit_summary）', async () => {
    const store = useWorkspaceStore()
    store.currentSessionId = 'chat-1'
    store.messages = []
    chatMocks.submitMessage.mockResolvedValue({
      message: chatMessage(1, { kind: 'edit_summary', taskId: 'chat-task-9' }),
      taskId: 'chat-task-9',
    })
    await store.submitChatMessage('请修改 NOTES.md')
    expect(taskMocks.getRealTask).toHaveBeenCalledWith('chat-task-9')
    // store.task 由 getRealTask 的返回（夹具）填充，用于聊天内审批卡片
    expect(store.task).not.toBeNull()
    expect(store.task?.kind).toBe('model')
  })

  it('submitDecision 构造版本绑定的审批请求（approve）', async () => {
    const store = useWorkspaceStore()
    store.task = structuredClone(modelTaskFixture)
    await store.submitDecision('approve')
    const [taskId, approval] = taskMocks.submitApproval.mock.calls[0] as [
      string,
      { decision: string; changeSetId: string; revision: number; diffHash: string; idempotencyKey: string },
    ]
    expect(taskId).toBe(modelTaskFixture.id)
    expect(approval.decision).toBe('approve')
    expect(approval.changeSetId).toBe('cs-model00000001')
    expect(approval.revision).toBe(1)
    expect(approval.diffHash).toBe('model-diff-hash')
    expect(approval.idempotencyKey).toBeTruthy()
    expect(store.task?.state).toBe('completed')
  })

  it('chat SSE 按 sequence 去重并追加', async () => {
    const store = useWorkspaceStore()
    chatMocks.getChatSession.mockResolvedValue({
      session: chatSession(),
      messages: [chatMessage(1)],
    })
    await store.openChatSession('chat-1', 'ws-1')
    const { onEvent } = captureChatSubscription()
    expect(store.messages).toHaveLength(1)
    onEvent(chatMessage(2, { role: 'user', content: '用户消息经 SSE 送达' }))
    expect(store.messages).toHaveLength(2)
    onEvent(chatMessage(2, { role: 'user', content: '用户消息经 SSE 送达' })) // 重复帧
    expect(store.messages).toHaveLength(2)
    expect(store.lastChatSequence).toBe(2)
  })

  it('切换会话后旧流事件被丢弃', async () => {
    const store = useWorkspaceStore()
    chatMocks.getChatSession.mockResolvedValue({
      session: chatSession(),
      messages: [chatMessage(1)],
    })
    await store.openChatSession('chat-1', 'ws-1')
    const { onEvent } = captureChatSubscription()
    store.currentSessionId = 'chat-2' // 模拟切换到另一会话
    onEvent(chatMessage(2))
    expect(store.messages).toHaveLength(1)
  })

  it('renameChatSession 成功后同步列表标题', async () => {
    const store = useWorkspaceStore()
    store.chatSessions = [chatSession(), chatSession({ id: 'chat-2', title: '第二个' })]
    chatMocks.renameChatSession.mockResolvedValue(chatSession({ title: '新标题' }))

    const ok = await store.renameChatSession('chat-1', '新标题', 'ws-1')

    expect(ok).toBe(true)
    expect(chatMocks.renameChatSession).toHaveBeenCalledWith('chat-1', 'ws-1', '新标题')
    expect(store.chatSessions[0].title).toBe('新标题')
    expect(store.chatSessions[1].title).toBe('第二个')
  })

  it('renameChatSession 失败保留原标题并返回 false', async () => {
    const store = useWorkspaceStore()
    store.chatSessions = [chatSession()]
    chatMocks.renameChatSession.mockRejectedValue(new Error('bad'))

    const ok = await store.renameChatSession('chat-1', '新标题', 'ws-1')

    expect(ok).toBe(false)
    expect(store.chatSessions[0].title).toBe('新会话')
    expect(store.error).toBeTruthy()
  })

  it('deleteChatSession 删除当前会话并切换到剩余列表第一项', async () => {
    const store = useWorkspaceStore()
    store.chatSessions = [chatSession(), chatSession({ id: 'chat-2', title: '第二个' })]
    store.currentSessionId = 'chat-1'
    store.messages = [chatMessage(1)]
    chatMocks.getChatSession.mockResolvedValue({
      session: chatSession({ id: 'chat-2' }),
      messages: [],
    })

    const ok = await store.deleteChatSession('chat-1', 'ws-1')

    expect(ok).toBe(true)
    expect(chatMocks.deleteChatSession).toHaveBeenCalledWith('chat-1', 'ws-1')
    expect(store.chatSessions.map((s) => s.id)).toEqual(['chat-2'])
    expect(store.currentSessionId).toBe('chat-2')
    const sub = captureChatSubscription()
    expect(sub.sessionId).toBe('chat-2')
    expect(sub.options.tail).toBe(true)
  })

  it('deleteChatSession 删除最后一个会话后清空状态', async () => {
    const store = useWorkspaceStore()
    store.chatSessions = [chatSession()]
    store.currentSessionId = 'chat-1'
    store.messages = [chatMessage(1)]

    const ok = await store.deleteChatSession('chat-1', 'ws-1')

    expect(ok).toBe(true)
    expect(store.chatSessions).toHaveLength(0)
    expect(store.currentSessionId).toBeNull()
    expect(store.messages).toHaveLength(0)
  })

  it('deleteChatSession 删除非当前会话不影响当前消息', async () => {
    const store = useWorkspaceStore()
    store.chatSessions = [chatSession(), chatSession({ id: 'chat-2' })]
    store.currentSessionId = 'chat-1'
    store.messages = [chatMessage(1)]

    const ok = await store.deleteChatSession('chat-2', 'ws-1')

    expect(ok).toBe(true)
    expect(store.currentSessionId).toBe('chat-1')
    expect(store.messages).toHaveLength(1)
  })

  it('deleteChatSession 失败时保留列表与当前状态', async () => {
    const store = useWorkspaceStore()
    store.chatSessions = [chatSession()]
    store.currentSessionId = 'chat-1'
    chatMocks.deleteChatSession.mockRejectedValue(new Error('bad'))

    const ok = await store.deleteChatSession('chat-1', 'ws-1')

    expect(ok).toBe(false)
    expect(store.chatSessions).toHaveLength(1)
    expect(store.currentSessionId).toBe('chat-1')
    expect(store.error).toBeTruthy()
  })
})

describe('workspace store：任务 SSE 状态机（WP7 保留行为）', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    taskMocks.getRealTask.mockReset().mockResolvedValue(structuredClone(modelTaskFixture))
    taskMocks.submitApproval.mockReset().mockResolvedValue(structuredClone(modelTaskFixture))
    taskMocks.createRealTask.mockReset().mockResolvedValue(structuredClone(modelTaskFixture))
    eventMocks.subscribeRealTaskEvents.mockReset().mockReturnValue(() => {})
    eventMocks.subscribeChatEvents.mockReset().mockReturnValue(() => {})
    chatMocks.listChatSessions.mockReset().mockResolvedValue([])
    chatMocks.getChatSession.mockReset().mockResolvedValue({ session: chatSession(), messages: [] })
    wsMocks.listFiles.mockReset().mockResolvedValue([])
    wsMocks.listRegisteredWorkspaces.mockReset().mockResolvedValue([])
  })

  it('收到事件后连接状态置为 open，并且 sequence 去重', async () => {
    const store = useWorkspaceStore()
    await store.loadTask(modelTaskFixture.id)
    await flushPromises()
    const { onEvent } = captureTaskSubscription()
    expect(store.eventConnection).toBe('connecting')

    onEvent({ sequence: 1, eventType: 'task.planning', payload: {}, createdAt: 't' })
    onEvent({ sequence: 1, eventType: 'task.planning', payload: {}, createdAt: 't' })

    expect(store.eventConnection).toBe('open')
    expect(store.events.length).toBe(1)
    expect(store.lastSequence).toBe(1)
  })

  it('sequence 缺口触发全量重同步（getRealTask 再次拉取）', async () => {
    const store = useWorkspaceStore()
    await store.loadTask(modelTaskFixture.id)
    await flushPromises()
    const { onEvent } = captureTaskSubscription()
    const before = taskMocks.getRealTask.mock.calls.length

    onEvent({ sequence: 1, eventType: 'task.planning', payload: {}, createdAt: 't' })
    // 收到不连续帧（3），本地 lastSequence=1 → 触发重同步
    onEvent({
      sequence: 3,
      eventType: 'task.generating_diff',
      payload: { changeSetId: 'cs-x', additions: 1, deletions: 0 },
      createdAt: 't',
    })
    await flushPromises()

    expect(taskMocks.getRealTask.mock.calls.length).toBeGreaterThan(before)
  })

  it('订阅真实任务时启用 tail=true，stream.end 后将连接置为 closed', async () => {
    const store = useWorkspaceStore()
    await store.loadTask(modelTaskFixture.id)
    await flushPromises()
    const { options } = captureTaskSubscription()

    // M-01: 真实任务必须持续订阅（tail=true），否则后端回放完就断开
    expect(options).toMatchObject({ afterSequence: 0, tail: true })
    expect(typeof options.onEnd).toBe('function')

    options.onEnd!()
    expect(store.eventConnection).toBe('closed')
  })

  it('modelLifecycle getter 从事件派生有序阶段（模型任务）', async () => {
    const store = useWorkspaceStore()
    store.task = structuredClone(modelTaskFixture)
    store.events = structuredClone(modelTaskEventsFixture)

    const steps = store.modelLifecycle
    expect(steps.map((s) => s.stage)).toEqual([
      'planning',
      'reading',
      'generating',
      'awaiting',
    ])
    expect(steps[0].status).toBe('completed')
    expect(steps[1].status).toBe('completed')
    expect(steps[2].status).toBe('completed')
    expect(steps[3].status).toBe('current')
  })

  it('modelLifecycle 对非模型任务返回空', async () => {
    const store = useWorkspaceStore()
    store.task = { ...structuredClone(modelTaskFixture), kind: 'real' }
    store.events = structuredClone(modelTaskEventsFixture)
    expect(store.modelLifecycle).toEqual([])
  })

  it('失败事件使时间线末步骤标记为 failed', async () => {
    const store = useWorkspaceStore()
    store.task = structuredClone(modelTaskFixture)
    store.events = [
      ...structuredClone(modelTaskEventsFixture).slice(0, 3),
      {
        sequence: 4,
        eventType: 'task.failed',
        payload: { code: 'MODEL_DISABLED', message: 'provider 未启用' },
        createdAt: 't',
      },
    ]
    const steps = store.modelLifecycle
    expect(steps.find((s) => s.stage === 'generating')?.status).toBe('failed')
  })
})
