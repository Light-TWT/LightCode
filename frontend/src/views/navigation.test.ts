import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter, type Router } from 'vue-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import RealTaskView from './RealTaskView.vue'
import SkillsView from './SkillsView.vue'
import WorkspaceHomeView from './WorkspaceHomeView.vue'
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
  const message = {
    id: 'msg-1',
    sessionId: 'chat-1',
    sequence: 1,
    role: 'assistant',
    content: '你好，我是 LightCode。',
    kind: 'message',
    taskId: '',
    createdAt: 't',
  }
  const settings = {
    configured: true,
    status: 'ready',
    provider: 'openai-compatible',
    modelId: 'demo-model',
    detail: 'Provider 已就绪。',
    originAllowlisted: true,
    transport: 'https',
  }
  const task = {
    id: 'chat-task-1',
    workspaceId: 'ws-1',
    sessionId: 'chat-1',
    kind: 'model',
    state: 'awaiting_approval',
    title: '让模型追加标记',
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
      saveSettings: vi.fn(),
      testConnection: vi.fn(),
      deleteProvider: vi.fn(),
      listProviders: vi.fn(),
      createProvider: vi.fn(),
      subscribeChatEvents: vi.fn(),
      subscribeRealTaskEvents: vi.fn(),
    },
    ws,
    session,
    message,
    settings,
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
    saveSettings: m.mocks.saveSettings,
    testConnection: m.mocks.testConnection,
    listProviders: m.mocks.listProviders,
    createProvider: m.mocks.createProvider,
    deleteProvider: m.mocks.deleteProvider,
  },
}))
vi.mock('@/services/real-task.service', () => ({
  realTaskService: {
    getRealTask: m.mocks.getRealTask,
    submitApproval: m.mocks.submitApproval,
    createRealTask: m.mocks.createRealTask,
  },
}))
vi.mock('@/services/skills.service', () => ({
  skillsService: {
    list: vi.fn().mockResolvedValue([]),
    get: vi.fn(),
    document: vi.fn(),
    upload: vi.fn(),
    setStatus: vi.fn(),
    remove: vi.fn(),
  },
}))
vi.mock('@/services/event.service', () => ({
  subscribeChatEvents: m.mocks.subscribeChatEvents,
  subscribeRealTaskEvents: m.mocks.subscribeRealTaskEvents,
}))

function createAppRouter(): Router {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', name: 'home', component: WorkspaceHomeView },
      { path: '/workspace/:workspaceId', name: 'workspace', component: WorkspaceView },
      {
        path: '/workspace/:workspaceId/session/:sessionId',
        name: 'workspace-session',
        component: WorkspaceView,
      },
      {
        path: '/workspace/:workspaceId/task/:taskId',
        name: 'real-task',
        component: RealTaskView,
      },
      {
        path: '/workspace/:workspaceId/skills',
        name: 'skills',
        component: SkillsView,
      },
    ],
  })
}

function mountView(component: unknown, router: Router) {
  return mount(component as never, { global: { plugins: [router] } })
}

