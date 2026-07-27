import {
  registeredFileContentFixture,
  registeredFilesFixture,
  registeredWorkspacesFixture,
  searchHitsFixture,
} from '@/fixtures/phase1.fixture'
import { isApiMode } from '@/config/runtime'
import { requestJson } from '@/services/http'
import type {
  RegisteredFileContent,
  RegisteredFileEntry,
  RegisteredWorkspace,
  WorkspaceSearchHit,
} from '@/types/agent'

export interface RegisteredWorkspaceService {
  listRegisteredWorkspaces(): Promise<RegisteredWorkspace[]>
  listFiles(workspaceId: string, path?: string): Promise<RegisteredFileEntry[]>
  readFile(workspaceId: string, path: string): Promise<RegisteredFileContent>
  search(workspaceId: string, query: string): Promise<WorkspaceSearchHit[]>
}

export const mockRegisteredWorkspaceService: RegisteredWorkspaceService = {
  async listRegisteredWorkspaces() {
    return structuredClone(registeredWorkspacesFixture)
  },
  async listFiles(_workspaceId, path = '') {
    return structuredClone(registeredFilesFixture[path] ?? [])
  },
  async readFile(_workspaceId, path) {
    return { ...structuredClone(registeredFileContentFixture), relativePath: path }
  },
  async search(_workspaceId, query) {
    if (!query) return []
    return structuredClone(searchHitsFixture)
  },
}

export const httpRegisteredWorkspaceService: RegisteredWorkspaceService = {
  async listRegisteredWorkspaces() {
    return requestJson<RegisteredWorkspace[]>('/registered-workspaces')
  },
  async listFiles(workspaceId, path = '') {
    const suffix = path ? `?path=${encodeURIComponent(path)}` : ''
    return requestJson<RegisteredFileEntry[]>(
      `/registered-workspaces/${workspaceId}/files${suffix}`,
    )
  },
  async readFile(workspaceId, path) {
    return requestJson<RegisteredFileContent>(
      `/registered-workspaces/${workspaceId}/file?path=${encodeURIComponent(path)}`,
    )
  },
  async search(workspaceId, query) {
    return requestJson<WorkspaceSearchHit[]>(
      `/registered-workspaces/${workspaceId}/search?query=${encodeURIComponent(query)}`,
    )
  },
}

export const registeredWorkspaceService = isApiMode
  ? httpRegisteredWorkspaceService
  : mockRegisteredWorkspaceService
