import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter, type Router } from 'vue-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import WorkspaceView from './WorkspaceView.vue'

const m = vi.hoisted(() => {
  const ws = {
    id: 'ws-1',
    displayName: 'Demo Workspace',
    enabled: true,
    capabilities: ['read', 'search'],
    policyVersion: 'policy-v1',
  }
  const session = {
    id: 'chat-1',
    workspaceId: 'ws-1',
    title: '新会话',
    status: 'active',
    createdAt: 't',
    updatedAt: 't',
  }
  const userMsg = {
    id: 'msg-1',
    sessionId: 'chat-1',
    sequence: 1,
    role: 'user',
    content: '请修改 NOTES.md',
    kind: 'message',
    taskId: '',
    createdAt: 't',
  }
  const assistantMsg = {
    id: 'msg-2',
    sessionId: 'chat-1',
    sequence: 2,
    role: 'assistant',
    content: '好的，我先看一下文件。',
    kind: 'message',
    taskId: '',
    createdAt: 't',
  }
  const editSummary = {
    id: 'msg-3',
    sessionId: 'chat-1',
    sequence: 3,
    role: 'assistant',
    content: '已根据你的要求生成候选变更集：文件 NOTES.md，新增 1 行、删除 0 行。',
    kind: 'edit_summary',
    taskId: 'chat-task-1',
    createdAt: 't',
  }
  const task = {
    id: 'chat-task-1',
    workspaceId: 'ws-1',
    sessionId: 'chat-1',
    kind: 'model',
    state: 'awaiting_approval',
    title: '在 NOTES.md 末尾追加标记',
    targetFile: 'NOTES.md',
    changeSet: {
      changeSetId: 'cs-1',
      revision: 1,
      diffHash: 'hash',
      baseSha256: 'b',
      proposedSha256: 'p',
      logicalRelativePath: 'NOTES.md',
      status: 'active',
      policyVersion: 'policy-v1',
      additions: 1,
      deletions: 0,
      before: ['a'],
      after: ['a', 'b'],
    },
    plan: [],
    toolCalls: [],
    verification: { status: 'pending', command: '内建完整性验证', lines: [] },
    createdAt: 't',
  }
  return {
    mocks: {
      listRegisteredWorkspaces: vi.fn(),
      listFiles: vi.fn(),
      readFile: vi.fn(),
      search: vi.fn(),
      listChatSessions: vi.fn(),
      createChatSession: vi.fn(),
      getChatSession: vi.fn(),
      submitMessage: vi.fn(),
      getRealTask: vi.fn(),
      submitApproval: vi.fn(),
      createRealTask: vi.fn(),
      getSettings: vi.fn(),
      getHealth: vi.fn(),
      subscribeChatEvents: vi.fn(),
      subscribeRealTaskEvents: vi.fn(),
    },
    ws,
    session,
    userMsg,
    assistantMsg,
    editSummary,
    task,
  }
})

vi.mock('@/services/registered-workspace.service', () => ({
  registeredWorkspaceService: {
    listRegisteredWorkspaces: m.mocks.listRegisteredWorkspaces,
    listFiles: m.mocks.listFiles,
    readFile: m.mocks.readFile,
    search: m.mocks.search,
  },
}))
vi.mock('@/services/chat.service', () => ({
  chatService: {
    listChatSessions: m.mocks.listChatSessions,
    createChatSession: m.mocks.createChatSession,
    getChatSession: m.mocks.getChatSession,
    submitMessage: m.mocks.submitMessage,
  },
}))
vi.mock('@/services/provider.service', () => ({
  providerService: {
    getSettings: m.mocks.getSettings,
    getHealth: m.mocks.getHealth,
    saveSettings: vi.fn(),
    testConnection: vi.fn(),
    clearSettings: vi.fn(),
  },
}))
vi.mock('@/services/real-task.service', () => ({
  realTaskService: {
    getRealTask: m.mocks.getRealTask,
    submitApproval: m.mocks.submitApproval,
    createRealTask: m.mocks.createRealTask,
  },
}))
vi.mock('@/services/event.service', () => ({
  subscribeChatEvents: m.mocks.subscribeChatEvents,
  subscribeRealTaskEvents: m.mocks.subscribeRealTaskEvents,
}))

const readySettings = {
  configured: true,
  status: 'ready',
  provider: 'openai-compatible',
  modelId: 'demo-model',
  detail: 'Provider 已就绪。',
  originAllowlisted: true,
  transport: 'https',
}

const unconfiguredSettings = {
  configured: false,
  status: 'unconfigured',
  provider: '',
  modelId: '',
  detail: '后端缺少配置。',
  originAllowlisted: false,
  transport: 'none',
}

function createTestRouter(): Router {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', name: 'home', component: { template: '<div>home</div>' } },
      { path: '/workspace/:workspaceId', name: 'workspace', component: WorkspaceView },
      {
        path: '/workspace/:workspaceId/session/:sessionId',
        name: 'workspace-session',
        component: WorkspaceView,
      },
      {
        path: '/workspace/:workspaceId/task/:taskId',
        name: 'real-task',
        component: { template: '<div>task review</div>' },
      },
      { path: '/settings', name: 'settings', component: { template: '<div>settings</div>' } },
    ],
  })
}

async function mountWorkspace() {
  const router = createTestRouter()
  await router.push('/workspace/ws-1/session/chat-1')
  await router.isReady()
  const wrapper = mount(WorkspaceView, { global: { plugins: [router] } })
  await flushPromises()
  return { wrapper, router }
}

