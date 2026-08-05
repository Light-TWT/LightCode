import { afterEach, describe, expect, it, vi } from 'vitest'
import { registeredWorkspaceService } from './registered-workspace.service'

describe('registeredWorkspaceService（HTTP-only）', () => {
  afterEach(() => {
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
  })

  function stubFetch(payload: unknown) {
    const fetchMock = vi.fn(async () => ({
      ok: true,
      json: async () => payload,
    }))
    vi.stubGlobal('fetch', fetchMock)
    return fetchMock
  }

  it('lists registered workspaces without any root path field', async () => {
    const fetchMock = stubFetch([
      {
        id: 'ws-1',
        displayName: 'Demo',
        enabled: true,
        capabilities: ['read', 'search'],
        policyVersion: 'policy-v1',
      },
    ])
    const workspaces = await registeredWorkspaceService.listRegisteredWorkspaces()
    expect(String(fetchMock.mock.calls[0][0])).toContain('/registered-workspaces')
    for (const ws of workspaces) {
      expect(ws).toHaveProperty('id')
      expect(ws).toHaveProperty('displayName')
      expect(ws).toHaveProperty('enabled')
      expect(ws).toHaveProperty('capabilities')
      expect(ws).toHaveProperty('policyVersion')
      // 安全不变量：公共视图绝不包含真实根路径
      expect(ws).not.toHaveProperty('rootPath')
    }
  })

  it('hits the endpoints with encoded query params (token-only navigation)', async () => {
    const fetchMock = stubFetch([])

    await registeredWorkspaceService.listFiles('ws-1', 'src/sub dir')
    expect(fetchMock.mock.calls[0][0]).toContain(
      '/registered-workspaces/ws-1/files?nodeToken=src%2Fsub%20dir',
    )

    await registeredWorkspaceService.search('ws-1', 'a&b')
    expect(fetchMock.mock.calls[1][0]).toContain(
      '/registered-workspaces/ws-1/search?query=a%26b',
    )
  })

  it('reads a single file via the fileToken endpoint', async () => {
    const fetchMock = stubFetch({ content: 'x' })
    const file = await registeredWorkspaceService.readFile('ws-1', 'NOTES.md')
    expect(fetchMock.mock.calls[0][0]).toContain(
      '/registered-workspaces/ws-1/file?fileToken=NOTES.md',
    )
    expect(file.content).toBe('x')
  })
})
