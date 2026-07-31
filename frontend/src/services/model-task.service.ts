import { isApiMode } from '@/config/runtime'
import { requestJsonValidated } from '@/services/http'
import { parseModelTask } from '@/contracts/real-task.schema'
import type { CreateModelTaskInput, ModelTaskResponse } from '@/types/agent'

export interface ModelTaskService {
  /** 仅提交 workspaceId + title；模型只"提议"，由服务端生成不可变变更集。 */
  createModelTask(input: CreateModelTaskInput): Promise<ModelTaskResponse>
}

// 模块级自增序号，保证 Mock 模式每次创建得到稳定且唯一的任务 id。
let _seq = 0

export const mockModelTaskService: ModelTaskService = {
  async createModelTask(input) {
    _seq += 1
    return {
      id: `model-task-mock${_seq}`,
      workspaceId: input.workspaceId,
      state: 'awaiting_approval',
      changeSetId: `cs-mock${_seq}`,
      detail: '模型已生成候选变更集，等待审批。',
    }
  },
}

export const httpModelTaskService: ModelTaskService = {
  async createModelTask(input) {
    return requestJsonValidated<ModelTaskResponse>(
      '/model-tasks',
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          workspaceId: input.workspaceId,
          title: input.title,
        }),
      },
      parseModelTask,
    )
  },
}

export const modelTaskService = isApiMode ? httpModelTaskService : mockModelTaskService