describe('路由收敛（核心 Agent 更新阶段 A）', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    m.mocks.listRegisteredWorkspaces.mockResolvedValue([m.ws])
    m.mocks.listFiles.mockResolvedValue([])
    m.mocks.readFile.mockResolvedValue({ content: '' })
    m.mocks.search.mockResolvedValue([])
    m.mocks.listChatSessions.mockResolvedValue([m.session])
    m.mocks.createChatSession.mockResolvedValue(m.session)
    m.mocks.getChatSession.mockResolvedValue({ session: m.session, messages: [m.message] })
    m.mocks.submitMessage.mockResolvedValue({ message: m.message, taskId: '' })
    m.mocks.getSettings.mockResolvedValue(m.settings)
    m.mocks.getHealth.mockResolvedValue(null)
    m.mocks.listProviders.mockResolvedValue([])
    m.mocks.getRealTask.mockResolvedValue(m.task)
    m.mocks.submitApproval.mockResolvedValue(m.task)
    m.mocks.subscribeChatEvents.mockReturnValue(() => {})
    m.mocks.subscribeRealTaskEvents.mockReturnValue(() => {})
    // 任务/会话加载后 store 会订阅 SSE（HTTP-only），需桩 EventSource
    vi.stubGlobal('EventSource', vi.fn(function () {
      return { close: vi.fn(), addEventListener: vi.fn() }
    }))
  })
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('/ 存在已注册工作区时停留在首页（不自动重定向）', async () => {
    const router = createAppRouter()
    await router.push('/')
    await router.isReady()
    mountView(WorkspaceHomeView, router)
    await flushPromises()
    expect(router.currentRoute.value.fullPath).toBe('/')
  })

  it('/ 无工作区时仍停留在首页且可从侧边栏打开设置模态层', async () => {
    m.mocks.listRegisteredWorkspaces.mockResolvedValue([])
    const router = createAppRouter()
    await router.push('/')
    await router.isReady()
    const wrapper = mountView(WorkspaceHomeView, router)
    await flushPromises()
    expect(router.currentRoute.value.fullPath).toBe('/')
    await wrapper.get('[data-testid="settings-btn"]').trigger('click')
    await flushPromises()
    // 设置以大型模态层打开（Teleport 到 body），不跳转独立设置页
    expect(router.currentRoute.value.fullPath).toBe('/')
    expect(document.body.querySelector('[data-testid="settings-overlay"]')).toBeTruthy()
  })

  it('/workspace/:workspaceId 渲染聊天主界面', async () => {
    const router = createAppRouter()
    await router.push('/workspace/ws-1')
    await router.isReady()
    const wrapper = mountView(WorkspaceView, router)
    await flushPromises()
    expect(wrapper.get('[data-testid="workspace-title"]').text()).toBe('Demo Workspace')
    expect(wrapper.get('[data-testid="chat-input"]').exists()).toBe(true)
    // 会话面板默认收起，点击导航项展开
    await wrapper.get('[data-testid="nav-btn-sessions"]').trigger('click')
    await flushPromises()
    expect(wrapper.get('[data-testid="session-row"]').exists()).toBe(true)
    expect(m.mocks.listChatSessions).toHaveBeenCalledWith('ws-1')
  })

  it('/workspace/:workspaceId?panel=sessions 打开会话面板（技能页侧边栏跳转）', async () => {
    const router = createAppRouter()
    await router.push('/workspace/ws-1?panel=sessions')
    await router.isReady()
    const wrapper = mountView(WorkspaceView, router)
    await flushPromises()
    expect(wrapper.get('[data-testid="panel-sessions"]').exists()).toBe(true)
  })

  it('/workspace/:workspaceId/session/:sessionId 打开会话并渲染消息', async () => {
    const router = createAppRouter()
    await router.push('/workspace/ws-1/session/chat-1')
    await router.isReady()
    const wrapper = mountView(WorkspaceView, router)
    await flushPromises()
    expect(m.mocks.getChatSession).toHaveBeenCalledWith('chat-1', 'ws-1')
    const messages = wrapper.findAll('[data-testid="chat-message"]')
    expect(messages.length).toBeGreaterThanOrEqual(1)
    expect(wrapper.text()).toContain('你好，我是 LightCode。')
  })

  it('/workspace/:workspaceId/task/:taskId 渲染审查深链（RealTaskView）', async () => {
    const router = createAppRouter()
    await router.push('/workspace/ws-1/task/chat-task-1')
    await router.isReady()
    const wrapper = mountView(RealTaskView, router)
    await flushPromises()
    expect(m.mocks.getRealTask).toHaveBeenCalledWith('chat-task-1')
    expect(wrapper.get('[data-testid="task-state"]').text()).toBe('等待审批')
  })

  it('keeps existing sidebar test ids and appends the Skill navigation button', async () => {
    const router = createAppRouter()
    await router.push('/workspace/ws-1')
    await router.isReady()
    const wrapper = mount(WorkspaceView, {
      global: { plugins: [router, createPinia()], stubs: { teleport: true } },
    })
    await flushPromises()

    expect(wrapper.get('[data-testid="nav-btn-workspace"]').exists()).toBe(true)
    expect(wrapper.get('[data-testid="nav-btn-files"]').exists()).toBe(true)
    expect(wrapper.get('[data-testid="nav-btn-sessions"]').exists()).toBe(true)
    expect(wrapper.get('[data-testid="settings-btn"]').exists()).toBe(true)
    await wrapper.get('[data-testid="nav-btn-skills"]').trigger('click')
    await flushPromises()

    expect(router.currentRoute.value.fullPath).toBe('/workspace/ws-1/skills')
  })

  it('/workspace/:workspaceId/skills 渲染技能管理视图', async () => {
    const router = createAppRouter()
    await router.push('/workspace/ws-1/skills')
    await router.isReady()
    const wrapper = mountView(SkillsView, router)
    await flushPromises()
    expect(wrapper.get('[data-testid="skills-title"]').exists()).toBe(true)
    expect(wrapper.get('[data-testid="skill-upload-button"]').exists()).toBe(true)
  })
})
