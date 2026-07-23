import { sessionsFixture, workspaceEntriesFixture, workspaceFixture } from '@/fixtures/agent.fixture'
import { requestJson } from '@/services/http'
import type { Session, Workspace, WorkspaceEntry } from '@/types/agent'

export interface WorkspaceService {
  getWorkspace(workspaceId: string): Promise<Workspace>
  getSessions(workspaceId: string): Promise<Session[]>
  getRecentWorkspaces(): Promise<WorkspaceEntry[]>
  getAllWorkspaces(): Promise<WorkspaceEntry[]>
}

export const mockWorkspaceService: WorkspaceService = {
  async getWorkspace() {
    return structuredClone(workspaceFixture)
  },
  async getSessions() {
    return structuredClone(sessionsFixture)
  },
  async getRecentWorkspaces() {
    return structuredClone(workspaceEntriesFixture.slice(0, 5))
  },
  async getAllWorkspaces() {
    return structuredClone(workspaceEntriesFixture)
  },
}

export const httpWorkspaceService: WorkspaceService = {
  async getWorkspace(workspaceId) {
    return requestJson<Workspace>(`/workspaces/${workspaceId}`)
  },
  async getSessions(workspaceId) {
    return requestJson<Session[]>(`/workspaces/${workspaceId}/sessions`)
  },
  async getRecentWorkspaces() {
    return requestJson<WorkspaceEntry[]>('/workspaces/recent')
  },
  async getAllWorkspaces() {
    return requestJson<WorkspaceEntry[]>('/workspaces')
  },
}

export const workspaceService = import.meta.env.VITE_LIGHTCODE_RUNTIME === 'api'
  ? httpWorkspaceService
  : mockWorkspaceService
