import { defineStore } from 'pinia'
import { taskService } from '@/services/task.service'
import { workspaceService } from '@/services/workspace.service'
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
    async load(workspaceId: string) {
      this.loading = true
      try {
        const [workspace, sessions, task] = await Promise.all([
          workspaceService.getWorkspace(workspaceId),
          workspaceService.getSessions(workspaceId),
          taskService.getCurrentTask(this.activeSessionId),
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
      this.task = await taskService.approveChangeSet(this.task.id)
    },
  },
})
