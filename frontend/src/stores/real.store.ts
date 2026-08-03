import { defineStore } from 'pinia'
import { isApiMode } from '@/config/runtime'
import { subscribeRealTaskEvents } from '@/services/event.service'
import { realTaskService } from '@/services/real-task.service'
import { modelTaskService } from '@/services/model-task.service'
import { registeredWorkspaceService } from '@/services/registered-workspace.service'
import { parseModelLifecycleEvent } from '@/contracts/real-task.schema'
import type {
  ApprovalDecision,
  EventConnection,
  ModelLifecycleStage,
  ModelLifecycleStep,
  ModelTaskResponse,
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
    // 注册工作区浏览（令牌导航，前端不持有自由路径）
    workspaces: [] as RegisteredWorkspace[],
    currentWorkspaceId: null as string | null,
    /** 面包屑栈：根目录为空；每项含展示名与回传用的浏览令牌 */
    pathStack: [] as { name: string; token: string }[],
    entries: [] as RegisteredFileEntry[],
    filePreview: null as RegisteredFileContent | null,
    searchQuery: '',
    searchHits: [] as WorkspaceSearchHit[],
    // 真实任务闭环
    task: null as RealTask | null,
    events: [] as TaskEvent[],
    lastSequence: 0,
    /** SSE 连接状态机（WP7）：断点续传与降级可观测性 */
    eventConnection: 'idle' as EventConnection,
    // 通用
    loading: false,
    submitting: false,
    error: null as string | null,
    _unsubscribeEvents: null as (() => void) | null,
    /** 缺口全量同步进行中的防重入标志 */
    _resyncing: false,
  }),

  getters: {
    /** 从 SSE 事件派生模型任务的稳定生命周期时间线（WP7 前端状态机）。
     *  仅当任务为模型任务时返回非空；其他类型任务返回空数组。 */
    modelLifecycle(state): ModelLifecycleStep[] {
      if (state.task?.kind !== 'model') return []
      const order: { stage: ModelLifecycleStage; eventType: string; label: string }[] = [
        { stage: 'planning', eventType: 'task.planning', label: '规划变更' },
        { stage: 'reading', eventType: 'task.reading_workspace', label: '读取目标文件' },
        { stage: 'generating', eventType: 'task.generating_diff', label: '生成候选变更集' },
        { stage: 'awaiting', eventType: 'task.awaiting_approval', label: '等待审批' },
      ]
      const seen = new Set<string>()
      let failed = false
      for (const ev of state.events) {
        if (ev.eventType === 'task.failed') failed = true
        seen.add(ev.eventType)
      }
      // 已到达的最远阶段索引（事件存在的最后一个有序阶段）
      let reachedIdx = -1
      order.forEach((o, i) => {
        if (seen.has(o.eventType)) reachedIdx = i
      })
      const steps: ModelLifecycleStep[] = order.map((o, i) => {
        let status: ModelLifecycleStep['status']
        if (failed) {
          // 失败：已到达阶段标记为完成，其后第一步标记为 failed（无法进行）
          status = i <= reachedIdx ? 'completed' : i === reachedIdx + 1 ? 'failed' : 'upcoming'
        } else if (i < reachedIdx) {
          status = 'completed'
        } else if (i === reachedIdx) {
          // 最远到达阶段即当前停留点（如 awaiting_approval 等待用户审批）
          status = 'current'
        } else {
          status = 'upcoming'
        }
        return { stage: o.stage, label: o.label, status }
      })
      return steps
    },
  },
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
      this.pathStack = []
      this.filePreview = null
      this.searchQuery = ''
      this.searchHits = []
      if (this.workspaces.length === 0) {
        await this.loadWorkspaces()
      }
      await this.loadDirectory(undefined)
    },

    /** 列出目录。`nodeToken` 为上层目录签发的令牌；根目录传 undefined */
    async loadDirectory(nodeToken?: string) {
      if (!this.currentWorkspaceId) return
      this.loading = true
      this.error = null
      try {
        this.entries = await registeredWorkspaceService.listFiles(
          this.currentWorkspaceId,
          nodeToken,
        )
        this.filePreview = null
      } catch (err) {
        this.error = err instanceof Error ? err.message : String(err)
      } finally {
        this.loading = false
      }
    },

    /** 进入子目录：压入面包屑并以下一层令牌继续列举 */
    async enterDirectory(entry: RegisteredFileEntry) {
      if (entry.kind !== 'dir' || !entry.token) return
      this.pathStack = [...this.pathStack, { name: entry.name, token: entry.token }]
      this.searchHits = []
      this.searchQuery = ''
      await this.loadDirectory(entry.token)
    },

    /** 返回上一级：弹出面包屑栈顶，用父级令牌重新列举 */
    async goUp() {
      if (this.pathStack.length === 0) return
      const stack = this.pathStack.slice(0, -1)
      this.pathStack = stack
      const parent = stack[stack.length - 1]
      await this.loadDirectory(parent ? parent.token : undefined)
    },

    /** 仅回传服务端签发的 fileToken 打开文件，绝不提交自由路径 */
    async openFileByToken(token: string) {
      if (!this.currentWorkspaceId || !token) return
      this.error = null
      try {
        this.filePreview = await registeredWorkspaceService.readFile(
          this.currentWorkspaceId,
          token,
        )
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

    /** 创建模型任务（WP6）：仅提交 workspaceId + title。服务端跑编排并生成候选
     *  变更集；成功返回 ModelTaskResponse 供上层导航，failed/异常则设置 error 并返回 null。 */
    async createModelTask(workspaceId: string, title: string): Promise<ModelTaskResponse | null> {
      this.submitting = true
      this.error = null
      try {
        const resp = await modelTaskService.createModelTask({ workspaceId, title })
        if (resp.state !== 'awaiting_approval') {
          this.error = resp.detail || '模型任务创建失败'
          return null
        }
        return resp
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

    /** 缺口全量同步：清空本地事件游标后重新拉取任务并重订阅，
     *  用于 SSE sequence 不连续（断线后丢帧）的恢复路径。 */
    async _resync(taskId: string) {
      this.events = []
      this.lastSequence = 0
      await this.loadTask(taskId)
    },

    _resubscribe(taskId: string) {
      this.cleanup()
      if (!isApiMode) {
        this.eventConnection = 'idle'
        return
      }
      this.eventConnection = 'connecting'
      this._unsubscribeEvents = subscribeRealTaskEvents(
        taskId,
        (event) => {
          if (this._resyncing) return
          // sequence 缺口检测：本地已有事件但收到不连续帧 → 全量重同步，
          // 避免状态机漂移（WP7 要求缺口全量同步）。
          if (this.lastSequence > 0 && event.sequence > this.lastSequence + 1) {
            this._resyncing = true
            this._resync(taskId).finally(() => {
              this._resyncing = false
            })
            return
          }
          if (event.sequence <= this.lastSequence) return // 去重
          // 模型事件 payload 防御性校验：畸形事件丢弃而非污染状态机
          try {
            parseModelLifecycleEvent(event.eventType, event.payload)
          } catch {
            return
          }
          this.eventConnection = 'open'
          this.lastSequence = event.sequence
          this.events = [...this.events, event]
        },
        // EventSource 在连接错误后会自动重连；标记为 reconnecting 而非 closed
        () => {
          this.eventConnection = 'reconnecting'
        },
        { afterSequence: this.lastSequence },
      )
    },

    resetTask() {
      this.cleanup()
      this.task = null
      this.events = []
      this.lastSequence = 0
      this.eventConnection = 'idle'
      this._resyncing = false
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
