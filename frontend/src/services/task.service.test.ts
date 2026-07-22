import { describe, expect, it } from 'vitest'
import { mockTaskService } from './task.service'

describe('mockTaskService', () => {
  it('returns the current task with an awaiting-approval changeset', async () => {
    const task = await mockTaskService.getCurrentTask('session-login-validation')

    expect(task.state).toBe('awaiting_approval')
    expect(task.changeSet.status).toBe('pending')
    expect(task.toolCalls).toHaveLength(4)
    expect(task.toolCalls[2]).toMatchObject({
      toolName: 'generate_diff',
      status: 'pending',
      fileSummary: { path: 'login.py', additions: 6, deletions: 2 },
    })
  })

  it('records an approval and exposes verification output', async () => {
    const approvedTask = await mockTaskService.approveChangeSet('task-login-validation')

    expect(approvedTask.changeSet.status).toBe('approved')
    expect(approvedTask.verification.status).toBe('passed')
  })

  it('returns task history entries for a workspace', async () => {
    const entries = await mockTaskService.getTaskHistory('workspace-login-service')

    expect(entries.length).toBe(8)
    expect(entries[0].status).toBe('waiting')
    expect(entries.filter(e => e.status === 'done')).toHaveLength(4)
    expect(entries.filter(e => e.status === 'fail')).toHaveLength(2)
    expect(entries.filter(e => e.status === 'cancelled')).toHaveLength(1)
  })

  it('returns full task detail for a given task id', async () => {
    const detail = await mockTaskService.getTaskDetail('history-task-3')

    expect(detail.status).toBe('fail')
    expect(detail.title).toContain('rate limiting')
    expect(detail.failReason).toBeDefined()
    expect(detail.plan.length).toBeGreaterThanOrEqual(4)
    expect(detail.toolCalls.length).toBeGreaterThanOrEqual(5)
  })

  it('returns waiting-task detail with review redirect info', async () => {
    const detail = await mockTaskService.getTaskDetail('history-task-1')

    expect(detail.status).toBe('waiting')
    expect(detail.approval.status).toBe('none')
    expect(detail.plan.some(s => s.state === 'waiting')).toBe(true)
  })
})
