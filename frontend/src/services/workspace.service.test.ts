import { describe, expect, it } from 'vitest'
import { mockWorkspaceService } from './workspace.service'

describe('mockWorkspaceService', () => {
  it('returns recent workspaces with status, tags and time', async () => {
    const recent = await mockWorkspaceService.getRecentWorkspaces()

    expect(recent.length).toBeGreaterThanOrEqual(4)
    expect(recent[0]).toMatchObject({
      name: expect.any(String),
      rootPath: expect.any(String),
      status: 'waiting',
      tags: expect.arrayContaining([expect.any(String)]),
    })
  })

  it('returns all registered workspaces', async () => {
    const all = await mockWorkspaceService.getAllWorkspaces()

    expect(all.length).toBeGreaterThanOrEqual(7)
    expect(all.every(w => w.name && w.rootPath)).toBe(true)
  })

  it('filters drawer by name', async () => {
    const all = await mockWorkspaceService.getAllWorkspaces()

    const dashboard = all.filter(w => w.name.includes('dashboard'))
    expect(dashboard).toHaveLength(1)
    expect(dashboard[0].name).toBe('dashboard-ui')
  })
})
