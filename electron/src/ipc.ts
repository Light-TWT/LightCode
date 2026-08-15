/**
 * IPC channel constants and runtime validation for the Electron trust bridge.
 *
 * The renderer only ever receives a validated, path-free {@link SafeWorkspaceDto}.
 * Raw folder paths never cross the preload boundary in renderer-facing payloads.
 */

export interface SafeWorkspaceDto {
  id: string
  displayName: string
  enabled: boolean
  capabilities: string[]
  policyVersion: string
}

export interface SelectFolderResultOk {
  cancelled: false
  workspace: SafeWorkspaceDto
}

export interface SelectFolderResultCancel {
  cancelled: true
}

export interface SelectFolderResultError {
  cancelled: false
  error: string
}

export type SelectFolderResult =
  | SelectFolderResultOk
  | SelectFolderResultCancel
  | SelectFolderResultError

export const IPC_CHANNELS = {
  selectWorkspaceFolder: 'lightcode:select-workspace-folder',
  getApiBaseUrl: 'lightcode:get-api-base-url',
} as const

/** The sidecar registration payload is constructed only by Electron main. */
export interface RegisterPayload {
  rootPath: string
}

export function isSafeWorkspaceDto(value: unknown): value is SafeWorkspaceDto {
  if (typeof value !== 'object' || value === null) return false
  const o = value as Record<string, unknown>
  return (
    typeof o.id === 'string' &&
    typeof o.displayName === 'string' &&
    typeof o.enabled === 'boolean' &&
    Array.isArray(o.capabilities) &&
    o.capabilities.every((c) => typeof c === 'string') &&
    typeof o.policyVersion === 'string'
  )
}

export function isServeFolderPayload(value: unknown): value is RegisterPayload {
  if (typeof value !== 'object' || value === null) return false
  const o = value as Record<string, unknown>
  return typeof o.rootPath === 'string' && o.rootPath.length > 0
}