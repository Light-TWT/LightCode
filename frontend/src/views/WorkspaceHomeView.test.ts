import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter, type Router } from 'vue-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import WorkspaceHomeView from './WorkspaceHomeView.vue'

const m = vi.hoisted(() => {
  const ws = {
    id: 'ws-1',
    displayName: 'Demo Workspace',
    enabled: true,
    capabilities: ['list_files', 'read_file', 'search_files'],
    policyVersion: 'policy-v1',
  }
  return {
    ws,
    mocks: {
      listRegisteredWorkspaces: vi.fn(),
      createChatSession: vi.fn(),
      submitMessage: vi.fn(),
      subscribeChatEvents: vi.fn(),
      isDesktopAvailable: vi.fn(),
      selectFolder: vi.fn(),
    },
  }
})

vi.mock('@/services/registered-workspace.service', () => ({
  registeredWorkspaceService: {
    listRegisteredWorkspaces: m.mocks.listRegisteredWorkspaces,
  },
}))
vi.mock('@/services/chat.service', () => ({
  chatService: {
    listChatSessions: vi.fn(),
    createChatSession: m.mocks.createChatSession,
    getChatSession: vi.fn(),
    submitMessage: m.mocks.submitMessage,
    renameChatSession: vi.fn(),
    deleteChatSession: vi.fn(),
  },
}))
vi.mock('@/services/event.service', () => ({
  subscribeChatEvents: m.mocks.subscribeChatEvents,
  subscribeRealTaskEvents: vi.fn(),
}))
vi.mock('@/services/desktop.service', () => ({
  isDesktopAvailable: m.mocks.isDesktopAvailable,
  selectFolder: m.mocks.selectFolder,
}))

function createTestRouter(): Router {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', name: 'home', component: WorkspaceHomeView },
      { path: '/workspace/:workspaceId', name: 'workspace', component: { template: '<div>ws</div>' } },
      {
        path: '/workspace/:workspaceId/session/:sessionId',
        name: 'workspace-session',
        component: { template: '<div>session</div>' },
      },
    ],
  })
}

async function mountHome() {
  const router = createTestRouter()
  await router.push('/')
  await router.isReady()
  const wrapper = mount(WorkspaceHomeView, { global: { plugins: [router] } })
  await flushPromises()
  return { wrapper, router }
}

describe('WorkspaceHomeView（首页）', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    m.mocks.listRegisteredWorkspaces.mockResolvedValue([])
    m.mocks.isDesktopAvailable.mockReturnValue(true)
    m.mocks.createChatSession.mockResolvedValue({
      id: 'chat-1',
      workspaceId: 'ws-1',
      title: '新会话',
      status: 'active',
      createdAt: 't',
      updatedAt: 't',
    })
    m.mocks.submitMessage.mockResolvedValue({
      message: { id: 'm', sessionId: 'chat-1', sequence: 1, role: 'user', content: 'hi', kind: 'message', taskId: '', createdAt: 't' },
    })
  })

  it('does not auto-redirect to a workspace', async () => {
    m.mocks.listRegisteredWorkspaces.mockResolvedValue([m.ws])
    const { router } = await mountHome()
    expect(router.currentRoute.value.name).toBe('home')
  })

  it('disables the composer and send when no workspace is selected', async () => {
    const { wrapper } = await mountHome()
    expect(wrapper.get('[data-testid="home-chat-input"]').attributes('disabled')).toBeDefined()
    expect(wrapper.get('[data-testid="home-send"]').attributes('disabled')).toBeDefined()
  })

  it('selects a folder and sets it as the current workspace', async () => {
    m.mocks.listRegisteredWorkspaces.mockResolvedValue([m.ws])
    m.mocks.selectFolder.mockResolvedValue({ cancelled: false, workspace: m.ws })
    const { wrapper } = await mountHome()
    await wrapper.get('[data-testid="picker-trigger"]').trigger('click')
    await wrapper.get('[data-testid="pick-folder-btn"]').trigger('click')
    await flushPromises()
    expect(m.mocks.selectFolder).toHaveBeenCalled()
    // The input becomes enabled once a workspace is selected.
    expect(wrapper.get('[data-testid="home-chat-input"]').attributes('disabled')).toBeUndefined()
  })

  it('stays on the homepage when the folder picker is cancelled', async () => {
    m.mocks.listRegisteredWorkspaces.mockResolvedValue([])
    m.mocks.selectFolder.mockResolvedValue({ cancelled: true })
    const { wrapper, router } = await mountHome()
    await wrapper.get('[data-testid="picker-trigger"]').trigger('click')
    await wrapper.get('[data-testid="pick-folder-btn"]').trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.name).toBe('home')
  })

  it('creates a session and navigates on the first message', async () => {
    m.mocks.listRegisteredWorkspaces.mockResolvedValue([m.ws])
    const { wrapper, router } = await mountHome()
    // Select the folder as current workspace.
    m.mocks.selectFolder.mockResolvedValue({ cancelled: false, workspace: m.ws })
    await wrapper.get('[data-testid="picker-trigger"]').trigger('click')
    await wrapper.get('[data-testid="pick-folder-btn"]').trigger('click')
    await flushPromises()
    await wrapper.get('[data-testid="home-chat-input"]').setValue('帮我看看这个项目')
    await wrapper.get('[data-testid="home-send"]').trigger('click')
    await flushPromises()
    expect(m.mocks.createChatSession).toHaveBeenCalled()
    expect(m.mocks.submitMessage).toHaveBeenCalled()
    expect(router.currentRoute.value.name).toBe('workspace-session')
  })
})