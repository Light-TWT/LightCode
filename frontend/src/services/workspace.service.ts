import { sessionsFixture, workspaceEntriesFixture, workspaceFixture } from '@/fixtures/agent.fixture'
import type { Session, Workspace, WorkspaceEntry } from '@/types/agent'

export interface WorkspaceService {
  getWorkspace(): Promise<Workspace>
  getSessions(): Promise<Session[]>
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
