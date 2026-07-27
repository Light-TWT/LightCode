import { defineStore } from 'pinia'
import { isApiMode } from '@/config/runtime'
import { subscribeRealTaskEvents } from '@/services/event.service'
import { realTaskService } from '@/services/real-task.service'
import { registeredWorkspaceService } from '@/services/registered-workspace.service'
import type {
  ApprovalDecision,
  RealTask,
  RegisteredFileContent,
  RegisteredFileEntry,
  RegisteredWorkspace,
  TaskEvent,
  WorkspaceSearchHit,
} from '@/types/agent'

function newIdempotencyKey(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID()
  }
  return `idem-${Date.now()}-${Math.random().toString(16).slice(2)}`
}

export const useRealStore = defineStore('real', {
  state: () => ({
    // 注册工作区浏览
    workspaces: [] as RegisteredWorkspace[],
    currentWorkspaceId: null as string | null,
    currentPath: '',
    entries: [] as RegisteredFileEntry[],
    filePreview: null as RegisteredFileContent | null,
    searchQuery: '',
    searchHits: [] as WorkspaceSearchHit[],
    // 真实任务闭环
    task: null as RealTask | null,
    events: [] as TaskEvent[],
    lastSequence: 0,
    // 通用
    loading: false,
    submitting: false,
    error: null as string | null,
    _unsubscribeEvents: null as (() => void) | null,
  }),
  actions: {
    async loadWorkspaces() {
      this.loading = true
      this.error = null
      try {
        this.workspaces = await registeredWorkspaceService.listRegisteredWorkspaces()
      } catch (err) {
        this.error = err instanceof Error ? err.message : String(err)
      } finally {
        this.loading = false
      }
    },

    async openWorkspace(workspaceId: string) {
      this.currentWorkspaceId = workspaceId
      this.currentPath = ''
      this.filePreview = null
      this.searchQuery = ''
      this.searchHits = []
      if (this.workspaces.length === 0) {
        await this.loadWorkspaces()
      }
      await this.loadDirectory('')
    },

    async loadDirectory(path: string) {
      if (!this.currentWorkspaceId) return
      this.loading = true
      this.error = null
      try {
        this.entries = await registeredWorkspaceService.listFiles(this.currentWorkspaceId, path)
        this.currentPath = path
      } catch (err) {
        this.error = err instanceof Error ? err.message : String(err)
      } finally {
        this.loading = false
      }
    },

    /** 后端 relativePath 相对当前列举目录，这里拼出工作区内完整相对路径 */
    childPath(entry: RegisteredFileEntry): string {
      return this.currentPath ? `${this.currentPath}/${entry.name}` : entry.name
    },

    async openFile(path: string) {
      if (!this.currentWorkspaceId) return
      this.error = null
      try {
        this.filePreview = await registeredWorkspaceService.readFile(this.currentWorkspaceId, path)
      } catch (err) {
        this.error = err instanceof Error ? err.message : String(err)
      }
    },

    async runSearch(query: string) {
      if (!this.currentWorkspaceId) return
      this.searchQuery = query
      this.error = null
      if (!query) {
        this.searchHits = []
        return
      }
      try {
        this.searchHits = await registeredWorkspaceService.search(this.currentWorkspaceId, query)
      } catch (err) {
        this.error = err instanceof Error ? err.message : String(err)
      }
    },

    async createTask(workspaceId: string, title: string, templateId = 'append-marker') {
      this.submitting = true
      this.error = null
      try {
        const task = await realTaskService.createRealTask({ workspaceId, title, templateId })
        this._setTask(task)
        return task
      } catch (err) {
        this.error = err instanceof Error ? err.message : String(err)
        return null
      } finally {
        this.submitting = false
      }
    },

    async loadTask(taskId: string) {
      this.loading = true
      this.error = null
      try {
        const task = await realTaskService.getRealTask(taskId)
        this._setTask(task)
      } catch (err) {
        this.error = err instanceof Error ? err.message : String(err)
      } finally {
        this.loading = false
      }
    },

    /** 审批闭环：从当前变更集构造版本绑定的审批请求（approve/reject 共用） */
    async submitDecision(decision: ApprovalDecision) {
      if (!this.task?.changeSet) {
        this.error = '当前任务没有可审批的变更集'
        return
      }
      this.submitting = true
      this.error = null
      try {
        const cs = this.task.changeSet
        const updated = await realTaskService.submitApproval(this.task.id, {
          decision,
          changeSetId: cs.changeSetId,
          revision: cs.revision,
          diffHash: cs.diffHash,
          idempotencyKey: newIdempotencyKey(),
        })
        // 审批后重新订阅，续传补齐审批期间落库的事件
        this._setTask(updated)
      } catch (err) {
        this.error = err instanceof Error ? err.message : String(err)
      } finally {
        this.submitting = false
      }
    },

    _setTask(task: RealTask) {
      // 切换到不同任务时重置事件游标，避免用旧 sequence 过滤新任务事件
      if (this.task?.id !== task.id) {
        this.events = []
        this.lastSequence = 0
      }
      this.task = task
      this._resubscribe(task.id)
    },

    _resubscribe(taskId: string) {
      this.cleanup()
      if (!isApiMode) return
      this._unsubscribeEvents = subscribeRealTaskEvents(
        taskId,
        (event) => {
          if (event.sequence <= this.lastSequence) return
          this.lastSequence = event.sequence
          this.events = [...this.events, event]
        },
        () => {},
        { afterSequence: this.lastSequence },
      )
    },

    resetTask() {
      this.cleanup()
      this.task = null
      this.events = []
      this.lastSequence = 0
      this.error = null
    },

    cleanup() {
      if (this._unsubscribeEvents) {
        this._unsubscribeEvents()
        this._unsubscribeEvents = null
      }
    },
  },
})
