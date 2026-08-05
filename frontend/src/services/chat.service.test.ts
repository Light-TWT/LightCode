import { afterEach, describe, expect, it, vi } from 'vitest'
import { chatService } from './chat.service'
import { ContractValidationError } from '@/contracts/real-task.schema'

const sessionPayload = {
  id: 'chat-abc123',
  workspaceId: 'ws-1',
  title: '新会话',
  status: 'active',
  createdAt: '2026-08-04T00:00:00+00:00',
  updatedAt: '2026-08-04T00:00:00+00:00',
}

const messagePayload = {
  id: 'msg-1',
  sessionId: 'chat-abc123',
  sequence: 1,
  role: 'assistant',
  content: '你好',
  kind: 'message',
  taskId: '',
  createdAt: '2026-08-04T00:00:00+00:00',
}

function stubFetch(payload: unknown) {
  const fetchMock = vi.fn(async () => ({
    ok: true,
    json: async () => payload,
  }))
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

describe('chatService（HTTP-only）', () => {
  afterEach(() => {
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
  })

  it('GET /workspaces/{id}/chat-sessions', async () => {
    const fetchMock = stubFetch([sessionPayload])
    const sessions = await chatService.listChatSessions('ws-1')
    expect(String(fetchMock.mock.calls[0][0])).toContain('/workspaces/ws-1/chat-sessions')
    expect(sessions).toHaveLength(1)
    expect(sessions[0].id).toBe('chat-abc123')
  })

  it('POST /workspaces/{id}/chat-sessions 请求体只含 workspaceId + title', async () => {
    const fetchMock = stubFetch(sessionPayload)
    const session = await chatService.createChatSession('ws-1', '新会话')
    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit]
    expect(url).toContain('/workspaces/ws-1/chat-sessions')
    expect(init.method).toBe('POST')
    const body = JSON.parse(init.body as string)
    // 后端 ChatSessionCreateRequest 为 extra=forbid：不得携带 rootPath/path/命令等字段
    expect(Object.keys(body).sort()).toEqual(['title', 'workspaceId'])
    expect(session.id).toBe('chat-abc123')
  })

  it('GET /chat-sessions/{id}?workspaceId=xxx 带回话与消息', async () => {
    const fetchMock = stubFetch({ session: sessionPayload, messages: [messagePayload] })
    const detail = await chatService.getChatSession('chat-abc123', 'ws-1')
    expect(String(fetchMock.mock.calls[0][0])).toContain(
      '/chat-sessions/chat-abc123?workspaceId=ws-1',
    )
    expect(detail.session.id).toBe('chat-abc123')
    expect(detail.messages).toHaveLength(1)
    expect(detail.messages[0].role).toBe('assistant')
  })

  it('POST /chat-sessions/{id}/messages 请求体只含 content', async () => {
    const fetchMock = stubFetch({ message: messagePayload, taskId: '' })
    const resp = await chatService.submitMessage('chat-abc123', '你好')
    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit]
    expect(url).toContain('/chat-sessions/chat-abc123/messages')
    expect(init.method).toBe('POST')
    const body = JSON.parse(init.body as string)
    // 后端 ChatMessageSubmitRequest 为 extra=forbid：只接受 content
    expect(Object.keys(body).sort()).toEqual(['content'])
    expect(resp.message.sequence).toBe(1)
    expect(resp.taskId).toBe('')
  })

  it('edit_summary 响应携带 taskId（供审批闭环加载关联任务）', async () => {
    stubFetch({
      message: {
        ...messagePayload,
        kind: 'edit_summary',
        taskId: 'chat-task-1',
        content: '已根据你的要求生成候选变更集。',
      },
      taskId: 'chat-task-1',
    })
    const resp = await chatService.submitMessage('chat-abc123', '请修改 NOTES.md')
    expect(resp.taskId).toBe('chat-task-1')
    expect(resp.message.kind).toBe('edit_summary')
  })

  it('拒绝含 rootPath 的畸形响应（契约不兼容）', async () => {
    stubFetch({ session: sessionPayload, messages: [messagePayload], rootPath: '/etc' })
    await expect(chatService.getChatSession('chat-abc123', 'ws-1')).rejects.toBeInstanceOf(
      ContractValidationError,
    )
  })
})
