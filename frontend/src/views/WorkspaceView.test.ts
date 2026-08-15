import { flushPromises, mount } from '@vue/test-utils'
import { nextTick } from 'vue'
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
    createdAt: '2026-08-06T15:36:00.000Z',
    updatedAt: '2026-08-06T15:37:00.000Z',
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
      renameChatSession: vi.fn(),
      deleteChatSession: vi.fn(),
      getRealTask: vi.fn(),
      submitApproval: vi.fn(),
      createRealTask: vi.fn(),
      getSettings: vi.fn(),
      getHealth: vi.fn(),
      listProviders: vi.fn(),
      createProvider: vi.fn(),
      testConnection: vi.fn(),
      clearSettings: vi.fn(),
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
    renameChatSession: m.mocks.renameChatSession,
    deleteChatSession: m.mocks.deleteChatSession,
  },
}))
vi.mock('@/services/provider.service', () => ({
  providerService: {
    getSettings: m.mocks.getSettings,
    getHealth: m.mocks.getHealth,
    listProviders: m.mocks.listProviders,
    createProvider: m.mocks.createProvider,
    testConnection: m.mocks.testConnection,
    clearSettings: m.mocks.clearSettings,
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
    ],
  })
}

async function mountWorkspace(attachToBody = false) {
  const router = createTestRouter()
  await router.push('/workspace/ws-1/session/chat-1')
  await router.isReady()
  const wrapper = mount(WorkspaceView, {
    global: { plugins: [router], stubs: { teleport: true } },
    // 断言 document.activeElement 时需真实挂载到 document（默认挂载在游离节点上，focus 不生效）
    ...(attachToBody ? { attachTo: document.body } : {}),
  })
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
    m.mocks.renameChatSession.mockResolvedValue({ ...m.session, title: '新标题' })
    m.mocks.deleteChatSession.mockResolvedValue({ ok: true })
    m.mocks.getSettings.mockResolvedValue(readySettings)
    m.mocks.listProviders.mockResolvedValue([
      {
        id: 'default',
        name: 'openai-compatible',
        provider: 'openai-compatible',
        modelId: 'demo-model',
        enabled: true,
        status: 'ready',
        baseUrlHost: 'provider.example',
      },
    ])
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

  it('渲染用户（右）与助手（左）消息；点击「会话」展开会话列表', async () => {
    const { wrapper } = await mountWorkspace()
    expect(wrapper.findAll('[data-testid="chat-message"]').length).toBe(2)
    expect(wrapper.find('.user-bubble').text()).toBe('请修改 NOTES.md')
    expect(wrapper.find('.assistant-bubble').text()).toBe('好的，我先看一下文件。')
    // 会话面板默认收起，点击导航项展开
    expect(wrapper.find('[data-testid="session-row"]').exists()).toBe(false)
    await wrapper.get('[data-testid="nav-btn-sessions"]').trigger('click')
    await flushPromises()
    expect(wrapper.findAll('[data-testid="session-row"]').length).toBe(1)
  })

  it('会话悬停侧栏默认隐藏，并在鼠标悬停时显示工作区与 24 小时制时间', async () => {
    const { wrapper } = await mountWorkspace()
    await wrapper.get('[data-testid="nav-btn-sessions"]').trigger('click')
    await flushPromises()

    expect(wrapper.find('[data-testid="session-hover-panel"]').exists()).toBe(false)
    expect(wrapper.get('[data-testid="session-row"]').text()).not.toContain(m.session.updatedAt)

    await wrapper.get('[data-testid="session-row"]').trigger('mouseenter')

    expect(wrapper.get('[data-testid="session-hover-panel"]').exists()).toBe(true)
    expect(wrapper.get('[data-testid="session-hover-title"]').text()).toBe(m.session.title)
    expect(wrapper.get('[data-testid="session-hover-workspace"]').text()).toContain('Demo Workspace')
    expect(wrapper.find('[data-testid="session-hover-workspace-icon"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="session-hover-time-icon"]').exists()).toBe(true)
    const d = new Date(m.session.updatedAt)
    const hh = String(d.getHours()).padStart(2, '0')
    const mm = String(d.getMinutes()).padStart(2, '0')
    const timeText = wrapper.get('[data-testid="session-hover-updated"]').text()
    expect(timeText).toContain(`会话更新时间：${hh}:${mm}`)
    expect(timeText).toMatch(/会话更新时间：\d{2}:\d{2}$/)
    expect(wrapper.find('[data-testid="session-hover-relative"]').exists()).toBe(false)
  })

  it('离开会话区域隐藏悬停侧栏，键盘 focus 会话行时显示', async () => {
    const { wrapper } = await mountWorkspace()
    await wrapper.get('[data-testid="nav-btn-sessions"]').trigger('click')
    await flushPromises()
    const sessionArea = wrapper.get('.session-area')
    const sessionRow = wrapper.get('[data-testid="session-row"]')

    await sessionRow.trigger('mouseenter')
    expect(wrapper.get('[data-testid="session-hover-panel"]').exists()).toBe(true)

    await sessionArea.trigger('mouseleave')
    expect(wrapper.find('[data-testid="session-hover-panel"]').exists()).toBe(false)

    await sessionRow.trigger('focus')
    expect(wrapper.get('[data-testid="session-hover-panel"]').exists()).toBe(true)
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

  it('折叠侧边栏为窄图标条；点击导航项展开面板，再点一次收起', async () => {
    m.mocks.listFiles.mockResolvedValue([{ name: 'NOTES.md', kind: 'file', token: 'tok-notes' }])
    const { wrapper } = await mountWorkspace()
    // 初始：导航展开，面板收起
    expect(wrapper.find('.sidebar.collapsed').exists()).toBe(false)
    expect(wrapper.find('[data-testid="panel-files"]').exists()).toBe(false)

    // 点击箭头折叠 → 导航变窄图标条
    await wrapper.get('[data-testid="sidebar-collapse"]').trigger('click')
    expect(wrapper.find('.sidebar.collapsed').exists()).toBe(true)

    // 点击「文件浏览」→ 面板展开
    await wrapper.get('[data-testid="nav-btn-files"]').trigger('click')
    await flushPromises()
    expect(wrapper.get('[data-testid="panel-files"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="file-entry"]').exists()).toBe(true)

    // 再点一次 → 面板收起
    await wrapper.get('[data-testid="nav-btn-files"]').trigger('click')
    await flushPromises()
    expect(wrapper.find('[data-testid="panel-files"]').exists()).toBe(false)
  })

  it('文件浏览面板内点击文件行展开预览，再点一次收起', async () => {
    m.mocks.listFiles.mockResolvedValue([
      { name: 'NOTES.md', kind: 'file', token: 'tok-notes' },
      { name: 'src', kind: 'dir', token: 'tok-src' },
    ])
    m.mocks.readFile.mockResolvedValue({ content: '第一行\n第二行' })
    const { wrapper } = await mountWorkspace()

    await wrapper.get('[data-testid="nav-btn-files"]').trigger('click')
    await flushPromises()
    expect(wrapper.findAll('[data-testid="file-entry"]').length).toBe(2)

    // 点击文件行 → 预览区展开，内容为 readFile 返回
    await wrapper.get('[data-testid="file-entry"]').trigger('click')
    await flushPromises()
    expect(m.mocks.readFile).toHaveBeenCalledWith('ws-1', 'tok-notes')
    expect(wrapper.get('[data-testid="file-preview"]').exists()).toBe(true)
    expect(wrapper.get('[data-testid="preview-content"]').text()).toBe('第一行\n第二行')

    // 再点一次同一文件 → 预览收起
    await wrapper.get('[data-testid="file-entry"]').trigger('click')
    await flushPromises()
    expect(wrapper.find('[data-testid="file-preview"]').exists()).toBe(false)
  })

  it('三点菜单：点击打开，再次点击关闭，Escape 关闭', async () => {
    const { wrapper } = await mountWorkspace()
    await wrapper.get('[data-testid="nav-btn-sessions"]').trigger('click')
    await flushPromises()
    const more = wrapper.get('[data-testid="session-more"]')
    expect(wrapper.find('[data-testid="session-menu"]').exists()).toBe(false)

    await more.trigger('click')
    expect(wrapper.find('[data-testid="session-menu"]').exists()).toBe(true)

    await more.trigger('click')
    expect(wrapper.find('[data-testid="session-menu"]').exists()).toBe(false)

    await more.trigger('click')
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }))
    await flushPromises()
    expect(wrapper.find('[data-testid="session-menu"]').exists()).toBe(false)
  })

  it('重命名：打开独立弹窗，输入可用并回车提交后同步列表', async () => {
    const { wrapper } = await mountWorkspace()
    await wrapper.get('[data-testid="nav-btn-sessions"]').trigger('click')
    await flushPromises()
    await wrapper.get('[data-testid="session-more"]').trigger('click')
    await wrapper.get('[data-testid="session-rename"]').trigger('click')
    await flushPromises()

    expect(wrapper.find('[data-testid="session-menu"]').exists()).toBe(false)
    expect(wrapper.get('[data-testid="rename-dialog"]').attributes('role')).toBe('dialog')
    const input = wrapper.get('[data-testid="rename-dialog-input"]')
    expect((input.element as HTMLInputElement).value).toBe('新会话')
    await input.trigger('focus')
    await input.setValue('新标题')
    m.mocks.renameChatSession.mockResolvedValue({ ...m.session, title: '新标题' })
    await wrapper.get('[data-testid="rename-dialog-form"]').trigger('submit')
    await flushPromises()

    expect(m.mocks.renameChatSession).toHaveBeenCalledWith('chat-1', 'ws-1', '新标题')
    expect(wrapper.find('[data-testid="rename-dialog"]').exists()).toBe(false)
    expect(wrapper.get('[data-testid="session-row"]').text()).toContain('新标题')
  })

  it('重命名：Escape、取消、遮罩和空白标题不提交', async () => {
    const { wrapper } = await mountWorkspace()
    await wrapper.get('[data-testid="nav-btn-sessions"]').trigger('click')
    await flushPromises()

    await wrapper.get('[data-testid="session-more"]').trigger('click')
    await wrapper.get('[data-testid="session-rename"]').trigger('click')
    await wrapper.get('[data-testid="rename-dialog-input"]').trigger('keydown.esc')
    expect(wrapper.find('[data-testid="rename-dialog"]').exists()).toBe(false)

    await wrapper.get('[data-testid="session-more"]').trigger('click')
    await wrapper.get('[data-testid="session-rename"]').trigger('click')
    await wrapper.get('[data-testid="rename-dialog-cancel"]').trigger('click')
    expect(wrapper.find('[data-testid="rename-dialog"]').exists()).toBe(false)

    await wrapper.get('[data-testid="session-more"]').trigger('click')
    await wrapper.get('[data-testid="session-rename"]').trigger('click')
    await wrapper.get('[data-testid="rename-dialog"]').trigger('click.self')
    expect(wrapper.find('[data-testid="rename-dialog"]').exists()).toBe(false)

    await wrapper.get('[data-testid="session-more"]').trigger('click')
    await wrapper.get('[data-testid="session-rename"]').trigger('click')
    await wrapper.get('[data-testid="rename-dialog-input"]').setValue('   ')
    await wrapper.get('[data-testid="rename-dialog-form"]').trigger('submit')
    await flushPromises()
    expect(m.mocks.renameChatSession).not.toHaveBeenCalled()
  })

  it('重命名：请求进行中禁用输入和按钮，失败时保留弹窗与草稿', async () => {
    const { wrapper } = await mountWorkspace()
    await wrapper.get('[data-testid="nav-btn-sessions"]').trigger('click')
    await flushPromises()
    await wrapper.get('[data-testid="session-more"]').trigger('click')
    await wrapper.get('[data-testid="session-rename"]').trigger('click')
    const input = wrapper.get('[data-testid="rename-dialog-input"]')
    await input.setValue('保留草稿')

    let rejectRename: (reason?: unknown) => void = () => {}
    m.mocks.renameChatSession.mockImplementation(() => new Promise((_, reject) => { rejectRename = reject }))
    await wrapper.get('[data-testid="rename-dialog-form"]').trigger('submit')
    await nextTick()
    expect(wrapper.get('[data-testid="rename-dialog-input"]').attributes('disabled')).toBeDefined()
    expect(wrapper.get('[data-testid="rename-dialog-cancel"]').attributes('disabled')).toBeDefined()
    expect(wrapper.get('[data-testid="rename-dialog-confirm"]').text()).toContain('保存中…')

    rejectRename(new Error('rename failed'))
    await flushPromises()
    expect(wrapper.find('[data-testid="rename-dialog"]').exists()).toBe(true)
    expect((wrapper.get('[data-testid="rename-dialog-input"]').element as HTMLInputElement).value).toBe('保留草稿')
  })

  it('删除：取消不调用接口，确认后删除并从列表移除', async () => {
    m.mocks.listChatSessions.mockResolvedValue([
      m.session,
      { ...m.session, id: 'chat-2', title: '第二个' },
    ])
    const { wrapper } = await mountWorkspace(true)
    await wrapper.get('[data-testid="nav-btn-sessions"]').trigger('click')
    await flushPromises()
    expect(wrapper.findAll('[data-testid="session-row"]').length).toBe(2)

    // 打开菜单 → 删除 → 取消
    await wrapper.get('[data-testid="session-more"]').trigger('click')
    await wrapper.get('[data-testid="session-delete"]').trigger('click')
    expect(wrapper.find('[data-testid="delete-dialog"]').exists()).toBe(true)
    // 默认焦点落在「取消」按钮（规格要求）
    await flushPromises()
    expect(document.activeElement).toBe(wrapper.get('[data-testid="delete-cancel"]').element)
    await wrapper.get('[data-testid="delete-cancel"]').trigger('click')
    expect(wrapper.find('[data-testid="delete-dialog"]').exists()).toBe(false)
    expect(m.mocks.deleteChatSession).not.toHaveBeenCalled()

    // 再次删除 → 确认
    await wrapper.get('[data-testid="session-more"]').trigger('click')
    await wrapper.get('[data-testid="session-delete"]').trigger('click')
    await wrapper.get('[data-testid="delete-confirm"]').trigger('click')
    await flushPromises()

    expect(m.mocks.deleteChatSession).toHaveBeenCalledWith('chat-1', 'ws-1')
    expect(wrapper.findAll('[data-testid="session-row"]').length).toBe(1)
  })

  it('删除进行中禁用两个对话框按钮', async () => {
    const { wrapper } = await mountWorkspace()
    await wrapper.get('[data-testid="nav-btn-sessions"]').trigger('click')
    await flushPromises()
    await wrapper.get('[data-testid="session-more"]').trigger('click')
    await wrapper.get('[data-testid="session-delete"]').trigger('click')

    let resolveDelete: (v: { ok: boolean }) => void = () => {}
    m.mocks.deleteChatSession.mockImplementation(
      () => new Promise((r) => { resolveDelete = r }),
    )
    await wrapper.get('[data-testid="delete-confirm"]').trigger('click')
    await flushPromises()

    expect(wrapper.get('[data-testid="delete-confirm"]').attributes('disabled')).toBeDefined()
    expect(wrapper.get('[data-testid="delete-cancel"]').attributes('disabled')).toBeDefined()

    resolveDelete({ ok: true })
    await flushPromises()
  })

  it('设置层：点击设置按钮在工作区上方打开，工作区内容仍保留在 DOM', async () => {
    const { wrapper } = await mountWorkspace()
    expect(wrapper.find('[data-testid="settings-overlay"]').exists()).toBe(false)

    await wrapper.get('[data-testid="settings-btn"]').trigger('click')
    await flushPromises()

    // 模态层出现且为对话框语义
    expect(wrapper.get('[data-testid="settings-overlay"]').exists()).toBe(true)
    expect(wrapper.get('[data-testid="settings-modal"]').attributes('role')).toBe('dialog')
    expect(wrapper.get('[data-testid="settings-modal"]').attributes('aria-modal')).toBe('true')
    // 工作区未卸载：消息流、输入框仍在
    expect(wrapper.findAll('[data-testid="chat-message"]').length).toBe(2)
    expect(wrapper.get('[data-testid="chat-input"]').exists()).toBe(true)
    // 复用设置业务内容：分类、供应商列表、详情与添加入口
    expect(wrapper.get('[data-testid="settings-cat-providers"]').exists()).toBe(true)
    expect(wrapper.get('[data-testid="settings-cat-about"]').exists()).toBe(true)
    expect(wrapper.get('[data-testid="provider-row-default"]').exists()).toBe(true)
    expect(wrapper.get('[data-testid="detail-name"]').text()).toBe('openai-compatible')
    expect(wrapper.get('[data-testid="open-add"]').exists()).toBe(true)
    // 模态层不显示独立设置页的「返回」入口（工作区页头部的返回按钮不在模态层内）
    expect(wrapper.find('[data-testid="settings-modal"] [data-testid="back-home-btn"]').exists()).toBe(false)
    // 模态层内可切换到「关于」
    await wrapper.get('[data-testid="settings-cat-about"]').trigger('click')
    await flushPromises()
    expect(wrapper.get('[data-testid="about-panel"]').exists()).toBe(true)
  })

  it('设置层：关闭按钮、Esc、遮罩点击均关闭，工作区内容不丢失', async () => {
    const { wrapper } = await mountWorkspace()

    // 关闭按钮
    await wrapper.get('[data-testid="settings-btn"]').trigger('click')
    await flushPromises()
    await wrapper.get('[data-testid="settings-overlay-close"]').trigger('click')
    await flushPromises()
    expect(wrapper.find('[data-testid="settings-overlay"]').exists()).toBe(false)

    // Esc
    await wrapper.get('[data-testid="settings-btn"]').trigger('click')
    await flushPromises()
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }))
    await flushPromises()
    expect(wrapper.find('[data-testid="settings-overlay"]').exists()).toBe(false)

    // 遮罩点击
    await wrapper.get('[data-testid="settings-btn"]').trigger('click')
    await flushPromises()
    await wrapper.get('[data-testid="settings-overlay"]').trigger('click.self')
    await flushPromises()
    expect(wrapper.find('[data-testid="settings-overlay"]').exists()).toBe(false)

    // 无论哪种方式关闭，工作区内容与输入框仍在
    expect(wrapper.findAll('[data-testid="chat-message"]').length).toBe(2)
    expect(wrapper.get('[data-testid="chat-input"]').exists()).toBe(true)
  })

  it('设置层：关闭后路由与会话不变，焦点回到设置按钮', async () => {
    const { wrapper, router } = await mountWorkspace(true)
    const settingsBtn = wrapper.get('[data-testid="settings-btn"]')
    ;(settingsBtn.element as HTMLElement).focus()
    await settingsBtn.trigger('click')
    await flushPromises()
    // 打开后焦点进入设置层面板
    expect(document.activeElement).toBe(wrapper.get('[data-testid="settings-modal"]').element)

    await wrapper.get('[data-testid="settings-overlay-close"]').trigger('click')
    await flushPromises()
    expect(wrapper.find('[data-testid="settings-overlay"]').exists()).toBe(false)
    // 不跳转路由、不重建会话
    expect(router.currentRoute.value.fullPath).toBe('/workspace/ws-1/session/chat-1')
    expect(document.activeElement).toBe(settingsBtn.element)
  })

  it('设置层：添加供应商弹层在设置层上方打开，Esc 只关闭弹层', async () => {
    // 真实挂载到 document：弹层内按键事件需沿 DOM 树到达 document 级 Esc 监听
    const { wrapper } = await mountWorkspace(true)
    await wrapper.get('[data-testid="settings-btn"]').trigger('click')
    await flushPromises()
    await wrapper.get('[data-testid="open-add"]').trigger('click')
    await flushPromises()

    expect(wrapper.get('[data-testid="settings-overlay"]').exists()).toBe(true)
    expect(wrapper.get('[data-testid="modal-api-key"]').exists()).toBe(true)

    // 键盘场景：焦点在弹层输入框内按 Esc，只关闭弹层（capture 截断）
    const keyInput = wrapper.get('[data-testid="modal-api-key"]')
    ;(keyInput.element as HTMLInputElement).focus()
    expect(document.activeElement).toBe(keyInput.element)
    await keyInput.trigger('keydown', { key: 'Escape' })
    await flushPromises()
    // 弹层关闭，设置层保持打开
    expect(wrapper.find('[data-testid="modal-api-key"]').exists()).toBe(false)
    expect(wrapper.get('[data-testid="settings-overlay"]').exists()).toBe(true)
  })

  it('设置层：关闭后重新打开，添加供应商弹层的 API Key 输入为空', async () => {
    const { wrapper } = await mountWorkspace()
    await wrapper.get('[data-testid="settings-btn"]').trigger('click')
    await flushPromises()
    await wrapper.get('[data-testid="open-add"]').trigger('click')
    await flushPromises()
    await wrapper.get('[data-testid="modal-api-key"]').setValue('sk-top-secret')
    expect((wrapper.get('[data-testid="modal-api-key"]').element as HTMLInputElement).value).toBe('sk-top-secret')

    // 关闭设置层（整棵内容树销毁，含弹层输入）
    await wrapper.get('[data-testid="settings-overlay-close"]').trigger('click')
    await flushPromises()
    expect(wrapper.find('[data-testid="settings-overlay"]').exists()).toBe(false)

    // 重新打开并再次打开弹层：API Key 输入为空，密钥不残留
    await wrapper.get('[data-testid="settings-btn"]').trigger('click')
    await flushPromises()
    await wrapper.get('[data-testid="open-add"]').trigger('click')
    await flushPromises()
    expect((wrapper.get('[data-testid="modal-api-key"]').element as HTMLInputElement).value).toBe('')
    expect(wrapper.text()).not.toContain('sk-top-secret')
  })

  it('Provider 未就绪时提示区「设置」链接打开设置层，不离开工作区', async () => {
    m.mocks.getSettings.mockResolvedValue(unconfiguredSettings)
    const { wrapper } = await mountWorkspace()
    await wrapper.get('[data-testid="open-settings-link"]').trigger('click')
    await flushPromises()
    expect(wrapper.get('[data-testid="settings-overlay"]').exists()).toBe(true)
    expect(wrapper.get('[data-testid="workspace-title"]').exists()).toBe(true)
  })
})
