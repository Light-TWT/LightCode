import { defineStore } from 'pinia'
import { mockTaskService } from '@/services/task.service'
import { mockWorkspaceService } from '@/services/workspace.service'
import type { Session, Task, Workspace } from '@/types/agent'

export const useAgentStore = defineStore('agent', {
  state: () => ({
    workspace: null as Workspace | null,
    sessions: [] as Session[],
    task: null as Task | null,
    activeSessionId: 'session-login-validation',
    loading: false,
  }),
  actions: {
    async load() {
      this.loading = true
      try {
        const [workspace, sessions, task] = await Promise.all([
          mockWorkspaceService.getWorkspace(),
          mockWorkspaceService.getSessions(),
          mockTaskService.getCurrentTask(this.activeSessionId),
        ])
        this.workspace = workspace
        this.sessions = sessions
        this.task = task
      } finally {
        this.loading = false
      }
    },
    async approveCurrentChangeSet() {
      if (!this.task) return
      this.task = await mockTaskService.approveChangeSet(this.task.id)
    },
  },
})
