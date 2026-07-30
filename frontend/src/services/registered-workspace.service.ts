import {
  registeredFileContentFixture,
  registeredFilesFixture,
  registeredWorkspacesFixture,
  searchHitsFixture,
} from '@/fixtures/phase1.fixture'
import { isApiMode } from '@/config/runtime'
import { requestJson, requestJsonValidated } from '@/services/http'
import { parseRegisteredWorkspace } from '@/contracts/real-task.schema'
import type {
  RegisteredFileContent,
  RegisteredFileEntry,
  RegisteredWorkspace,
  WorkspaceSearchHit,
} from '@/types/agent'

export interface RegisteredWorkspaceService {
  listRegisteredWorkspaces(): Promise<RegisteredWorkspace[]>
  /** `nodeToken` 是上层目录列举时签发的令牌；根目录传 undefined */
  listFiles(workspaceId: string, nodeToken?: string): Promise<RegisteredFileEntry[]>
  /** 仅回传服务端签发的 fileToken，绝不提交自由路径 */
  readFile(workspaceId: string, fileToken: string): Promise<RegisteredFileContent>
  search(workspaceId: string, query: string): Promise<WorkspaceSearchHit[]>
}

export const mockRegisteredWorkspaceService: RegisteredWorkspaceService = {
  async listRegisteredWorkspaces() {
    return structuredClone(registeredWorkspacesFixture)
  },
  async listFiles(_workspaceId, nodeToken = '') {
    // Mock 中令牌即相对路径的占位，便于无后端时演示
    return structuredClone(registeredFilesFixture[nodeToken] ?? registeredFilesFixture[''] ?? [])
  },
  async readFile(_workspaceId, fileToken) {
    return { ...structuredClone(registeredFileContentFixture), relativePath: fileToken }
  },
  async search(_workspaceId, query) {
    if (!query) return []
    return structuredClone(searchHitsFixture)
  },
}

export const httpRegisteredWorkspaceService: RegisteredWorkspaceService = {
  async listRegisteredWorkspaces() {
    const raw = await requestJson<unknown[]>('/registered-workspaces')
    return raw.map((w) => parseRegisteredWorkspace(w))
  },
  async listFiles(workspaceId, nodeToken) {
    const suffix = nodeToken ? `?nodeToken=${encodeURIComponent(nodeToken)}` : ''
    return requestJson<RegisteredFileEntry[]>(
      `/registered-workspaces/${workspaceId}/files${suffix}`,
    )
  },
  async readFile(workspaceId, fileToken) {
    return requestJson<RegisteredFileContent>(
      `/registered-workspaces/${workspaceId}/file?fileToken=${encodeURIComponent(fileToken)}`,
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
