import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  httpRegisteredWorkspaceService,
  mockRegisteredWorkspaceService,
} from './registered-workspace.service'

describe('mockRegisteredWorkspaceService', () => {
  it('lists registered workspaces without any root path field', async () => {
    const workspaces = await mockRegisteredWorkspaceService.listRegisteredWorkspaces()

    expect(workspaces.length).toBeGreaterThan(0)
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

  it('lists root and subdirectory entries with kind markers', async () => {
    const root = await mockRegisteredWorkspaceService.listFiles('demo-real-workspace')
    expect(root.some((e) => e.kind === 'dir')).toBe(true)
    expect(root.some((e) => e.kind === 'secret')).toBe(true)

    const sub = await mockRegisteredWorkspaceService.listFiles('demo-real-workspace', 'src')
    expect(sub).toHaveLength(1)
    expect(sub[0].kind).toBe('file')
  })

  it('reads file content and searches by query', async () => {
    const file = await mockRegisteredWorkspaceService.readFile('demo-real-workspace', 'NOTES.md')
    expect(file.relativePath).toBe('NOTES.md')
    expect(file.content).toContain('demo content')

    expect(await mockRegisteredWorkspaceService.search('demo-real-workspace', '')).toHaveLength(0)
    const hits = await mockRegisteredWorkspaceService.search('demo-real-workspace', 'demo')
    expect(hits.length).toBeGreaterThan(0)
  })
})

describe('httpRegisteredWorkspaceService', () => {
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

  it('hits the registered-workspaces endpoints with encoded query params', async () => {
    const fetchMock = stubFetch([])

    await httpRegisteredWorkspaceService.listRegisteredWorkspaces()
    expect(fetchMock.mock.calls[0][0]).toContain('/registered-workspaces')

    await httpRegisteredWorkspaceService.listFiles('ws-1', 'src/sub dir')
    expect(fetchMock.mock.calls[1][0]).toContain(
      '/registered-workspaces/ws-1/files?path=src%2Fsub%20dir',
    )

    await httpRegisteredWorkspaceService.search('ws-1', 'a&b')
    expect(fetchMock.mock.calls[2][0]).toContain(
      '/registered-workspaces/ws-1/search?query=a%26b',
    )
  })

  it('reads a single file via the file endpoint', async () => {
    const fetchMock = stubFetch({ relativePath: 'NOTES.md', content: 'x' })

    const file = await httpRegisteredWorkspaceService.readFile('ws-1', 'NOTES.md')
    expect(fetchMock.mock.calls[0][0]).toContain(
      '/registered-workspaces/ws-1/file?path=NOTES.md',
    )
    expect(file.content).toBe('x')
  })
})
