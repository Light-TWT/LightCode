import { requestJson } from '@/services/http'
import { parseChatSession, parseChatSessionDetail, parseChatSubmitResponse } from '@/contracts/real-task.schema'
import type { ChatMessage, ChatSession, ChatSubmitResponse } from '@/types/agent'

export interface ChatService {
  /** GET /workspaces/{id}/chat-sessions */
  listChatSessions(workspaceId: string): Promise<ChatSession[]>
  /** POST /workspaces/{id}/chat-sessions —— 请求体只含 workspaceId + title */
  createChatSession(workspaceId: string, title: string): Promise<ChatSession>
  /** GET /chat-sessions/{id}?workspaceId=xxx（工作区归属校验） */
  getChatSession(sessionId: string, workspaceId?: string): Promise<{ session: ChatSession; messages: ChatMessage[] }>
  /** POST /chat-sessions/{id}/messages —— 请求体只含 content，绝不提交路径/补丁/命令 */
  submitMessage(sessionId: string, content: string): Promise<ChatSubmitResponse>
}

export const chatService: ChatService = {
  async listChatSessions(workspaceId) {
    const raw = await requestJson<unknown[]>(`/workspaces/${workspaceId}/chat-sessions`)
    return raw.map((s) => parseChatSession(s))
  },

  async createChatSession(workspaceId, title) {
    const raw = await requestJson<unknown>(`/workspaces/${workspaceId}/chat-sessions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ workspaceId, title }),
    })
    return parseChatSession(raw)
  },

  async getChatSession(sessionId, workspaceId) {
    const suffix = workspaceId ? `?workspaceId=${encodeURIComponent(workspaceId)}` : ''
    const raw = await requestJson<unknown>(`/chat-sessions/${sessionId}${suffix}`)
    return parseChatSessionDetail(raw)
  },

  async submitMessage(sessionId, content) {
    const raw = await requestJson<unknown>(`/chat-sessions/${sessionId}/messages`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content }),
    })
    return parseChatSubmitResponse(raw)
  },
}
