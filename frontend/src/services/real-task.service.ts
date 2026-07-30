import { realTaskFixture } from '@/fixtures/phase1.fixture'
import { isApiMode } from '@/config/runtime'
import { requestJson } from '@/services/http'
import { parseRealTask } from '@/contracts/real-task.schema'
import type { ApprovalInput, CreateRealTaskInput, RealTask } from '@/types/agent'

export interface RealTaskService {
  createRealTask(input: CreateRealTaskInput): Promise<RealTask>
  getRealTask(taskId: string): Promise<RealTask>
  /** 审批（approve/reject）。请求体字段与后端 ApprovalRequest 严格一致（extra=forbid）。 */
  submitApproval(taskId: string, approval: ApprovalInput): Promise<RealTask>
}

function cloneRealTask(): RealTask {
  return structuredClone(realTaskFixture)
}

export const mockRealTaskService: RealTaskService = {
  async createRealTask(input) {
    const task = cloneRealTask()
    task.workspaceId = input.workspaceId
    task.title = input.title
    return task
  },
  async getRealTask(taskId) {
    if (taskId !== realTaskFixture.id) {
      throw new Error(`Unknown mock real task ${taskId}`)
    }
    return cloneRealTask()
  },
  async submitApproval(taskId, approval) {
    if (taskId !== realTaskFixture.id) {
      throw new Error(`Unknown mock real task ${taskId}`)
    }
    const task = cloneRealTask()
    if (approval.decision === 'approve') {
      task.state = 'completed'
      if (task.changeSet) task.changeSet.status = 'applied'
      task.verification = {
        status: 'passed',
        command: '内建完整性验证',
        lines: ['written file hash matches proposedSha256'],
      }
    } else {
      task.state = 'cancelled'
      if (task.changeSet) task.changeSet.status = 'rejected'
    }
    return task
  },
}

export const httpRealTaskService: RealTaskService = {
  async createRealTask(input) {
    const raw = await requestJson<unknown>('/real-tasks', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        workspaceId: input.workspaceId,
        title: input.title,
        templateId: input.templateId ?? 'append-marker',
      }),
    })
    return parseRealTask(raw) as RealTask
  },
  async getRealTask(taskId) {
    const raw = await requestJson<unknown>(`/real-tasks/${taskId}`)
    return parseRealTask(raw) as RealTask
  },
  async submitApproval(taskId, approval) {
    const raw = await requestJson<unknown>(`/real-tasks/${taskId}/approval`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(approval),
    })
    return parseRealTask(raw) as RealTask
  },
}

export const realTaskService = isApiMode ? httpRealTaskService : mockRealTaskService
