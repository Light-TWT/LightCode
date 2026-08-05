import { requestJsonValidated } from '@/services/http'
import { parseModelTask } from '@/contracts/real-task.schema'
import type { CreateModelTaskInput, ModelTaskResponse } from '@/types/agent'

export interface ModelTaskService {
  /** 仅提交 workspaceId + title；模型只"提议"，由服务端生成不可变变更集。 */
  createModelTask(input: CreateModelTaskInput): Promise<ModelTaskResponse>
}

export const modelTaskService: ModelTaskService = {
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
