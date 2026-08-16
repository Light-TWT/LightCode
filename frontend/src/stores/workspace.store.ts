import { defineStore } from 'pinia'
import { chatService } from '@/services/chat.service'
import { subscribeChatEvents, subscribeRealTaskEvents } from '@/services/event.service'
import { realTaskService } from '@/services/real-task.service'
import { registeredWorkspaceService } from '@/services/registered-workspace.service'
import { parseModelLifecycleEvent } from '@/contracts/real-task.schema'
import type {
  ApprovalDecision,
  ChatMessage,
  ChatSession,
  EventConnection,
  ModelLifecycleStage,
  ModelLifecycleStep,
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

export const useWorkspaceStore = defineStore('workspace', {
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
    // 任务闭环（真实/模型任务复用 Phase 1 审批）
    task: null as RealTask | null,
    events: [] as TaskEvent[],
    lastSequence: 0,
    /** 任务 SSE 连接状态机：断点续传与降级可观测性 */
    eventConnection: 'idle' as EventConnection,
    // 聊天会话（核心 Agent 更新阶段 A）
    chatSessions: [] as ChatSession[],
    currentSessionId: null as string | null,
    messages: [] as ChatMessage[],
    lastChatSequence: 0,
    sending: false,
    /** 聊天 SSE 连接状态机（tail 续传 + 断线重连） */
    chatConnection: 'idle' as EventConnection,
    // 通用
    loading: false,
    submitting: false,
    error: null as string | null,
    _unsubscribeEvents: null as (() => void) | null,
    _unsubscribeChatEvents: null as (() => void) | null,
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
      // 切换工作区时清空旧工作区上下文：任务、聊天会话、消息与连接
      this.resetTask()
      this._cleanupChatEvents()
      this.chatSessions = []
      this.currentSessionId = null
      this.messages = []
      this.lastChatSequence = 0
      this.chatConnection = 'idle'
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
      this._cleanupTaskEvents()
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
        {
          afterSequence: this.lastSequence,
          // 真实任务必须持续订阅（tail=true）：后端回放完既有事件后继续轮询，
          // 否则连接会立即以 stream.end 结束，实时状态停留在旧快照。
          tail: true,
          // 服务端正常结束（含 tail 超时）→ 连接关闭；仅当订阅仍属于当前任务时
          // 更新状态，避免被新订阅/cleanup 覆盖。
          onEnd: () => {
            if (this.task?.id === taskId) {
              this.eventConnection = 'closed'
            }
          },
        },
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

    // --- 核心 Agent 更新（阶段 A）：聊天会话与消息 ---

    async loadChatSessions(workspaceId: string) {
      this.error = null
      try {
        this.chatSessions = await chatService.listChatSessions(workspaceId)
      } catch (err) {
        this.error = err instanceof Error ? err.message : String(err)
      }
    },

    /** 新建会话：服务端持久化后置为当前会话并订阅 chat.event */
    async createChatSession(workspaceId: string, title: string): Promise<ChatSession | null> {
      this.submitting = true
      this.error = null
      try {
        const session = await chatService.createChatSession(workspaceId, title)
        this.chatSessions = [session, ...this.chatSessions.filter((s) => s.id !== session.id)]
        this.currentSessionId = session.id
        this.messages = []
        this.lastChatSequence = 0
        this._subscribeChatEvents(session.id)
        return session
      } catch (err) {
        this.error = err instanceof Error ? err.message : String(err)
        return null
      } finally {
        this.submitting = false
      }
    },

    /** 重命名会话：成功后同步列表中的会话标题 */
    async renameChatSession(
      sessionId: string,
      title: string,
      workspaceId: string,
    ): Promise<boolean> {
      this.error = null
      try {
        const updated = await chatService.renameChatSession(sessionId, workspaceId, title)
        this.chatSessions = this.chatSessions.map((s) =>
          s.id === updated.id ? updated : s,
        )
        return true
      } catch (err) {
        this.error = err instanceof Error ? err.message : String(err)
        return false
      }
    },

    /** 永久删除会话。若删除的是当前会话：关闭旧流，有剩余会话则打开
     *  列表第一项，否则清空状态；删除非当前会话只移除对应行。 */
    async deleteChatSession(sessionId: string, workspaceId: string): Promise<boolean> {
      this.error = null
      try {
        await chatService.deleteChatSession(sessionId, workspaceId)
      } catch (err) {
        this.error = err instanceof Error ? err.message : String(err)
        return false
      }
      const wasCurrent = this.currentSessionId === sessionId
      this.chatSessions = this.chatSessions.filter((s) => s.id !== sessionId)
      if (wasCurrent) {
        // 清理已删除会话的任务/审批状态与会话订阅（含在途发送标志）
        this.resetTask()
        this.sending = false
        this.currentSessionId = null
        this.messages = []
        this.lastChatSequence = 0
        this.chatConnection = 'idle'
        const next = this.chatSessions[0]
        if (next) {
          await this.openChatSession(next.id, workspaceId)
        }
      }
      return true
    },

    /** 打开既有会话：拉取历史消息并按最新 sequence 续传订阅 chat.event */
    async openChatSession(sessionId: string, workspaceId?: string) {
      this.currentSessionId = sessionId
      this.sending = false
      this.error = null
      try {
        const detail = await chatService.getChatSession(sessionId, workspaceId)
        this.messages = detail.messages
        this.lastChatSequence = detail.messages.length
          ? detail.messages[detail.messages.length - 1].sequence
          : 0
        this._subscribeChatEvents(sessionId)
        // 加载最近一条 edit_summary 关联的任务，使聊天内审批卡片与底部审查栏可用
        const pending = [...detail.messages]
          .reverse()
          .find((msg) => msg.kind === 'edit_summary' && msg.taskId)
        if (pending) {
          await this.loadTask(pending.taskId)
        }
      } catch (err) {
        this.error = err instanceof Error ? err.message : String(err)
      }
    },

    /** 提交用户消息：持久化回复直接追加；taskId 非空时加载关联任务以便审查 */
    async submitChatMessage(content: string) {
      if (!this.currentSessionId || this.sending) return
      this.sending = true
      this.error = null
      try {
        const resp = await chatService.submitMessage(this.currentSessionId, content)
        this._appendChatMessage(resp.message)
        if (resp.taskId) {
          await this.loadTask(resp.taskId)
        }
      } catch (err) {
        this.error = err instanceof Error ? err.message : String(err)
      } finally {
        this.sending = false
      }
    },

    /** 追加聊天消息（按 sequence 去重；POST 返回与 SSE 帧双路径安全） */
    _appendChatMessage(message: ChatMessage) {
      if (message.sequence <= this.lastChatSequence) return
      this.lastChatSequence = message.sequence
      this.messages = [...this.messages, message]
    },

    /** 首页发起：选定工作区后直接建会话并发送首条消息，返回会话 id 供导航。
     *  成功后才由视图跳转 `/workspace/:workspaceId/session/:sessionId`。 */
    async homeCreateAndSend(workspaceId: string, content: string): Promise<string | null> {
      if (!this.currentWorkspaceId || this.sending) return null
      this.resetTask()
      this._cleanupChatEvents()
      this.chatSessions = []
      this.currentSessionId = null
      this.messages = []
      this.lastChatSequence = 0
      this.chatConnection = 'idle'
      const title = content.trim().replace(/\s+/g, ' ').slice(0, 20) || '新会话'
      const session = await this.createChatSession(workspaceId, title)
      if (!session) return null
      // The session already exists; submit the first message (failures only set
      // this.error) and navigate so the user can continue in the full workspace.
      await this.submitChatMessage(content)
      return session.id
    },

    /** 订阅当前会话的 chat.event（tail 续传；EventSource 断线自动带 Last-Event-ID 重连） */
    _subscribeChatEvents(sessionId: string) {
      this._cleanupChatEvents()
      this._openChatEventStream(sessionId)
    },

    /** 打开/重开聊天事件流。服务端 tail 窗口（30s）结束后 stream.end，这里自动
     *  重开一条流并从 lastChatSequence 续传，保证后续消息（含用户气泡）持续到达。 */
    _openChatEventStream(sessionId: string) {
      if (this.currentSessionId !== sessionId) return
      this.chatConnection = 'connecting'
      this._unsubscribeChatEvents = subscribeChatEvents(
        sessionId,
        (message) => {
          if (this.currentSessionId !== sessionId) return // 已切换会话，丢弃旧流
          this._appendChatMessage(message)
          this.chatConnection = 'open'
        },
        () => {
          if (this.currentSessionId === sessionId) this.chatConnection = 'reconnecting'
        },
        {
          afterSequence: this.lastChatSequence,
          tail: true,
          onEnd: () => {
            if (this.currentSessionId !== sessionId) return
            this.chatConnection = 'closed'
            this._openChatEventStream(sessionId)
          },
        },
      )
    },

    _cleanupChatEvents() {
      if (this._unsubscribeChatEvents) {
        this._unsubscribeChatEvents()
        this._unsubscribeChatEvents = null
      }
    },

    _cleanupTaskEvents() {
      if (this._unsubscribeEvents) {
        this._unsubscribeEvents()
        this._unsubscribeEvents = null
      }
    },

    cleanup() {
      this._cleanupChatEvents()
      this._cleanupTaskEvents()
    },
  },
})
