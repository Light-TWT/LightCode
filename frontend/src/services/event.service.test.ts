import { afterEach, describe, expect, it, vi } from 'vitest'
import { subscribeTaskEvents } from './event.service'

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
})