describe('WorkspaceView（聊天主界面）', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    m.mocks.listRegisteredWorkspaces.mockResolvedValue([m.ws])
    m.mocks.listFiles.mockResolvedValue([])
    m.mocks.readFile.mockResolvedValue({ content: '' })
    m.mocks.search.mockResolvedValue([])
    m.mocks.listChatSessions.mockResolvedValue([m.session])
    m.mocks.createChatSession.mockResolvedValue(m.session)
    // 默认会话无 edit_summary（不触发任务加载，输入框常驻）
    m.mocks.getChatSession.mockResolvedValue({
      session: m.session,
      messages: [m.userMsg, m.assistantMsg],
    })
    m.mocks.submitMessage.mockResolvedValue({
      message: { ...m.assistantMsg, sequence: 4, id: 'msg-4', content: '已完成审查流程。' },
      taskId: '',
    })
    m.mocks.getSettings.mockResolvedValue(readySettings)
    m.mocks.getRealTask.mockResolvedValue(m.task)
    m.mocks.submitApproval.mockResolvedValue({
      ...m.task,
      state: 'completed',
      changeSet: { ...m.task.changeSet, status: 'applied' },
    })
    m.mocks.subscribeChatEvents.mockReturnValue(() => {})
    m.mocks.subscribeRealTaskEvents.mockReturnValue(() => {})
    vi.stubGlobal('EventSource', vi.fn(function () {
      return { close: vi.fn(), addEventListener: vi.fn() }
    }))
  })
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  function mockSessionWithEditSummary() {
    m.mocks.getChatSession.mockResolvedValue({
      session: m.session,
      messages: [m.userMsg, m.assistantMsg, m.editSummary],
    })
  }

  it('渲染用户（右）与助手（左）消息及会话列表', async () => {
    const { wrapper } = await mountWorkspace()
    expect(wrapper.findAll('[data-testid="chat-message"]').length).toBe(2)
    expect(wrapper.find('.user-bubble').text()).toBe('请修改 NOTES.md')
    expect(wrapper.find('.assistant-bubble').text()).toBe('好的，我先看一下文件。')
    expect(wrapper.findAll('[data-testid="session-row"]').length).toBe(1)
  })

  it('edit_summary 卡片显示审查操作，批准走 store.submitDecision', async () => {
    mockSessionWithEditSummary()
    const { wrapper } = await mountWorkspace()
    // openChatSession 自动加载最近 edit_summary 关联任务 → 卡片操作可用
    expect(m.mocks.getRealTask).toHaveBeenCalledWith('chat-task-1')
    const card = wrapper.get('[data-testid="edit-summary"]')
    expect(card.text()).toContain('候选变更集')
    expect(wrapper.get('[data-testid="view-diff-btn"]').exists()).toBe(true)

    await wrapper.get('[data-testid="card-approve-btn"]').trigger('click')
    await flushPromises()

    expect(m.mocks.submitApproval).toHaveBeenCalledTimes(1)
    const [taskId, approval] = m.mocks.submitApproval.mock.calls[0] as [
      string,
      { decision: string; changeSetId: string },
    ]
    expect(taskId).toBe('chat-task-1')
    expect(approval.decision).toBe('approve')
    expect(approval.changeSetId).toBe('cs-1')
    // 审批后底部审查栏消失（任务完成），输入框恢复
    expect(wrapper.find('[data-testid="pending-approve"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="chat-input"]').exists()).toBe(true)
  })

  it('待审批任务存在时底部显示审查/拒绝而非输入框', async () => {
    mockSessionWithEditSummary()
    const { wrapper } = await mountWorkspace()
    expect(wrapper.find('[data-testid="pending-approve"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="pending-reject"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="pending-view-diff"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="chat-input"]').exists()).toBe(false)
  })

  it('Provider 未就绪时禁用输入框并提示去设置', async () => {
    m.mocks.getSettings.mockResolvedValue(unconfiguredSettings)
    const { wrapper } = await mountWorkspace()
    const input = wrapper.get('[data-testid="chat-input"]')
    expect(input.attributes('disabled')).toBeDefined()
    expect(wrapper.get('[data-testid="provider-hint"]').exists()).toBe(true)
    expect(wrapper.get('[data-testid="provider-status"]').text()).toContain('未配置')
  })

  it('error 消息只渲染固定文案，不渲染服务端自由 message', async () => {
    m.mocks.getChatSession.mockResolvedValue({
      session: m.session,
      messages: [
        {
          ...m.assistantMsg,
          sequence: 1,
          id: 'msg-err',
          kind: 'error',
          content: 'Authorization: Bearer secret-value; sk-abcdefghijklmnopqrstuvwxyz; C:\\private',
        },
      ],
    })
    const { wrapper } = await mountWorkspace()
    const error = wrapper.get('[data-testid="error-message"]')
    expect(error.text()).toContain('模型处理失败')
    expect(error.text()).not.toContain('secret-value')
    expect(error.text()).not.toContain('sk-abcdefghijklmnopqrstuvwxyz')
    expect(error.text()).not.toContain('Authorization')
    expect(error.text()).not.toContain('C:\\private')
  })

  it('Enter 发送消息：调用 submitMessage 并把返回消息追加到流', async () => {
    const { wrapper } = await mountWorkspace()
    const input = wrapper.get('[data-testid="chat-input"]')
    await input.setValue('继续')
    await input.trigger('keydown.enter')
    await flushPromises()

    expect(m.mocks.submitMessage).toHaveBeenCalledWith('chat-1', '继续')
    expect(wrapper.findAll('[data-testid="chat-message"]').length).toBe(3)
    expect(wrapper.text()).toContain('已完成审查流程。')
  })
})
