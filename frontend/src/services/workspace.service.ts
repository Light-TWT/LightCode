import { sessionsFixture, workspaceFixture } from '@/fixtures/agent.fixture'
import type { Session, Workspace } from '@/types/agent'

export interface WorkspaceService {
  getWorkspace(): Promise<Workspace>
  getSessions(): Promise<Session[]>
}

export const mockWorkspaceService: WorkspaceService = {
  async getWorkspace() {
    return structuredClone(workspaceFixture)
  },
  async getSessions() {
    return structuredClone(sessionsFixture)
  },
}
