import { requestJson } from '@/services/http'
import { parseRealTask } from '@/contracts/real-task.schema'
import type { ApprovalInput, CreateRealTaskInput, RealTask } from '@/types/agent'

export interface RealTaskService {
  createRealTask(input: CreateRealTaskInput): Promise<RealTask>
  getRealTask(taskId: string): Promise<RealTask>
  /** 审批（approve/reject）。请求体字段与后端 ApprovalRequest 严格一致（extra=forbid）。 */
  submitApproval(taskId: string, approval: ApprovalInput): Promise<RealTask>
}

export const realTaskService: RealTaskService = {
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
