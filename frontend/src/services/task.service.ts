import { taskFixture } from '@/fixtures/agent.fixture'
import type { Task } from '@/types/agent'

function cloneTask(): Task {
  return structuredClone(taskFixture)
}

export interface TaskService {
  getCurrentTask(sessionId: string): Promise<Task>
  approveChangeSet(taskId: string): Promise<Task>
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
}
