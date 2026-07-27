import { afterEach, describe, expect, it, vi } from 'vitest'
import { subscribeRealTaskEvents, subscribeTaskEvents } from './event.service'

describe('subscribeTaskEvents', () => {
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

    const unsubscribe = subscribeTaskEvents('task-1', vi.fn(), vi.fn())
    expect(typeof unsubscribe).toBe('function')

    unsubscribe()
    expect(close).toHaveBeenCalledTimes(1)
  })

  it('registers task.event, error, and stream.end listeners', () => {
    const { addEventListener } = mockEventSource()

    subscribeTaskEvents('task-1', vi.fn(), vi.fn())

    const events = addEventListener.mock.calls.map((c: unknown[]) => c[0])
    expect(events).toContain('task.event')
    expect(events).toContain('error')
    expect(events).toContain('stream.end')
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
