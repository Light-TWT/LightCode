import { afterEach, describe, expect, it, vi } from 'vitest'
import { subscribeChatEvents, subscribeRealTaskEvents } from './event.service'

const chatMessagePayload = {
  id: 'msg-1',
  sessionId: 'chat-1',
  sequence: 2,
  role: 'assistant',
  content: '你好',
  kind: 'message',
  taskId: '',
  createdAt: 't',
}

describe('subscribeRealTaskEvents', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  function mockEventSource() {
    const close = vi.fn()
    const addEventListener = vi.fn()
    vi.stubGlobal('EventSource', vi.fn(function () {
      return { close, addEventListener }
    }))
    return { close, addEventListener }
  }

  it('returns an unsubscribe function that closes the connection', () => {
    const { close } = mockEventSource()

    const unsubscribe = subscribeRealTaskEvents('task-1', vi.fn(), vi.fn())
    expect(typeof unsubscribe).toBe('function')

    unsubscribe()
    expect(close).toHaveBeenCalledTimes(1)
  })

  it('registers task.event, error, and stream.end listeners', () => {
    const { addEventListener } = mockEventSource()

    subscribeRealTaskEvents('task-1', vi.fn(), vi.fn())

    const events = addEventListener.mock.calls.map((c: unknown[]) => c[0])
    expect(events).toContain('task.event')
    expect(events).toContain('error')
    expect(events).toContain('stream.end')
  })

  it('closes the connection and calls onEnd on stream.end', () => {
    const { close, addEventListener } = mockEventSource()
    const onEnd = vi.fn()

    subscribeRealTaskEvents('real-task-1', vi.fn(), vi.fn(), { tail: true, onEnd })

    const endHandler = addEventListener.mock.calls.find((c: unknown[]) => c[0] === 'stream.end')?.[1]
    expect(typeof endHandler).toBe('function')
    ;(endHandler as () => void)()

    expect(close).toHaveBeenCalledTimes(1)
    expect(onEnd).toHaveBeenCalledTimes(1)
  })

  it('connects to the real-task endpoint with resume params', () => {
    mockEventSource()

    subscribeRealTaskEvents('real-task-1', vi.fn(), vi.fn(), { afterSequence: 7, tail: true })

    const ctor = globalThis.EventSource as unknown as ReturnType<typeof vi.fn>
    const url = ctor.mock.calls[0][0] as string
    expect(url).toContain('/real-tasks/real-task-1/events')
    expect(url).toContain('after_sequence=7')
    expect(url).toContain('tail=true')
  })

  it('omits resume params when not provided', () => {
    mockEventSource()

    subscribeRealTaskEvents('real-task-1', vi.fn(), vi.fn())

    const ctor = globalThis.EventSource as unknown as ReturnType<typeof vi.fn>
    const url = ctor.mock.calls[0][0] as string
    expect(url).not.toContain('?')
  })
})

describe('subscribeChatEvents（核心 Agent 更新阶段 A）', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  function mockEventSource() {
    const close = vi.fn()
    const addEventListener = vi.fn()
    vi.stubGlobal('EventSource', vi.fn(function () {
      return { close, addEventListener }
    }))
    return { close, addEventListener }
  }

  it('connects to the chat endpoint with resume params', () => {
    mockEventSource()

    subscribeChatEvents('chat-1', vi.fn(), vi.fn(), { afterSequence: 5, tail: true })

    const ctor = globalThis.EventSource as unknown as ReturnType<typeof vi.fn>
    const url = ctor.mock.calls[0][0] as string
    expect(url).toContain('/chat-sessions/chat-1/events')
    expect(url).toContain('after_sequence=5')
    expect(url).toContain('tail=true')
  })

  it('listens for chat.event and parses ChatMessage payloads', () => {
    const { addEventListener } = mockEventSource()
    const onEvent = vi.fn()

    subscribeChatEvents('chat-1', onEvent, vi.fn())

    const events = addEventListener.mock.calls.map((c: unknown[]) => c[0])
    expect(events).toContain('chat.event')

    const chatHandler = addEventListener.mock.calls.find((c: unknown[]) => c[0] === 'chat.event')?.[1]
    ;(chatHandler as (e: MessageEvent) => void)({
      data: JSON.stringify(chatMessagePayload),
    } as MessageEvent)

    expect(onEvent).toHaveBeenCalledTimes(1)
    expect(onEvent.mock.calls[0][0]).toMatchObject({
      sessionId: 'chat-1',
      sequence: 2,
      kind: 'message',
    })
  })

  it('drops malformed chat.event frames instead of crashing', () => {
    const { addEventListener } = mockEventSource()
    const onEvent = vi.fn()

    subscribeChatEvents('chat-1', onEvent, vi.fn())

    const chatHandler = addEventListener.mock.calls.find((c: unknown[]) => c[0] === 'chat.event')?.[1]
    ;(chatHandler as (e: MessageEvent) => void)({ data: '{broken' } as MessageEvent)
    ;(chatHandler as (e: MessageEvent) => void)({
      data: JSON.stringify({ ...chatMessagePayload, role: 'hacker' }),
    } as MessageEvent)

    expect(onEvent).not.toHaveBeenCalled()
  })
})
