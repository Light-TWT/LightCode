import { defineStore } from 'pinia'
import { subscribeTaskEvents } from '@/services/event.service'
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
    _unsubscribeEvents: null as (() => void) | null,
  }),
  actions: {
    async load(workspaceId: string) {
      this.loading = true
      this._cleanupEvents()
      try {
        const [workspace, sessions, task] = await Promise.all([
          workspaceService.getWorkspace(workspaceId),
          workspaceService.getSessions(workspaceId),
          taskService.getCurrentTask(this.activeSessionId),
        ])
        this.workspace = workspace
        this.sessions = sessions
        this.task = task
        this._subscribeTaskEvents(task.id)
      } finally {
        this.loading = false
      }
    },
    async approveCurrentChangeSet() {
      if (!this.task) return
      this.task = await taskService.approveChangeSet(this.task.id)
    },
    /**
     * 拒绝当前变更集。Phase 0.5 legacy Mock 流程没有拒绝端点，
     * 这里仅在前端标记为 rejected（演示用途，刷新后恢复）。
     * Phase 1 真实任务的拒绝走 real.store 的 submitDecision('reject')。
     */
    rejectCurrentChangeSet() {
      if (!this.task) return
      this.task = { ...this.task, changeSet: { ...this.task.changeSet, status: 'rejected' } }
    },
    _subscribeTaskEvents(taskId: string) {
      const isApiMode = import.meta.env.VITE_LIGHTCODE_RUNTIME === 'api'
      if (!isApiMode) return
      this._unsubscribeEvents = subscribeTaskEvents(
        taskId,
        (event) => {
          if (this.task === null) return
          if (event.eventType === 'changeset.approved') {
            this.task = { ...this.task, changeSet: { ...this.task.changeSet, status: 'approved' } }
          } else if (event.eventType === 'verification.started') {
            const cmd = (event.payload as Record<string, unknown>).command as string
            this.task = { ...this.task, verification: { ...this.task.verification, status: 'running', command: cmd } }
          } else if (event.eventType === 'verification.completed') {
            const result = (event.payload as Record<string, unknown>).result as string
            const detail = (event.payload as Record<string, unknown>).detail as string
            this.task = {
              ...this.task,
              state: 'completed',
              verification: {
                ...this.task.verification,
                status: result === 'passed' ? 'passed' : 'failed',
                lines: [detail],
              },
            }
          }
        },
        () => {},
      )
    },
    _cleanupEvents() {
      if (this._unsubscribeEvents) {
        this._unsubscribeEvents()
        this._unsubscribeEvents = null
      }
    },
  },
})
