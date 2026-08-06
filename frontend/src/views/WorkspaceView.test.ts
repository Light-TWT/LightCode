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
      renameChatSession: vi.fn(),
      deleteChatSession: vi.fn(),
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
    renameChatSession: m.mocks.renameChatSession,
    deleteChatSession: m.mocks.deleteChatSession,
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

async function mountWorkspace(attachToBody = false) {
  const router = createTestRouter()
  await router.push('/workspace/ws-1/session/chat-1')
  await router.isReady()
  const wrapper = mount(WorkspaceView, {
    global: { plugins: [router] },
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
})
