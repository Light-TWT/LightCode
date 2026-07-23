import { taskDetailFixtures, taskFixture, taskHistoryEntriesFixture } from '@/fixtures/agent.fixture'
import { requestJson } from '@/services/http'
import type { HistoryTaskDetail, HistoryTaskEntry, Task } from '@/types/agent'

function cloneTask(): Task {
  return structuredClone(taskFixture)
}

export interface TaskService {
  getCurrentTask(sessionId: string): Promise<Task>
  approveChangeSet(taskId: string): Promise<Task>
  getTaskHistory(workspaceId: string): Promise<HistoryTaskEntry[]>
  getTaskDetail(taskId: string): Promise<HistoryTaskDetail>
}

export const mockTaskService: TaskService = {
  async getCurrentTask(sessionId) {
    if (sessionId !== taskFixture.sessionId) {
      throw new Error(`No mock task for session ${sessionId}`)
    }

    return cloneTask()
  },

  async approveChangeSet(taskId) {
    if (taskId !== taskFixture.id) {
      throw new Error(`Unknown mock task ${taskId}`)
    }

    const task = cloneTask()
    task.changeSet.status = 'approved'
    task.state = 'completed'
    task.verification = {
      status: 'passed',
      command: '$ pytest test_login.py -v',
      lines: ['============================= test session starts =============================', 'test_login.py::test_login_valid_user PASSED', '============================== 3 passed in 0.12s ============================='],
    }
    return task
  },

  async getTaskHistory(workspaceId) {
    if (workspaceId !== 'workspace-login-service') {
      throw new Error(`No mock history for workspace ${workspaceId}`)
    }

    return structuredClone(taskHistoryEntriesFixture)
  },

  async getTaskDetail(taskId) {
    const detail = taskDetailFixtures[taskId]
    if (!detail) {
      throw new Error(`Unknown task detail ${taskId}`)
    }

    return structuredClone(detail)
  },
}

export const httpTaskService: TaskService = {
  async getCurrentTask(sessionId) {
    return requestJson<Task>(`/sessions/${sessionId}/tasks/current`)
  },
  async approveChangeSet(taskId) {
    return requestJson<Task>(`/tasks/${taskId}/changeset/approve`, { method: 'POST' })
  },
  async getTaskHistory(workspaceId) {
    return requestJson<HistoryTaskEntry[]>(`/workspaces/${workspaceId}/tasks/history`)
  },
  async getTaskDetail(taskId) {
    return requestJson<HistoryTaskDetail>(`/tasks/${taskId}`)
  },
}

export const taskService = import.meta.env.VITE_LIGHTCODE_RUNTIME === 'api'
  ? httpTaskService
  : mockTaskService
