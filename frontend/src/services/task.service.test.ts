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
})
