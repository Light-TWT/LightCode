import { describe, expect, it } from 'vitest'
import {
  ContractValidationError,
  parseRealTask,
  parseRegisteredWorkspace,
  parseTaskEvent,
} from '@/contracts/real-task.schema'

describe('runtime DTO validation', () => {
  it('accepts a well-formed registered workspace', () => {
    const ws = parseRegisteredWorkspace({
      id: 'ws-1',
      displayName: 'Demo',
      enabled: true,
      capabilities: ['read'],
      policyVersion: 'policy-v1',
    })
    expect(ws.id).toBe('ws-1')
  })

  it('rejects a workspace that leaks a real rootPath', () => {
    expect(() =>
      parseRegisteredWorkspace({
        id: 'ws-1',
        displayName: 'Demo',
        enabled: true,
        capabilities: [],
        policyVersion: 'policy-v1',
        rootPath: '/Users/x/proj',
      }),
    ).toThrow(ContractValidationError)
  })

  it('accepts a valid real task and rejects an unknown state', () => {
    const task = parseRealTask({
      id: 'real-1',
      workspaceId: 'ws-1',
      state: 'awaiting_approval',
      title: 't',
    })
    expect(task.state).toBe('awaiting_approval')

    expect(() =>
      parseRealTask({ id: 'real-1', workspaceId: 'ws-1', state: 'exploding', title: 't' }),
    ).toThrow(ContractValidationError)
  })

  it('validates task events', () => {
    const ev = parseTaskEvent({ sequence: 3, eventType: 'task.created', payload: {} })
    expect(ev.sequence).toBe(3)
    expect(() => parseTaskEvent({ sequence: 'x', eventType: 'task.created', payload: {} })).toThrow(
      ContractValidationError,
    )
  })
})
