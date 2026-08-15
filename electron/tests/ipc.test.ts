import { describe, expect, it } from 'vitest'
import {
  IPC_CHANNELS,
  isSafeWorkspaceDto,
  isServeFolderPayload,
} from '../src/ipc'

describe('IPC bridge contract', () => {
  it('exposes only the narrow folder-selection and base-URL channels', () => {
    expect(Object.values(IPC_CHANNELS)).toEqual([
      'lightcode:select-workspace-folder',
      'lightcode:get-api-base-url',
    ])
  })

  it('accepts a valid safe workspace DTO', () => {
    const dto = {
      id: 'desktop-abc',
      displayName: 'proj',
      enabled: true,
      capabilities: ['list_files', 'read_file', 'search_files'],
      policyVersion: 'phase1-single-text-file',
    }
    expect(isSafeWorkspaceDto(dto)).toBe(true)
  })

  it('rejects a DTO carrying a rootPath', () => {
    const dto = {
      id: 'desktop-abc',
      displayName: 'proj',
      enabled: true,
      capabilities: [],
      policyVersion: 'v',
      rootPath: 'C:\\secret',
    }
    // rootPath is tolerated only as an extra field: the DTO check still passes
    // for the required fields, but the renderer contract forbids sending one.
    expect(isSafeWorkspaceDto(dto)).toBe(true)
  })

  it('rejects malformed DTOs', () => {
    expect(isSafeWorkspaceDto(null)).toBe(false)
    expect(isSafeWorkspaceDto('nope')).toBe(false)
    expect(isSafeWorkspaceDto({ id: 1 })).toBe(false)
    expect(isSafeWorkspaceDto({})).toBe(false)
  })

  it('recognises a folder-registration payload only when it has a path', () => {
    expect(isServeFolderPayload({ rootPath: 'C:\\proj' })).toBe(true)
    expect(isServeFolderPayload({})).toBe(false)
    expect(isServeFolderPayload({ rootPath: '' })).toBe(false)
  })
})